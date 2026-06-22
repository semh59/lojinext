"""Runtime, inference-only predictor wrappers (Phase 4.0).

Bu modüller training kodunu (`fit`, `save_model`) HİÇ expose etmez. Diskten
serialize edilmiş .pkl artifact'i yükleyip `predict()` çağrısını dışa
açar. Bu sayede production deploy'a training kodu (xgboost.train, sklearn
fit, vb.) inmez ve test izolasyonu kolaylaşır.

Eğitim için ``app.core.ml.training`` paketi kullanılır — iki paket
birbirini import ETMEZ (cross-dependency guard).
"""

from app.core.ml.predictors.ensemble_predictor import EnsemblePredictor

__all__ = ["EnsemblePredictor"]
