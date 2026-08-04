"""TIR Yakıt Takip - Ensemble Servis Katmanı / EnsemblePredictorService: DB entegrasyonu ve model yönetimi."""

import asyncio
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor
from prediction_ml_service.domain.seasonal_factor import get_seasonal_factor
from prediction_ml_service.domain.vehicle_age import (
    compute_euro_class,
    compute_vehicle_age_factor,
)
from prediction_ml_service.infrastructure import cross_module_client
from v2.modules.platform_infra.public import get_logger

logger = get_logger(__name__)


async def _register_model_version(
    *,
    arac_id: int,
    predictor: EnsembleFuelPredictor,
    result: Dict,
    model_path: str,
) -> None:
    """`model_versiyonlar` tablosuna gerçek versiyon kaydı yaz.

    Eskiden burada `app.core.ml.model_manager.ModelManager.save_version()`
    çağrılıyordu — o sınıf var olmayan bir `model_versions` tablosuna raw
    SQL yazıyordu (FAZ0 tespiti, 2026-07-18: alembic geçmişinde bu tablo
    hiç bulunmuyor, sadece bir index adı kısa süre bu ismi taşımış).
    Gerçek yazım yolu `MLService.register_model_version()` — ORM ile
    `model_versiyonlar`'a yazar; `GET /admin/ml/versions/{arac_id}` bu
    veriyi okur ama hiçbir prod çağrısı bu metodu tetiklemiyordu (dead
    write path). Bu fonksiyon 3 çağıran sitesinde (`_persist_fallback_model`,
    `train_for_vehicle`, `train_general_model`) ortak kullanılır — hem
    doğru tabloya yazar hem de kendi try/except'i sayesinde `train_general_
    model`'in eski davranışını düzeltir (versiyon kaydı hatası artık
    zaten hesaplanmış eğitim sonucunu / disk kaydını / class-model
    döngüsünü iptal etmiyor).
    """
    from prediction_ml_service.application.ml_service import MLService
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

    try:
        measurements = result.get("measurements", {})
        metrics_payload = result.get("metrics", {})
        r2 = (
            metrics_payload.get("gb_test_r2")
            or result.get("ensemble_r2")
            or metrics_payload.get("gb_cv_mean")
        )
        async with UnitOfWork() as uow:
            ml_service = MLService(uow)
            latest = await uow.model_versiyon_repo.get_latest_version(arac_id)
            next_version = 1 if latest is None else latest.versiyon + 1
            await ml_service.register_model_version(
                arac_id=arac_id,
                versiyon=next_version,
                metrics={
                    "r2_skoru": r2,
                    "mae": measurements.get("mae"),
                    "mape": measurements.get("mape"),
                    "rmse": measurements.get("rmse"),
                },
                model_dosya_yolu=model_path,
                kullanilan_ozellikler=result.get("feature_importance", {}),
                veri_sayisi=int(result.get("sample_count") or 0),
            )
    except Exception as e:
        logger.error(f"Failed to register model version for arac_id={arac_id}: {e}")


