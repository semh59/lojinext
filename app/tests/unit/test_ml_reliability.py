from pathlib import Path

import numpy as np
import pytest

from v2.modules.prediction_ml.domain.ensemble_core import (
    EnsembleFuelPredictor,
    SecurityError,
)
from v2.modules.prediction_ml.domain.time_series_predictor import TimeSeriesPredictor


def test_ensemble_security_checksum(tmp_path):
    predictor = EnsembleFuelPredictor()
    # Modeli eğitmeden kaydedemeyiz, bu yüzden is_trained'i manuel set edelim (mock gibi)
    predictor.is_trained = True
    predictor.training_stats = {"physics_mae": 0.1}

    model_path = tmp_path / "test_model"
    # sklearn modellerini mocklamalıyız veya basit bir fit yapmalıyız
    # En basiti: dummy fit
    seferler = [{"mesafe_km": 100, "ton": 20, "ascent_m": 100, "descent_m": 50}] * 10
    actuals = np.array([30.0] * 10)
    predictor.fit(seferler, actuals)

    predictor.save_model(str(model_path))

    # Dosyayı manipüle et (tempering)
    sklearn_file = Path(f"{model_path}_sklearn.joblib")
    with open(sklearn_file, "ab") as f:
        f.write(b"corrupted")

    # Yüklemeye çalışınca SecurityError fırlatmalı
    new_predictor = EnsembleFuelPredictor()
    with pytest.raises(SecurityError):
        new_predictor.load_model(str(model_path))


def test_time_series_normalization_nan():
    predictor = TimeSeriesPredictor()
    X = np.array([[[32.0, np.nan], [np.inf, 35.0]]])  # (1, 2, 2)
    # create_sequences gibi bir yapı yerine doğrudan normalize'ı test et
    try:
        X_norm = predictor.normalize(X, fit=True)
        assert np.all(np.isfinite(X_norm)), "Normalized array contains NaN or Inf"
    except Exception as e:
        pytest.fail(f"Normalization failed with NaN/Inf: {e}")
