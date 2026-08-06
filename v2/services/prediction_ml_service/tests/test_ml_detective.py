"""
Split off app/tests/unit/test_ml_detective.py (missed in the original
Task 5 test-fix punch list, caught by a real CI lint run 2026-08-05):
EnsembleFuelPredictor and TimeSeriesPredictor only live in this service's
own package now. Mechanical import-path fix only, no behavioral changes.
"""

import threading

import numpy as np
from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor
from prediction_ml_service.domain.time_series_predictor import TimeSeriesPredictor


def test_ensemble_race_condition_protection():
    predictor = EnsembleFuelPredictor()
    # Dummy data for fit
    seferler = [{"mesafe_km": 100, "ton": 20}] * 20
    y = np.array([30.0] * 20)

    def train_worker():
        predictor.fit(seferler, y)

    def predict_worker():
        # Try to predict while training is running
        try:
            res = predictor.predict(seferler[0])
            # is_trained will be False during training, so this should
            # just return the physics-only prediction. The lock ensures
            # predict either waits or safely sees is_trained=False.
            assert res is not None
        except Exception as e:
            import pytest

            pytest.fail(f"Predict failed during training: {e}")

    # Start training and predicting at the same time
    t1 = threading.Thread(target=train_worker)
    t2 = threading.Thread(target=predict_worker)

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert predictor.is_trained is True


def test_time_series_padding_safety():
    predictor = TimeSeriesPredictor()
    # Only 5 days of data (needed: 30+7=37)
    short_data = [
        {
            "tarih": "2024-01-01",
            "ort_tuketim": 32.0,
            "toplam_km": 100,
            "ort_ton": 20,
            "sefer_sayisi": 2,
        }
    ] * 5

    features = predictor.prepare_features(short_data)
    targets = np.array([32.0] * 5)

    # create_sequences must not raise, must pad instead
    X, y = predictor.create_sequences(features, targets)
    assert X.shape[0] > 0
    assert X.shape[1] == predictor.SEQUENCE_LENGTH
