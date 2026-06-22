"""
TIR Yakıt Takip - Yakıt Tahmin Servisi
ML tabanlı yakıt tahmini iş mantığı

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: Yakıt tahmin motoru — regresyon modeli singleton tutulur.
CREATED_BY: app/core/container.py (lazy property)
"""

from typing import Any, Dict

import numpy as np

from app.core.ml.fuel_predictor import LinearRegressionModel
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class YakitTahminService:
    """
    Yakıt Tahminleme Servisi (Async Business Logic)
    """

    def __init__(self):
        self.model = LinearRegressionModel()
        self._analiz_repo = None
        self._arac_repo = None

    @property
    def analiz_repo(self):
        if self._analiz_repo is None:
            from app.database.repositories.analiz_repo import get_analiz_repo

            self._analiz_repo = get_analiz_repo()
        return self._analiz_repo

    @property
    def arac_repo(self):
        if self._arac_repo is None:
            from app.database.repositories.arac_repo import get_arac_repo

            self._arac_repo = get_arac_repo()
        return self._arac_repo

    async def train_model(self, arac_id: int) -> Dict:
        """Belirtilen araç için modeli eğitir (Async)"""
        seferler = await self.analiz_repo.get_training_seferler(arac_id, limit=200)

        # Zorluk derecesini sayısal değere çevir
        zorluk_map = {"Normal": 0, "Orta": 1, "Zor": 2}

        # 1. Eğitim verisi hazırlama (L/100km normalizasyonu ile)
        X_list = []
        y_list = []

        for s in seferler:
            mesafe = float(s["mesafe_km"])
            tuketim = float(s["tuketim"])

            if mesafe <= 0:
                continue

            # Hedef değişkeni L/100km'ye çevir (Kritik Düzeltme)
            l_100km = (tuketim / mesafe) * 100

            X_list.append(
                [
                    mesafe,
                    float(s["ton"]),
                    float(s.get("ascent_m", 0) or 0),
                    float(zorluk_map.get(s.get("zorluk", "Normal"), 0)),
                    float(s.get("flat_distance_km", 0) or 0),
                ]
            )
            y_list.append(l_100km)

        if not X_list:
            return {
                "success": False,
                "error": "Geçerli eğitim verisi bulunamadı (mesafe > 0 olmalı)",
            }

        X = np.array(X_list)
        y = np.array(y_list)

        local_model = LinearRegressionModel()
        result = local_model.fit(X, y)

        if result["success"]:
            await self.analiz_repo.save_model_params(arac_id, result)

        return result

    async def predict(
        self,
        arac_id: int,
        mesafe_km: float,
        ton: float,
        ascent_m: float = 0,
        flat_distance_km: float = 0,
        zorluk: str = "Normal",
        sofor_id: int = None,
    ) -> Dict:
        """Yeni bir sefer için yakıt tahmini yapar (Async)"""
        params = await self.analiz_repo.get_model_params(arac_id)

        if not params:
            return {
                "success": False,
                "error": "Bu araç için eğitilmiş model bulunamadı.",
                "requires_training": True,
            }

        # Her çağrıda yeni model nesnesi — singleton self.model'ı overwrite etmez
        # (concurrent request'lerde farklı araç params çakışmasını önler).
        local_model = LinearRegressionModel()
        local_model.coefficients = np.array(params["coefficients"]["weights"])
        local_model.intercept = params["coefficients"]["intercept"]
        local_model.r_squared_score = params["r_squared"]
        local_model._is_fitted = True

        if "scaling" in params:
            local_model.set_scaling_params(params["scaling"])
        elif "scaling" in params.get("coefficients", {}):
            local_model.set_scaling_params(params["coefficients"]["scaling"])

        # Zorluk dönüşümü
        zorluk_map = {"Normal": 0, "Orta": 1, "Zor": 2}
        z_val = float(zorluk_map.get(zorluk, 0))

        X_input = np.array([[mesafe_km, ton, ascent_m, z_val, flat_distance_km]])

        try:
            y_pred, meta = local_model.predict(X_input)
            l_100km_pred = float(y_pred[0])
            # [B-10] Fix: Convert L/100km to total Liters for the distance
            tahmin_litre = (l_100km_pred * mesafe_km) / 100

            sofor_faktor = 1.0
            if sofor_id:
                try:
                    from app.core.services.sofor_analiz_service import (
                        get_sofor_analiz_service,
                    )

                    analiz_service = get_sofor_analiz_service()

                    # DOĞRUDAN AWAIT! (Artık async metoddasın)
                    stats_list = await analiz_service.get_driver_stats(
                        sofor_id=sofor_id
                    )

                    if stats_list:
                        score = stats_list[0].performans_puani
                        if score is not None:
                            impact = 0.05
                            sofor_faktor = 1.0 - ((score - 50) / 50 * impact)
                            sofor_faktor = max(0.9, min(1.1, sofor_faktor))
                        else:
                            sofor_faktor = 1.0
                    else:
                        sofor_faktor = 1.0

                except Exception as e:
                    logger.warning(f"Driver factor calculation failed: {e}")

            final_tahmin = tahmin_litre * sofor_faktor
            tuketim_100km = (final_tahmin / mesafe_km) * 100 if mesafe_km > 0 else 0
            margin_percent = 0.08 if sofor_faktor > 1.0 else 0.05
            margin = final_tahmin * margin_percent

            return {
                "success": True,
                "tahmin_litre": round(final_tahmin, 1),
                "tahmin_tuketim_100km": round(tuketim_100km, 1),
                "guven_araligi": (
                    round(final_tahmin - margin, 1),
                    round(final_tahmin + margin, 1),
                ),
                "model_r2": round(params["r_squared"], 2),
                "sample_count": params["sample_count"],
                "last_trained": params["updated_at"],
                "sofor_faktor": round(sofor_faktor, 3),
            }

        except Exception as e:
            logger.error(f"Prediction error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def retrain_all_models(self) -> Dict:
        """Sistemdeki tüm araçlar için modelleri günceller (Async & Parallel)"""
        import asyncio

        araclar = await self.arac_repo.get_all(sadece_aktif=True)
        results: Dict[str, Any] = {"success": 0, "failed": 0, "details": []}

        sem = asyncio.Semaphore(3)  # ML eğitimleri ağır olduğu için düşük limit

        async def train_safe(arac):
            async with sem:
                res = await self.train_model(arac["id"])
                return arac["plaka"], res

        coros = [train_safe(a) for a in araclar]
        batch_results = await asyncio.gather(*coros)

        for plaka, res in batch_results:
            if res["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append(f"{plaka}: {res.get('error', 'OK')}")

        return results


def get_yakit_tahmin_service() -> YakitTahminService:
    from app.core.container import get_container

    return get_container().yakit_tahmin_service
