"""
Moved whole from app/tests/unit/test_ml_reliability.py (missed in the
original Task 5 test-fix punch list, caught by a real CI lint run
2026-08-05): EnsembleFuelPredictor/SecurityError/TimeSeriesPredictor only
live in this service's own package now. Mechanical import-path fix only,
no behavioral changes.
"""

from pathlib import Path

import numpy as np
import pytest
from prediction_ml_service.domain.ensemble_core import (
    EnsembleFuelPredictor,
    SecurityError,
)
from prediction_ml_service.domain.time_series_predictor import TimeSeriesPredictor


def test_ensemble_security_checksum(tmp_path):
    predictor = EnsembleFuelPredictor()
    # Can't save an untrained model, so set is_trained manually (mock-like)
    predictor.is_trained = True
    predictor.training_stats = {"physics_mae": 0.1}

    model_path = tmp_path / "test_model"
    # Need a real (dummy) fit rather than mocking the sklearn models
    seferler = [{"mesafe_km": 100, "ton": 20, "ascent_m": 100, "descent_m": 50}] * 10
    actuals = np.array([30.0] * 10)
    predictor.fit(seferler, actuals)

    predictor.save_model(str(model_path))

    # Tamper with the file
    sklearn_file = Path(f"{model_path}_sklearn.joblib")
    with open(sklearn_file, "ab") as f:
        f.write(b"corrupted")

    # Loading a tampered file must raise SecurityError
    new_predictor = EnsembleFuelPredictor()
    with pytest.raises(SecurityError):
        new_predictor.load_model(str(model_path))


def test_time_series_normalization_nan():
    predictor = TimeSeriesPredictor()
    X = np.array([[[32.0, np.nan], [np.inf, 35.0]]])  # (1, 2, 2)
    # Test normalize() directly rather than going through create_sequences
    try:
        X_norm = predictor.normalize(X, fit=True)
        assert np.all(np.isfinite(X_norm)), "Normalized array contains NaN or Inf"
    except Exception as e:
        pytest.fail(f"Normalization failed with NaN/Inf: {e}")
