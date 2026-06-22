"""EnsemblePredictor — inference-only wrapper (Phase 4.0).

Mevcut ``EnsembleFuelPredictor`` (ensemble_core.py:85, 1290 satır)
``fit()``, ``save_model()`` ve ``predict()`` aynı sınıfta tutuyor.
Bu sınıfı bölmek pickle backward-compat'i kıracağı için risk yüksek;
bunun yerine **inference-only wrapper** ile mantıksal ayrım yapıyoruz:

- ``EnsemblePredictor`` SADECE ``predict()`` expose eder
- ``fit()`` / ``save_model()`` metodları YOK — type-level enforcement
- ``EnsembleFuelPredictor`` import'u lazy (constructor içinde) → modülü
  import etmek xgboost/lightgbm/sklearn'i otomatik yüklemiyor; sadece
  predictor instance oluşturulduğunda iniyorlar
- Training için ``app.core.ml.training.trainer.Trainer`` kullanılır

İki paket cross-import etmez (Phase 4.0 mimari kuralı).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class EnsemblePredictor:
    """Inference-only ensemble wrapper.

    Constructor diskten model yükler; ``predict(sefer)`` çağrısı saf math
    + ML model inference yapar (fit YOK).

    Args:
        model_path: ``EnsembleFuelPredictor.save_model()`` çıktısı (.pkl)
            base path. ``{base}.pkl`` + ``{base}_xgb.json`` + ``{base}_lgb.json``
            + ``{base}_meta.json`` artifactlerini bekler.
        model_id: log/metric için isim (örn. ``arac_123`` veya ``class_heavy``).

    Raises:
        FileNotFoundError: model_path bulunamazsa.
    """

    def __init__(self, model_path: str, model_id: Optional[str] = None) -> None:
        # LAZY IMPORT — modül-seviyesi import xgboost/lightgbm/sklearn'i
        # ZORUNLU yüklerdi. Burada constructor içinde tutmak, predictor
        # instance oluşturulmadan önce ML libs RAM'e inmemesini sağlar.
        from app.core.ml.ensemble_core import EnsembleFuelPredictor

        path = Path(model_path)
        if not (path.parent / f"{path.stem}.pkl").exists():
            raise FileNotFoundError(f"Model artifact bulunamadı: {model_path}")

        self._inner: EnsembleFuelPredictor = EnsembleFuelPredictor()
        self._inner.load_model(str(path))
        self._model_id = model_id or path.stem
        # Inference-only: training stats production'da gereksiz, drop
        self._inner.training_stats = {}
        logger.info(
            "EnsemblePredictor loaded: id=%s, is_trained=%s, weights=%s",
            self._model_id,
            self._inner.is_trained,
            self._inner.weights,
        )

    def predict(self, sefer: Dict[str, Any]) -> Any:
        """Tek sefer dictinden tahmin üret.

        Returns:
            PredictionResult (tahmin_l_100km, physics_only, ml_correction, ...)
        """
        return self._inner.predict(sefer)

    @property
    def is_trained(self) -> bool:
        return self._inner.is_trained

    @property
    def weights(self) -> Dict[str, float]:
        return dict(self._inner.weights)

    @property
    def model_id(self) -> str:
        return self._model_id


__all__ = ["EnsemblePredictor"]
