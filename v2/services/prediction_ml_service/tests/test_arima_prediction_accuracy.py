"""
Split off app/tests/unit/test_prediction_accuracy.py (missed in the
original Task 5 test-fix punch list, caught by a real CI lint run
2026-08-05): ARIMATimeSeriesPredictor only lives in this service's own
package now. Mechanical import-path fix only, no behavioral changes.

ML prediction accuracy regression tests: these validate expected output
ranges for known inputs. A weight change or feature-engineering
regression should break these.
"""

import pytest
from prediction_ml_service.domain.time_series_predictor import (
    ARIMATimeSeriesPredictor,
)


class TestARIMATimeSeriesPredictorAccuracy:
    @pytest.fixture
    def predictor(self):
        return ARIMATimeSeriesPredictor()

    def test_sufficient_data_returns_success(self, predictor):
        data = [32.0 + (i % 3) for i in range(20)]
        result = predictor.predict(data)
        assert result["success"] is True
        assert "forecast" in result
        assert len(result["forecast"]) == 7

    def test_insufficient_data_uses_moving_average(self, predictor):
        data = [35.0, 36.0, 34.0]
        result = predictor.predict(data)
        assert result["success"] is True
        assert result["method"] == "moving_average"
        assert all(v > 0 for v in result["forecast"])

    def test_empty_data_returns_failure(self, predictor):
        result = predictor.predict([])
        assert result["success"] is False

    def test_stable_series_predicts_stable_trend(self, predictor):
        data = [32.0] * 15
        result = predictor.predict(data)
        assert result["success"] is True
        for v in result["forecast"]:
            assert 28.0 <= v <= 36.0, f"Prediction too far from a stable series: {v}"

    def test_rising_series_detects_increasing_trend(self, predictor):
        data = [30.0 + i * 0.5 for i in range(20)]
        result = predictor.predict(data)
        assert result["success"] is True
        assert result["trend"] in ("increasing", "stable")

    def test_custom_forecast_days(self, predictor):
        data = [32.0] * 15
        result = predictor.predict(data, forecast_days=14)
        assert result["forecast_days"] == 14
        assert len(result["forecast"]) == 14
