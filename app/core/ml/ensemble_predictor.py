"""
Backward-compat re-export shim.
Yeni kod ensemble_core ve ensemble_service'i doğrudan import etmeli.
"""

from app.core.ml.ensemble_core import (  # noqa: F401
    LIGHTGBM_AVAILABLE,
    SKLEARN_AVAILABLE,
    XGBOOST_AVAILABLE,
    EnsembleFuelPredictor,
    PredictionResult,
    SecurityError,
)
from app.core.ml.ensemble_service import (  # noqa: F401
    EnsemblePredictorService,
    get_ensemble_service,
)

__all__ = [
    "EnsembleFuelPredictor",
    "LIGHTGBM_AVAILABLE",
    "SKLEARN_AVAILABLE",
    "XGBOOST_AVAILABLE",
    "PredictionResult",
    "SecurityError",
    "EnsemblePredictorService",
    "get_ensemble_service",
]
