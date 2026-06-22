from pathlib import Path

import numpy as np
import pytest

from app.core.ml.benchmark import MLBenchmark
from app.core.ml.ensemble_predictor import EnsembleFuelPredictor, SecurityError
from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor
from app.core.ml.time_series_predictor import TimeSeriesPredictor


def test_benchmark_nan_inf_safety():
    benchmark = MLBenchmark()
    # NaN ve Inf içeren inputlar
    preds = np.array([32.0, np.nan, np.inf, 35.0])
    actuals = np.array([31.0, 32.0, 33.0, 34.0])

    results = benchmark.benchmark_prediction_accuracy("TestModel", preds, actuals)

    for r in results:
        assert np.isfinite(r.value), f"Metric {r.metric_name} is not finite: {r.value}"
        assert r.value >= 0 or r.metric_name == "R²", (
            f"Metric {r.metric_name} is negative: {r.value}"
        )


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


def test_lightgbm_margin_guard():
    predictor = LightGBMFuelPredictor()
    predictor.is_trained = True
    predictor.prediction_interval_margin_ = 0.25
    predictor.feature_importance_ = {}

    class DummyModel:
        def predict(self, X):
            return np.array([0.0])

    predictor.model = DummyModel()

    result = predictor.predict(
        {
            "mesafe_km": 120,
            "ton": 10.0,
            "ascent_m": 50,
            "descent_m": 20,
        }
    )

    assert result.prediction == 0.0
    assert result.confidence_interval == (-0.25, 0.25)


def test_time_series_normalization_nan():
    predictor = TimeSeriesPredictor()
    X = np.array([[[32.0, np.nan], [np.inf, 35.0]]])  # (1, 2, 2)
    # create_sequences gibi bir yapı yerine doğrudan normalize'ı test et
    try:
        X_norm = predictor.normalize(X, fit=True)
        assert np.all(np.isfinite(X_norm)), "Normalized array contains NaN or Inf"
    except Exception as e:
        pytest.fail(f"Normalization failed with NaN/Inf: {e}")
