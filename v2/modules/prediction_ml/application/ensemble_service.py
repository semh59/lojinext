"""TIR Yakıt Takip - Ensemble Servis Katmanı / EnsemblePredictorService: DB entegrasyonu ve model yönetimi."""

import asyncio
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

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
    from app.database.unit_of_work import UnitOfWork
    from v2.modules.prediction_ml.application.ml_service import MLService

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
        self._arac_repo = None
        self._sefer_repo = None
        self._dorse_repo = None
        self.predictors: OrderedDict[int, EnsembleFuelPredictor] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def arac_repo(self):
        if self._arac_repo is None:
            from v2.modules.fleet.public import get_arac_repo

            self._arac_repo = get_arac_repo()
        return self._arac_repo

    @property
    def sefer_repo(self):
        if self._sefer_repo is None:
            from v2.modules.trip.public import get_sefer_repo

            self._sefer_repo = get_sefer_repo()
        return self._sefer_repo

    @property
    def dorse_repo(self):
        if self._dorse_repo is None:
            from v2.modules.fleet.public import get_dorse_repo

            self._dorse_repo = get_dorse_repo()
        return self._dorse_repo

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
        legacy_repo,
    ) -> None:
        model_path = str(Path("app/models") / f"ensemble_v2_{model_id}.pkl")
        await _register_model_version(
            arac_id=model_id,
            predictor=predictor,
            result=result,
            model_path=model_path,
        )

        try:
            await legacy_repo.save_model_params(model_id, result)
        except Exception as e:
            logger.error(f"Failed to save legacy fallback model {model_id}: {e}")

        try:
            model_dir = Path("app/models")
            model_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(predictor.save_model, model_path)
        except Exception as e:
            logger.error(f"Failed to serialize fallback model {model_id}: {e}")

    def get_predictor(self, arac_id: int) -> EnsembleFuelPredictor:
        """Araç için predictor al veya oluştur (Thread-Safe + LRU Cache)"""
        with self._lock:
            if arac_id in self.predictors:
                # LRU: Mevcut olanı sona taşı (most recently used)
                self.predictors.move_to_end(arac_id)
                return self.predictors[arac_id]

            # Yeni oluştur
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
                    from app.infrastructure.monitoring.ml_probe import get_ml_probe

                    get_ml_probe().record_model_load_failure(
                        model_id=f"ensemble_v2_{arac_id}", exc=e
                    )
                except Exception:
                    pass

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
            "ids_hash": hashlib.md5(",".join(sample_ids).encode()).hexdigest()[:8],
        }

        return hashlib.sha256(
            json.dumps(stats_fingerprint, sort_keys=True).encode()
        ).hexdigest()[:16]

    async def train_for_vehicle(self, arac_id: int) -> Dict:
        """
        Belirli araç için model eğit.
        Veritabanından verileri toplar ve enrich eder.
        """
        from app.core.services.weather_service import get_weather_service
        from v2.modules.driver.public import get_driver_stats

        # Araç bilgisini al
        arac = await self.arac_repo.get_by_id(arac_id)
        if not arac:
            return {"success": False, "error": "Araç bulunamadı"}

        # Araç yaşı ve faktörü hesapla
        from v2.modules.fleet.public import Arac

        try:
            arac_entity = Arac(**arac)
            arac_yasi = arac_entity.yas
            yas_faktoru = arac_entity.yas_faktoru
        except Exception as _e:
            logger.warning(
                "Arac entity mapping failed for arac_id=%s (%s); using defaults.",
                arac_id,
                _e,
            )
            arac_yasi = 0
            yas_faktoru = 1.0

        # Eğitim verilerini al
        seferler = await self.sefer_repo.get_for_training(arac_id, limit=500)
        if len(seferler) < 10:
            return {"success": False, "error": f"Yetersiz veri: {len(seferler)} sefer"}

        # Verileri enrich et
        weather_service = get_weather_service()

        # Optimized: Bulk fetch driver stats Once (Phase 2G Optimization)
        # Using include_elite_score=False to prevent QueuePool exhaustion (Phase 2G Fix)
        all_driver_stats = await get_driver_stats(include_elite_score=False)
        driver_map = {d.sofor_id: d for d in all_driver_stats}

        enriched_seferler = []
        y_values = []

        for s in seferler:
            # Mevsim faktörü
            target_date = self._resolve_trip_date(s.get("tarih"))
            mevsim_faktor = weather_service.get_seasonal_factor(target_date)

            # Şoför faktörü (varsa) - Using lookup map instead of API call
            sofor_katsayi = 1.0
            sid = s.get("sofor_id")
            if sid and sid in driver_map:
                driver = driver_map[sid]
                # Filo karşılaştırmadan şoför katsayısı
                sofor_katsayi = 1.0 - (driver.filo_karsilastirma / 100) * 0.1

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
            logger.info(f"Model version registered for vehicle {arac_id}")

            # 2. AnalizRepo ile Legacy Kayıt (YakitFormul)
            try:
                from v2.modules.analytics_executive.public import get_analiz_repo

                analiz_repo = get_analiz_repo()
                await analiz_repo.save_model_params(arac_id, result)
                logger.info(f"Legacy model params saved for vehicle {arac_id}")
            except Exception as e:
                logger.error(f"Failed to save legacy model params: {e}")

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
            from v2.modules.analytics_executive.public import get_analiz_repo

            analiz_repo = get_analiz_repo()

            seferler = await self.sefer_repo.get_all_for_training(limit=2000)

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
                await analiz_repo.save_model_params(0, result)

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
                        legacy_repo=analiz_repo,
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
        uow=None,  # Optimization for session reuse
        route_analysis: Optional[Dict] = None,  # Phase 8
    ) -> Dict:
        """
        Yakıt tüketimi tahmin et
        """
        from app.core.services.weather_service import get_weather_service
        from v2.modules.driver.public import get_driver_stats

        # Single Session Reuse Pattern (Phase 3 Optimization)
        if uow:
            arac = await uow.arac_repo.get_by_id(arac_id)
        else:
            arac = await self.arac_repo.get_by_id(arac_id)

        if not arac:
            return {"success": False, "error": "Araç bulunamadı"}

        # Dorse verisi (Phase 4)
        dorse = None
        if dorse_id:
            if uow:
                dorse = await uow.dorse_repo.get_by_id(dorse_id)
            else:
                dorse = await self.dorse_repo.get_by_id(dorse_id)

        from v2.modules.fleet.public import Arac

        try:
            arac_entity = Arac(**arac)
        except Exception as _e:
            # Mapping başarısızsa uydurma 2020 modeli ile tahmin yapmak
            # production-aykırı (yaş faktörü yanlış, predicted_consumption
            # gerçek araç ile uyumsuz). Çağrıyı iptal et — endpoint katmanı
            # 503 dönsün, frontend retry / fallback'i kullansın.
            logger.error(
                "Arac entity mapping failed for arac_id=%s (%s); "
                "prediction iptal edildi (fake-2020 fallback üretilmiyor).",
                arac_id,
                _e,
            )
            raise RuntimeError(f"Arac entity {arac_id} mapping failed: {_e}") from _e

        # Mevsim faktörü
        weather_service = get_weather_service()
        target = target_date or date.today()
        mevsim_faktor = weather_service.get_seasonal_factor(target)

        # Şoför faktörü
        sofor_katsayi = 1.0
        if sofor_id:
            # Pass 'uow' for session consistency (Phase 3 Optimization)
            stats = await get_driver_stats(sofor_id, include_elite_score=False, uow=uow)
            if stats:
                sofor_katsayi = 1.0 - (stats[0].filo_karsilastirma / 100) * 0.1

        sefer = {
            "mesafe_km": mesafe_km,
            "ton": ton,
            "ascent_m": ascent_m,
            "descent_m": descent_m,
            "arac_yasi": arac_entity.yas,
            "yas_faktoru": arac_entity.yas_faktoru,
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
                "arac_yasi": arac_entity.yas,
                "yas_faktoru": round(arac_entity.yas_faktoru, 3),
                "euro_sinifi": arac_entity.euro_sinifi,
                "mevsim_faktor": mevsim_faktor,
                "sofor_katsayi": round(sofor_katsayi, 3),
            },
        }

    async def predict_batch(self, requests: List[Dict]) -> List[Dict]:
        """
        Gelişmiş N+1 Fix: Tek session ile toplu tahmin (Phase 3)
        """
        from app.database.unit_of_work import UnitOfWork

        results = []
        async with UnitOfWork() as uow:
            for req in requests:
                res = await self.predict_consumption(uow=uow, **req)
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
