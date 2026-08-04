import pytest

from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

pytestmark = pytest.mark.unit


def _make_seferler(n=20):
    return [
        {
            "tuketim": 30.0 + (i % 5),
            "tarih": f"2026-0{1 + i % 6}-15",
            "mesafe_km": 200.0 + i * 10,
            "ton": 18.0,
        }
        for i in range(n)
    ]


def test_fit_returns_success_shape_before_and_after_split():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(20))

    assert result["success"] is True
    assert "sample_count" in result
    assert "ensemble_r2" in result
    assert "measurements" in result
    assert set(result["measurements"].keys()) == {"mae", "rmse", "mape", "physics_mae"}
    assert "metrics" in result
    assert "feature_importance" in result
    assert "model_weights" in result
    assert "is_honest_test" in result
    assert predictor.is_trained is True


def test_fit_insufficient_data_returns_error():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(3))

    assert result["success"] is False
    assert "Yetersiz veri" in result["error"]
