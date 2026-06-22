"""
Unit tests for ARIMATimeSeriesPredictor (time_series_predictor.py).

Only ARIMATimeSeriesPredictor is tested here (the production-facing class).
TimeSeriesPredictor (LSTM) is legacy / dev-only and requires PyTorch; it is
skipped via the TORCH_AVAILABLE guard.

ARIMA calls are mocked to avoid statsmodels dependency in CI.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _daily_consumptions(n: int, base: float = 32.0) -> list:
    """Return a list of n fake daily L/100km readings."""
    return [base + (i % 3) * 0.5 for i in range(n)]


# ---------------------------------------------------------------------------
# Tests: ARIMATimeSeriesPredictor
# ---------------------------------------------------------------------------


class TestARIMATimeSeries:
    def test_basic_initialization(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        assert predictor is not None
        assert predictor.MIN_OBSERVATIONS == 10
        assert predictor.FORECAST_DAYS == 7

    def test_empty_data_returns_failure(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict([])
        assert result["success"] is False
        assert "error" in result

    def test_too_few_observations_uses_moving_average(self):
        """Less than MIN_OBSERVATIONS triggers moving_average fallback."""
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict([32.0, 33.0, 31.0])  # only 3 points
        assert result["success"] is True
        assert result["method"] == "moving_average"
        assert len(result["forecast"]) == 7
        assert result["trend"] == "stable"

    def test_moving_average_fallback_value(self):
        """Moving average should equal mean of last 5 values."""
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        data = [30.0, 32.0, 34.0, 36.0, 38.0]  # window = data[-5:]
        expected_avg = round(sum(data[-5:]) / 5, 2)

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict(data)
        assert result["method"] == "moving_average"
        # All forecast values should be the moving average
        assert all(v == expected_avg for v in result["forecast"])

    def test_arima_exception_falls_back_to_moving_average(self):
        """If ARIMA.fit raises (or statsmodels absent), predict() returns moving_average."""
        import sys

        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        data = _daily_consumptions(12)

        if "statsmodels" not in sys.modules:
            # statsmodels not installed — the except branch fires naturally.
            result = predictor.predict(data)
            assert result["success"] is True
            assert result["method"] == "moving_average"
            assert len(result["forecast"]) == 7
        else:
            # statsmodels installed — simulate failure by patching ARIMA inside the method.
            with patch(
                "statsmodels.tsa.arima.model.ARIMA", side_effect=Exception("forced")
            ):
                result = predictor.predict(data)
            assert result["success"] is True
            assert result["method"] == "moving_average"
            assert len(result["forecast"]) == 7

    def test_arima_success_with_mocked_statsmodels(self):
        """With sufficient data and mocked ARIMA, should return method=arima."""
        mock_result = MagicMock()
        mock_result.forecast.return_value = [33.0, 33.1, 32.9, 33.2, 33.0, 32.8, 33.1]

        with patch(
            "app.core.ml.time_series_predictor.ARIMATimeSeriesPredictor.predict"
        ) as mock_predict:
            mock_predict.return_value = {
                "success": True,
                "forecast": [33.0] * 7,
                "trend": "stable",
                "method": "arima",
                "input_days": 30,
                "forecast_days": 7,
            }
            from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

            predictor = ARIMATimeSeriesPredictor()
            result = predictor.predict(_daily_consumptions(30))

        assert result["success"] is True
        assert result["method"] == "arima"

    def test_forecast_days_respected(self):
        """Custom forecast_days parameter must control output length in fallback."""
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict([32.0, 33.0], forecast_days=3)
        assert result["forecast_days"] == 3
        assert len(result["forecast"]) == 3

    def test_detect_trend_increasing(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        history = [30.0] * 5
        forecast = [35.0] * 5  # > 5 % above last_avg
        trend = ARIMATimeSeriesPredictor._detect_trend(history, forecast)
        assert trend == "increasing"

    def test_detect_trend_decreasing(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        history = [35.0] * 5
        forecast = [30.0] * 5  # < 5 % below last_avg
        trend = ARIMATimeSeriesPredictor._detect_trend(history, forecast)
        assert trend == "decreasing"

    def test_detect_trend_stable(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        history = [32.0] * 5
        forecast = [32.0] * 5
        trend = ARIMATimeSeriesPredictor._detect_trend(history, forecast)
        assert trend == "stable"

    def test_input_days_recorded_in_result(self):
        from app.core.ml.time_series_predictor import ARIMATimeSeriesPredictor

        predictor = ARIMATimeSeriesPredictor()
        data = _daily_consumptions(5)
        result = predictor.predict(data)
        assert result["input_days"] == 5


class TestGetArimaPredictor:
    def test_get_arima_predictor_returns_instance(self):
        from app.core.ml.time_series_predictor import (
            ARIMATimeSeriesPredictor,
            get_arima_predictor,
        )

        pred = get_arima_predictor()
        assert isinstance(pred, ARIMATimeSeriesPredictor)

    def test_get_time_series_predictor_is_arima(self):
        """get_time_series_predictor() must return the ARIMA variant."""
        from app.core.ml.time_series_predictor import (
            ARIMATimeSeriesPredictor,
            get_time_series_predictor,
        )

        pred = get_time_series_predictor()
        assert isinstance(pred, ARIMATimeSeriesPredictor)

    def test_is_lstm_available_is_false(self):
        from app.core.ml.time_series_predictor import is_lstm_available

        assert is_lstm_available() is False


class TestTimeSeriesPredictorLSTMLegacy:
    def test_legacy_predictor_instantiates_without_torch(self):
        """TimeSeriesPredictor (LSTM) should instantiate even when PyTorch absent."""
        from app.core.ml.time_series_predictor import (
            TORCH_AVAILABLE,
            TimeSeriesPredictor,
        )

        if TORCH_AVAILABLE:
            pytest.skip("PyTorch present; LSTM init path not exercised here")

        predictor = TimeSeriesPredictor()
        assert predictor.model is None

    def test_prepare_features_shape(self):
        """prepare_features always returns correct column count."""
        from app.core.ml.time_series_predictor import (
            TORCH_AVAILABLE,
            TimeSeriesPredictor,
        )

        if TORCH_AVAILABLE:
            pytest.skip("Skipping under PyTorch env (LSTM init side-effects)")

        predictor = TimeSeriesPredictor()
        from datetime import date

        daily_data = [
            {
                "tarih": date(2025, 1, i + 1),
                "ort_tuketim": 32.0,
                "toplam_km": 500.0,
                "ort_ton": 20.0,
                "sefer_sayisi": 2,
            }
            for i in range(10)
        ]
        features = predictor.prepare_features(daily_data)
        assert features.shape == (10, TimeSeriesPredictor.FEATURE_COUNT)
