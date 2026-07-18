"""Trainer — offline batch model eğitim wrapper (Phase 4.0).

Mevcut ``EnsemblePredictorService.train_for_vehicle()`` ve
``train_general_model()`` mantığına thin facade. SeferWriteService /
inference path bu sınıfı ASLA import etmez — sadece Celery beat task
(``scheduler_task.py``) ve manuel admin endpoint kullanır.

Yeni training ihtiyaçları (Phase 4.2 sonrası faktör kalibrasyonu,
Phase 5 pilot veri kalibrasyonu) bu pakete eklenir.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class Trainer:
    """Offline model eğitim facade.

    Constructor lightweight — gerçek `EnsemblePredictorService` lazy
    import edilir. Inference path bu sınıfı import etse bile
    xgboost/lightgbm ekleri yüklenmez (yalnız `run()` çağrılırsa).
    """

    def __init__(self) -> None:
        self._service: Optional[Any] = None

    @property
    def service(self) -> Any:
        """Lazy: ``EnsemblePredictorService`` singleton."""
        if self._service is None:
            from v2.modules.prediction_ml.application.ensemble_service import (
                get_ensemble_service,
            )

            self._service = get_ensemble_service()
        return self._service

    async def train_for_vehicle(self, arac_id: int) -> Dict[str, Any]:
        """Tek araç için ensemble model eğit + diske kaydet.

        Returns:
            {success: bool, ...metrics}
        """
        logger.info("Trainer.train_for_vehicle started: arac_id=%s", arac_id)
        result = await self.service.train_for_vehicle(arac_id)
        logger.info(
            "Trainer.train_for_vehicle done: arac_id=%s, success=%s",
            arac_id,
            result.get("success"),
        )
        return result

    async def train_general_model(self) -> Dict[str, Any]:
        """Filo seviyesi cold-start model (yeni araçlar için baseline).

        Returns:
            {success: bool, ...metrics}
        """
        logger.info("Trainer.train_general_model started")
        result = await self.service.train_general_model()
        logger.info(
            "Trainer.train_general_model done: success=%s", result.get("success")
        )
        return result


__all__ = ["Trainer"]