class EnsemblePredictorService:
    """
    Ensemble predictor için iş mantığı servisi.
    Veritabanı entegrasyonu ve model yönetimi.
    """

    # Bellek yönetimi: her predictor ~50-100 MB (XGBoost+LightGBM+sklearn).
    # 100 predictor = 5-10 GB. Production'da 50 araç başına 5-10 GB makul.
    # Daha düşük tutmak için cache'i 20'ye sabitledik; LRU evict ile aktif
    # araçlar her zaman cache'de kalır.
    MAX_PREDICTORS = 20

    VEHICLE_CLASS_MODEL_IDS = {
        "heavy": 10000,
        "medium": 10001,
        "light": 10002,
    }
    MIN_CLASS_MODEL_SAMPLES = 10

    def __init__(self):
        self.predictors: OrderedDict[int, EnsembleFuelPredictor] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_trip_date(raw_value) -> date:
        if isinstance(raw_value, date):
            return raw_value
        if raw_value:
            try:
                return date.fromisoformat(str(raw_value)[:10])
            except ValueError:
                pass
        return date.today()

    def _get_vehicle_class(self, arac: Dict) -> str:
        tank = float(arac.get("tank_kapasitesi") or 0)
        if tank >= 500:
            return "heavy"
        if tank >= 200:
            return "medium"
        return "light"

    def _get_vehicle_class_model_id(self, arac: Dict) -> int:
        return self.VEHICLE_CLASS_MODEL_IDS[self._get_vehicle_class(arac)]

    @staticmethod
    def _extract_route_analysis(sefer: Dict) -> Optional[Dict]:
        rota_detay = sefer.get("rota_detay")
        if not isinstance(rota_detay, dict):
            return None
        route_analysis = rota_detay.get("route_analysis") or rota_detay
        return route_analysis if isinstance(route_analysis, dict) else None

    async def _persist_fallback_model(
        self,
        model_id: int,
        predictor: EnsembleFuelPredictor,
        result: Dict,
        seferler: List[Dict],
        notes: str,
    ) -> None:
        model_path = str(Path("app/models") / f"ensemble_v2_{model_id}.pkl")
        await _register_model_version(
            arac_id=model_id,
            predictor=predictor,
            result=result,
            model_path=model_path,
        )
        self._bump_model_version(model_id)
        predictor._cached_model_version = self._get_model_version(model_id)

        await cross_module_client.save_model_params(model_id, result)

        try:
            model_dir = Path("app/models")
            model_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(predictor.save_model, model_path)
        except Exception as e:
            logger.error(f"Failed to serialize fallback model {model_id}: {e}")

    def _get_model_version(self, arac_id: int) -> int:
        """Read the shared model-version counter from Redis.

        Each worker/replica process keeps its own separate LRU cache
        (see the module CLAUDE.md's multi-worker LRU note) -- this
        counter signals to this process's `get_predictor()` that a
        newer model was trained in another process. `CacheManager.get()`
        already degrades gracefully (returns None) if Redis is
        unreachable -- 0 is assumed in that case.
        """
        from v2.modules.platform_infra.public import get_cache_manager

        cache = get_cache_manager()
        raw = cache.get(f"predictor_version:{arac_id}")
        return int(raw) if raw is not None else 0

    def _bump_model_version(self, arac_id: int) -> None:
        """Increment the shared model-version counter for this vehicle."""
        from v2.modules.platform_infra.public import get_cache_manager

        cache = get_cache_manager()
        current = self._get_model_version(arac_id)
        cache.set(f"predictor_version:{arac_id}", str(current + 1))

    def get_predictor(self, arac_id: int) -> EnsembleFuelPredictor:
        """Get or create a predictor for the vehicle (thread-safe + LRU cache)."""
        with self._lock:
            current_version = self._get_model_version(arac_id)
            if arac_id in self.predictors:
                cached = self.predictors[arac_id]
                if cached._cached_model_version >= current_version:
                    # LRU: move existing entry to the end (most recently used)
                    self.predictors.move_to_end(arac_id)
                    return cached
                # Another worker/replica trained a newer model -- the
                # in-memory predictor is stale, reload from disk below.
                del self.predictors[arac_id]

            # Create a new one
            predictor = EnsembleFuelPredictor()

            # Diskten yüklemeyi dene (Persistence Fix)
            try:
                model_dir = Path("app/models")
                model_path = model_dir / f"ensemble_v2_{arac_id}.pkl"
                # Meta dosyası varlığı en güvenilir kontrol (joblib + json hibrit yapısı)
                if (model_dir / f"ensemble_v2_{arac_id}_meta.json").exists():
                    predictor.load_model(str(model_path))
                    # Schema validation — runtime feature count ile model'in
                    # eğitildiği feature count uyumsuzsa modeli devre dışı bırak.
                    # Aksi halde her predict() çağrısı 4-10sn süren mismatch
                    # exception zinciri tetikler (production blocker).
                    expected = predictor._resolve_expected_feature_count()
                    runtime = len(predictor.FEATURE_NAMES)
                    count_mismatch = bool(expected and expected != runtime)

                    # 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 26): SAYI
                    # aynı kalsa bile isim/sıra değişmişse (feature drift) yukarıdaki
                    # kontrol bunu kaçırıyordu. Persisted hash None ise (eski, bu
                    # alan eklenmeden önce kaydedilmiş model dosyası) karşılaştırma
                    # atlanır — false positive üretmemek için.
                    loaded_hash = predictor._loaded_feature_schema_hash
                    hash_mismatch = bool(
                        loaded_hash and loaded_hash != predictor._feature_hash
                    )

                    if count_mismatch:
                        logger.warning(
                            f"Model schema mismatch for vehicle {arac_id}: "
                            f"trained={expected} vs runtime={runtime}. "
                            "Marking as untrained, physics fallback aktif."
                        )
                        predictor.is_trained = False
                    elif hash_mismatch:
                        logger.warning(
                            f"Model feature schema hash mismatch for vehicle "
                            f"{arac_id}: persisted={loaded_hash} vs "
                            f"runtime={predictor._feature_hash} (feature count "
                            "unchanged but name/order drifted). Marking as "
                            "untrained, physics fallback aktif."
                        )
                        predictor.is_trained = False
                    else:
                        logger.info(
                            f"Loaded existing model for vehicle {arac_id} from disk."
                        )
            except Exception as e:
                logger.debug(
                    f"No existing persistent model for vehicle {arac_id} or load failed: {e}"
                )
                try:
                    from prediction_ml_service.infrastructure.ml_probe import (
                        get_ml_probe,
                    )

                    get_ml_probe().record_model_load_failure(
                        model_id=f"ensemble_v2_{arac_id}", exc=e
                    )
                except Exception:
                    pass

            predictor._cached_model_version = current_version
            self.predictors[arac_id] = predictor

            # Limit aşılırsa en eskiyi (baştakini) çıkar
            if len(self.predictors) > self.MAX_PREDICTORS:
                oldest_id, _ = self.predictors.popitem(last=False)
                logger.debug(
                    f"LRU Cache: Arac {oldest_id} predictor bellekten temizlendi."
                )

            return predictor

    def _calculate_training_hash(self, seferler: List[Dict]) -> str:
        """
        Gelişmiş Eğitim Verisi Parmak İzi (Stratified & Statistical)
        Sadece ID değil, mesafe ve yük dağılımını da kapsar.
        """
        import hashlib
        import json

        if not seferler:
            return "empty"

        # 1. Örneklem ID'leri (ilk 100)
        sample_ids = [str(s.get("id", i)) for i, s in enumerate(seferler[:100])]

        # 2. İstatistiksel özet (Data Drift yakalamak için)
        distances = [float(s.get("mesafe_km", 0) or 0) for s in seferler]
        loads = [float(s.get("ton", 0) or 0) for s in seferler]

        stats_fingerprint = {
            "count": len(seferler),
            "mean_dist": round(np.mean(distances), 1) if distances else 0,
            "mean_load": round(np.mean(loads), 1) if loads else 0,
            "ids_hash": hashlib.sha256(",".join(sample_ids).encode()).hexdigest()[:8],
        }

        return hashlib.sha256(
            json.dumps(stats_fingerprint, sort_keys=True).encode()
        ).hexdigest()[:16]

    async def train_for_vehicle(self, arac_id: int) -> Dict:
        """
        Belirli araç için model eğit.
        Veritabanından verileri toplar ve enrich eder.
        """
        arac = await cross_module_client.get_vehicle(arac_id)
        if not arac:
            return {"success": False, "error": "Araç bulunamadı"}
        seferler = await cross_module_client.get_training_data(arac_id, limit=500)

        # Compute vehicle age and its degradation factor
        arac_yasi, yas_faktoru = compute_vehicle_age_factor(arac.get("yil"))

        if len(seferler) < 10:
            return {"success": False, "error": f"Yetersiz veri: {len(seferler)} sefer"}

        # Optimized: Bulk fetch driver stats Once (Phase 2G Optimization)
        # Using include_elite_score=False to prevent QueuePool exhaustion (Phase 2G Fix)
        all_driver_stats = await cross_module_client.get_driver_stats(
            include_elite_score=False
        )
        driver_map = {d["sofor_id"]: d for d in all_driver_stats}

        enriched_seferler = []
        y_values = []

        for s in seferler:
            # Seasonal factor
            target_date = self._resolve_trip_date(s.get("tarih"))
            mevsim_faktor = get_seasonal_factor(target_date)

            # Driver factor (if any) - using lookup map instead of API call
            sofor_katsayi = 1.0
            sid = s.get("sofor_id")
            if sid and sid in driver_map:
                driver = driver_map[sid]
                # Driver coefficient derived from fleet comparison
                sofor_katsayi = 1.0 - (driver["filo_karsilastirma"] / 100) * 0.1

            enriched = {
                **s,
                "arac_yasi": arac_yasi,
                "yas_faktoru": yas_faktoru,
                "mevsim_faktor": mevsim_faktor,
                "sofor_katsayi": sofor_katsayi,
            }

            enriched_seferler.append(enriched)
            y_values.append(float(s["tuketim"]))

        # Model eğit — blocking joblib/sklearn ops → thread pool
        predictor = await asyncio.to_thread(self.get_predictor, arac_id)
        result = await asyncio.to_thread(
            predictor.fit, enriched_seferler, np.array(y_values)
        )

        if result["success"]:
            logger.info(f"Ensemble model trained for vehicle {arac_id}: {result}")

            model_path = str(Path("app/models") / f"ensemble_v2_{arac_id}.pkl")

            # 1. model_versiyonlar tablosuna gerçek versiyon kaydı
            await _register_model_version(
                arac_id=arac_id,
                predictor=predictor,
                result=result,
                model_path=model_path,
            )
            self._bump_model_version(arac_id)
            predictor._cached_model_version = self._get_model_version(arac_id)
            logger.info(f"Model version registered for vehicle {arac_id}")

            # 2. Legacy record via analytics_executive (YakitFormul)
            await cross_module_client.save_model_params(arac_id, result)
            logger.info(f"Legacy model params saved for vehicle {arac_id}")

            # 3. Serialize Model to Disk (Persistence fix)
            try:
                model_dir = Path("app/models")
                model_dir.mkdir(parents=True, exist_ok=True)

                # Save the trained model
                await asyncio.to_thread(predictor.save_model, model_path)
                logger.info(f"Serialized ensemble model saved for vehicle {arac_id}")
            except Exception as e:
                logger.error(f"Failed to serialize model for vehicle {arac_id}: {e}")

        return result

    async def train_general_model(self) -> Dict:
        """
        Tüm araçların verilerini kullanarak GENEL bir model eğitir (Fallback Modeli).
        Araç ID = 0 olarak kaydedilir.
        """
        logger.info("Training General Fallback Model (Vehicle ID: 0).")
        try:
            seferler = await cross_module_client.get_all_training_data(limit=2000)

            if len(seferler) < 20:
                return {
                    "success": False,
                    "error": f"Yetersiz toplam veri: {len(seferler)}",
                }

            # 2. Modeli eğit — blocking joblib/sklearn ops → thread pool
            y_actual = np.array([float(s["tuketim"]) for s in seferler])
            predictor = await asyncio.to_thread(self.get_predictor, 0)
            result = await asyncio.to_thread(predictor.fit, seferler, y_actual)

            if result.get("success"):
                # 3. model_versiyonlar tablosuna gerçek versiyon kaydı.
                # Kendi try/except'i _register_model_version içinde — burada
                # ARTIK bir istisna çağrının geri kalanını (legacy kayıt,
                # disk serialize, class-model döngüsü) iptal edemez. Eskiden
                # bu blok dış `try` içindeydi ve save_version() (dead
                # model_versions tablosu) her seferinde patlayıp fonksiyonu
                # erken `except Exception` dalına düşürüyordu — general
                # model zaten eğitilmiş olsa bile diske hiç yazılmıyordu.
                model_path = str(Path("app/models") / "ensemble_v2_0.pkl")
                await _register_model_version(
                    arac_id=0,
                    predictor=predictor,
                    result=result,
                    model_path=model_path,
                )
                self._bump_model_version(0)
                predictor._cached_model_version = self._get_model_version(0)
                await cross_module_client.save_model_params(0, result)

                # 4. Serialize General Model to Disk
                try:
                    model_dir = Path("app/models")
                    model_dir.mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(predictor.save_model, model_path)
                    logger.info("Serialized General Fallback Model saved to disk.")
                except Exception as e:
                    logger.error(f"Failed to serialize general model: {e}")

                logger.info("General Fallback Model trained and saved successfully.")
                class_models_trained = {}
                class_datasets: Dict[str, List[Any]] = {
                    "heavy": [],
                    "medium": [],
                    "light": [],
                }

                for sefer in seferler:
                    class_datasets[self._get_vehicle_class(sefer)].append(sefer)

                for vehicle_class, rows in class_datasets.items():
                    if len(rows) < self.MIN_CLASS_MODEL_SAMPLES:
                        continue

                    model_id = self.VEHICLE_CLASS_MODEL_IDS[vehicle_class]
                    class_predictor = await asyncio.to_thread(
                        self.get_predictor, model_id
                    )
                    class_result = await asyncio.to_thread(
                        class_predictor.fit,
                        rows,
                        np.array([float(row["tuketim"]) for row in rows]),
                    )
                    if not class_result.get("success"):
                        continue

                    await self._persist_fallback_model(
                        model_id=model_id,
                        predictor=class_predictor,
                        result=class_result,
                        seferler=rows,
                        notes=f"{vehicle_class.title()} class fallback model",
                    )
                    class_models_trained[vehicle_class] = {
                        "model_id": model_id,
                        "sample_count": len(rows),
                    }

                result["class_models_trained"] = class_models_trained

            return result
        except Exception as e:
            logger.error(f"General model training failed: {e}")
            return {"success": False, "error": str(e)}

    async def predict_consumption(
        self,
        arac_id: int,
        mesafe_km: float,
        ton: float,
        sofor_id: Optional[int] = None,
        ascent_m: float = 0,
        descent_m: float = 0,
        dorse_id: Optional[int] = None,
        target_date: Optional[date] = None,
        is_empty_trip: bool = False,
        route_analysis: Optional[Dict] = None,  # Phase 8
    ) -> Dict:
        """
        Yakıt tüketimi tahmin et
        """
        arac = await cross_module_client.get_vehicle(arac_id)

        if not arac:
            return {"success": False, "error": "Araç bulunamadı"}

        # Dorse verisi (Phase 4)
        dorse = None
        if dorse_id:
            dorse = await cross_module_client.get_trailer(dorse_id)

        arac_yasi, yas_faktoru = compute_vehicle_age_factor(arac.get("yil"))
        euro_sinifi = compute_euro_class(arac.get("yil"))

        # Seasonal factor
        target = target_date or date.today()
        mevsim_faktor = get_seasonal_factor(target)

        # Driver coefficient
        sofor_katsayi = 1.0
        if sofor_id:
            stats = await cross_module_client.get_driver_stats(
                sofor_id, include_elite_score=False
            )
            if stats:
                sofor_katsayi = 1.0 - (stats[0]["filo_karsilastirma"] / 100) * 0.1

        sefer = {
            "mesafe_km": mesafe_km,
            "ton": ton,
            "ascent_m": ascent_m,
            "descent_m": descent_m,
            "arac_yasi": arac_yasi,
            "yas_faktoru": yas_faktoru,
            "mevsim_faktor": mevsim_faktor,
            "sofor_katsayi": sofor_katsayi,
            "is_empty_trip": is_empty_trip,
            "dorse_bos_agirlik": dorse.get("bos_agirlik_kg") if dorse else 6500.0,
            "dorse_lastik_sayisi": dorse.get("lastik_sayisi") if dorse else 6,
            "dorse_lastik_direnci": dorse.get("dorse_lastik_direnc_katsayisi")
            if dorse
            else 0.006,
            "dorse_hava_direnci": dorse.get("dorse_hava_direnci") if dorse else 0.13,
            "rota_detay": {"route_analysis": route_analysis}
            if route_analysis
            else None,
        }

        # get_predictor may joblib.load from disk → run in thread pool
        predictor = await asyncio.to_thread(self.get_predictor, arac_id)

        # Phase 4: Fallback to General Model (ID 0) if vehicle-specific is not trained
        if not predictor.is_trained and arac_id != 0:
            class_model_id = self._get_vehicle_class_model_id(arac)
            class_predictor = await asyncio.to_thread(
                self.get_predictor, class_model_id
            )
            if class_predictor.is_trained:
                logger.info(
                    f"Vehicle {arac_id} model not trained. Using {self._get_vehicle_class(arac)} class fallback ({class_model_id})."  # noqa: E501
                )
                predictor = class_predictor
            else:
                logger.info(
                    f"Vehicle {arac_id} model not trained. Using General Model (ID 0) fallback."
                )
                predictor = await asyncio.to_thread(self.get_predictor, 0)

        result = await asyncio.to_thread(predictor.predict, sefer)

        interval = result.confidence_high - result.confidence_low
        confidence_score = max(
            0.0, min(1.0, 1 - interval / (2 * max(result.tahmin_l_100km, 1e-6)))
        )
        return {
            "success": True,
            "tahmin_l_100km": result.tahmin_l_100km,
            "tahmin_litre": round(mesafe_km * result.tahmin_l_100km / 100, 1),
            "guven_araligi": (result.confidence_low, result.confidence_high),
            "confidence_score": round(confidence_score, 3),
            "physics_only": result.physics_only,
            "ml_correction": result.ml_correction,
            "factors": {
                "arac_yasi": arac_yasi,
                "yas_faktoru": round(yas_faktoru, 3),
                "euro_sinifi": euro_sinifi,
                "mevsim_faktor": mevsim_faktor,
                "sofor_katsayi": round(sofor_katsayi, 3),
            },
        }

    async def predict_batch(self, requests: List[Dict]) -> List[Dict]:
        """Batch predictions -- one HTTP round-trip per vehicle/trailer lookup

        (the old single-UnitOfWork session-reuse optimization no longer
        applies now that fleet/driver data is fetched over HTTP, not a
        shared DB session -- see cross_module_client.py).
        """
        results = []
        for req in requests:
            res = await self.predict_consumption(**req)
            results.append(res)
        return results


# Singleton (Thread-Safe Double-Checked Locking)
_ensemble_service = None
_ensemble_service_lock = threading.Lock()


def get_ensemble_service() -> EnsemblePredictorService:
    """Thread-safe singleton erişimi"""
    global _ensemble_service
    if _ensemble_service is None:
        with _ensemble_service_lock:
            if _ensemble_service is None:  # Double-checked locking
                _ensemble_service = EnsemblePredictorService()
    return _ensemble_service
