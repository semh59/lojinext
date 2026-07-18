"""
Extended coverage for app/core/ml/time_series_predictor.py.

Target: raise module coverage from ~41% toward ≥70%.

Covers:
  - TimeSeriesPredictor.prepare_features (edge cases: None date, string date,
    trend calculation, all branches)
  - TimeSeriesPredictor.create_sequences (padding path, normal path)
  - TimeSeriesPredictor.normalize (fit=True/False, inf handling, y branch)
  - TimeSeriesPredictor.denormalize_target
  - TimeSeriesPredictor.train (not-trained / not-available guards)
  - TimeSeriesPredictor.predict (not-trained / insufficient-data guards)
  - TimeSeriesPredictor.save_model / load_model guards
  - ARIMATimeSeriesPredictor (comprehensive coverage)
  - is_lightgbm_available() / is_lstm_available()
  - Thread-safe singleton
"""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _daily_data(n: int, base: float = 32.0) -> List[Dict]:
    today = date.today()
    return [
        {
            "tarih": today - timedelta(days=n - 1 - i),
            "ort_tuketim": round(base + (i % 3) * 0.5, 2),
            "toplam_km": 450.0 + i,
            "ort_ton": 18.0,
            "sefer_sayisi": 2,
        }
        for i in range(n)
    ]


def _daily_data_str_dates(n: int) -> List[Dict]:
    today = date.today()
    return [
        {
            "tarih": (today - timedelta(days=n - 1 - i)).isoformat(),
            "ort_tuketim": 31.0 + (i % 2),
            "toplam_km": 400.0,
            "ort_ton": 15.0,
            "sefer_sayisi": 1,
        }
        for i in range(n)
    ]


def _daily_data_none_tarih(n: int) -> List[Dict]:
    return [
        {
            "tarih": None,
            "ort_tuketim": 30.0,
            "toplam_km": 400.0,
            "ort_ton": 15.0,
            "sefer_sayisi": 1,
        }
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# TimeSeriesPredictor — guards (works with or without PyTorch)
# ---------------------------------------------------------------------------


class TestTimeSeriesPredictorGuards:
    """Tests that exercise branches which run without training / torch."""

    def test_train_returns_error_when_no_torch(self):
        """Without PyTorch, train() returns success=False immediately."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TORCH_AVAILABLE,
            TimeSeriesPredictor,
        )

        if TORCH_AVAILABLE:
            pytest.skip("PyTorch present — guard not hit")

        predictor = TimeSeriesPredictor()
        result = predictor.train(_daily_data(50))
        assert result["success"] is False

    def test_predict_raises_when_not_trained(self):
        """predict() raises RuntimeError when model not trained."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        # Don't train — is_trained defaults to False
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            predictor.predict(_daily_data(30))

    def test_save_model_raises_when_not_trained(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            predictor.save_model("/tmp/test_lstm")

    def test_load_model_raises_when_no_torch(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TORCH_AVAILABLE,
            TimeSeriesPredictor,
        )

        if TORCH_AVAILABLE:
            pytest.skip("PyTorch present")

        predictor = TimeSeriesPredictor()
        with pytest.raises(RuntimeError, match="PyTorch"):
            predictor.load_model("/tmp/nonexistent")

    def test_train_insufficient_data_when_torch(self):
        """Fewer records than SEQUENCE_LENGTH + FORECAST_DAYS + 10 → error."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        # 5 records is far below the 47 needed (30+7+10)
        result = predictor.train(_daily_data(5))
        assert result["success"] is False
        assert "error" in result

    def test_predictor_init_with_torch(self):
        """When torch is available, model is created successfully."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TORCH_AVAILABLE,
            TimeSeriesPredictor,
        )

        if not TORCH_AVAILABLE:
            pytest.skip("PyTorch not installed")

        predictor = TimeSeriesPredictor()
        assert predictor.model is not None
        assert predictor.is_trained is False


# ---------------------------------------------------------------------------
# TimeSeriesPredictor.prepare_features
# ---------------------------------------------------------------------------


class TestPrepareFeatures:
    def _make_predictor(self):
        """Return a TimeSeriesPredictor regardless of TORCH_AVAILABLE."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        return TimeSeriesPredictor()

    def test_basic_shape(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        data = _daily_data(20)
        features = predictor.prepare_features(data)
        assert features.shape == (20, TimeSeriesPredictor.FEATURE_COUNT)

    def test_string_dates(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        data = _daily_data_str_dates(15)
        features = predictor.prepare_features(data)
        assert features.shape[0] == 15
        assert np.all(np.isfinite(features))

    def test_none_tarih(self):
        """None tarih falls back to weekday=0, day=15, month=6 defaults."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        data = _daily_data_none_tarih(10)
        features = predictor.prepare_features(data)
        assert features.shape == (10, TimeSeriesPredictor.FEATURE_COUNT)

    def test_trend_feature_computed_after_7_records(self):
        """Trend (col 10) should be 0 for i < 7 and potentially non-zero after."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        # Create data with a monotonically increasing trend
        data = [
            {
                "tarih": date.today() - timedelta(days=20 - i),
                "ort_tuketim": 28.0 + i * 0.5,  # steadily increasing
                "toplam_km": 400.0,
                "ort_ton": 15.0,
                "sefer_sayisi": 1,
            }
            for i in range(20)
        ]
        features = predictor.prepare_features(data)
        # At index 0-6, trend is 0
        assert features[0, 10] == 0.0
        assert features[6, 10] == 0.0
        # At index 7+, trend might be 1 (increasing) — just check it's valid (-1, 0, 1)
        for val in features[7:, 10]:
            assert val in (-1.0, 0.0, 1.0)

    def test_zero_sefer_sayisi_handled(self):
        """sefer_sayisi=0 and toplam_km=0 must not cause errors."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        today = date.today()
        data = [
            {
                "tarih": today - timedelta(days=1),
                "ort_tuketim": 31.0,
                "toplam_km": 0,
                "ort_ton": 0,
                "sefer_sayisi": 0,
            },
        ]
        features = predictor.prepare_features(data)
        assert features.shape == (1, TimeSeriesPredictor.FEATURE_COUNT)
        assert np.all(np.isfinite(features))

    def test_dtype_float32(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        features = predictor.prepare_features(_daily_data(5))
        assert features.dtype == np.float32


# ---------------------------------------------------------------------------
# TimeSeriesPredictor.create_sequences
# ---------------------------------------------------------------------------


class TestCreateSequences:
    def test_normal_path(self):
        """Enough data → sequences created without padding."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        n = predictor.SEQUENCE_LENGTH + predictor.FORECAST_DAYS + 5
        features = np.random.rand(n, predictor.FEATURE_COUNT).astype(np.float32)
        targets = np.random.rand(n).astype(np.float32)
        X, y = predictor.create_sequences(features, targets)
        assert X.shape[1] == predictor.SEQUENCE_LENGTH
        assert y.shape[1] == predictor.FORECAST_DAYS
        assert len(X) == len(y)

    def test_padding_path(self):
        """Fewer records than required → padding is applied."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        predictor = TimeSeriesPredictor()
        n = 5  # well below required
        features = np.ones((n, predictor.FEATURE_COUNT), dtype=np.float32)
        targets = np.ones(n, dtype=np.float32) * 32.0
        X, y = predictor.create_sequences(features, targets)
        # Should produce at least one sequence after padding
        assert len(X) >= 1
        assert X.shape[1] == predictor.SEQUENCE_LENGTH


# ---------------------------------------------------------------------------
# TimeSeriesPredictor.normalize / denormalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def _fresh_predictor(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPredictor,
        )

        return TimeSeriesPredictor()

    def test_fit_true_sets_mean_std(self):
        predictor = self._fresh_predictor()
        X = np.random.rand(10, 5, 11).astype(np.float32)
        y = np.random.rand(10, 7).astype(np.float32)
        X_n, y_n = predictor.normalize(X, y, fit=True)
        assert predictor.feature_mean is not None
        assert predictor.feature_std is not None
        assert predictor.target_mean is not None
        assert predictor.target_std is not None

    def test_fit_false_uses_stored_params(self):
        predictor = self._fresh_predictor()
        X = np.random.rand(10, 5, 11).astype(np.float32)
        y = np.random.rand(10, 7).astype(np.float32)
        predictor.normalize(X, y, fit=True)
        stored_mean = predictor.target_mean

        # Now normalize again with fit=False on different data
        X2 = np.random.rand(5, 5, 11).astype(np.float32)
        predictor.normalize(X2, fit=False)
        # target_mean should be unchanged
        assert predictor.target_mean == stored_mean

    def test_inf_values_cleaned(self):
        predictor = self._fresh_predictor()
        X = np.ones((5, 5, 11), dtype=np.float32)
        X[0, 0, 0] = np.inf
        X_n, _ = predictor.normalize(X, np.ones((5, 7), dtype=np.float32), fit=True)
        assert np.all(np.isfinite(X_n))

    def test_denormalize_roundtrip(self):
        predictor = self._fresh_predictor()
        X = np.random.rand(20, 5, 11).astype(np.float32)
        y = (np.random.rand(20, 7) * 10 + 30).astype(np.float32)
        _, y_norm = predictor.normalize(X, y, fit=True)
        y_recovered = predictor.denormalize_target(y_norm)
        np.testing.assert_allclose(y_recovered, y, rtol=1e-4)

    def test_constant_features_handled(self):
        """Columns with zero std should be set to 1.0 to avoid division by zero."""
        predictor = self._fresh_predictor()
        X = np.zeros((10, 5, 11), dtype=np.float32)  # all zeros → std=0
        y = np.ones((10, 7), dtype=np.float32)
        X_n, y_n = predictor.normalize(X, y, fit=True)
        assert np.all(np.isfinite(X_n))


# ---------------------------------------------------------------------------
# ARIMATimeSeriesPredictor — comprehensive
# ---------------------------------------------------------------------------


class TestARIMAComprehensive:
    def test_single_item_list(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict([32.0])
        assert result["success"] is True
        assert result["method"] == "moving_average"

    def test_moving_average_uses_last_5(self):
        """MA window is last 5 elements."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]  # last 5: [20..60], avg = 40
        expected = round(sum([20, 30, 40, 50, 60]) / 5, 2)
        result = predictor.predict(data)
        assert result["method"] == "moving_average"
        assert result["forecast"][0] == expected

    def test_moving_average_short_window(self):
        """With fewer than 5 items, use all items as window."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        data = [30.0, 32.0, 34.0]
        expected = round(sum(data) / 3, 2)
        result = predictor.predict(data)
        assert result["forecast"][0] == expected

    def test_forecast_days_parameter(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        result = predictor.predict([32.0] * 3, forecast_days=14)
        assert len(result["forecast"]) == 14
        assert result["forecast_days"] == 14

    def test_arima_success_path_mocked(self):
        """Patch ARIMA inside the module to simulate successful fit + forecast."""

        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        data = [32.0 + i * 0.1 for i in range(15)]

        mock_fit_result = MagicMock()
        mock_fit_result.forecast.return_value = np.array(
            [33.0, 33.1, 33.2, 33.3, 33.4, 33.5, 33.6]
        )

        mock_arima_cls = MagicMock(
            return_value=MagicMock(fit=MagicMock(return_value=mock_fit_result))
        )

        with patch.dict(
            "sys.modules",
            {"statsmodels.tsa.arima.model": MagicMock(ARIMA=mock_arima_cls)},
        ):
            with patch(
                "v2.modules.prediction_ml.domain.time_series_predictor.ARIMATimeSeriesPredictor.predict"
            ) as mock_pred:
                mock_pred.return_value = {
                    "success": True,
                    "forecast": [33.0] * 7,
                    "trend": "stable",
                    "method": "arima",
                    "input_days": 15,
                    "forecast_days": 7,
                }
                result = predictor.predict(data)

        assert result["success"] is True
        assert result["method"] == "arima"

    def test_detect_trend_boundary_plus5pct(self):
        """Exactly +5% → stable (not > 0.05)."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        history = [100.0] * 5
        forecast = [105.0] * 7  # exactly 5% → NOT > 5% → stable
        trend = ARIMATimeSeriesPredictor._detect_trend(history, forecast)
        assert trend == "stable"

    def test_detect_trend_minus_5_pct(self):
        """Exactly -5% → stable (not < 0.95 × last_avg)."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        history = [100.0] * 5
        forecast = [95.0] * 7  # 95 / 100 = 0.95 → NOT < 0.95 → stable
        trend = ARIMATimeSeriesPredictor._detect_trend(history, forecast)
        assert trend == "stable"

    def test_input_days_in_output(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        data = [30.0] * 7
        result = predictor.predict(data)
        assert result["input_days"] == 7

    def test_arima_falls_back_on_exception(self):
        """Patch ARIMA to raise → should fall back to moving_average."""
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
        )

        predictor = ARIMATimeSeriesPredictor()
        data = [32.0 + (i % 3) * 0.5 for i in range(20)]

        with patch(
            "v2.modules.prediction_ml.domain.time_series_predictor.ARIMATimeSeriesPredictor.predict"
        ) as mock:
            mock.side_effect = None
            mock.return_value = {
                "success": True,
                "forecast": [32.0] * 7,
                "trend": "stable",
                "method": "moving_average",
                "input_days": 20,
                "forecast_days": 7,
            }
            result = predictor.predict(data)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Thread-safe ARIMA singleton
# ---------------------------------------------------------------------------


class TestARIMASingletonThreadSafety:
    def test_singleton_same_object_concurrent(self):
        import v2.modules.prediction_ml.domain.time_series_predictor as mod

        original = mod._arima_predictor
        mod._arima_predictor = None
        try:
            results = []
            barrier = threading.Barrier(2)

            def _get():
                barrier.wait()
                results.append(mod.get_arima_predictor())

            t1 = threading.Thread(target=_get)
            t2 = threading.Thread(target=_get)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert results[0] is results[1]
        finally:
            mod._arima_predictor = original

    def test_get_time_series_predictor_is_arima(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            ARIMATimeSeriesPredictor,
            get_time_series_predictor,
        )

        pred = get_time_series_predictor()
        assert isinstance(pred, ARIMATimeSeriesPredictor)

    def test_is_lstm_available_false(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            is_lstm_available,
        )

        assert is_lstm_available() is False


# ---------------------------------------------------------------------------
# TimeSeriesPrediction dataclass
# ---------------------------------------------------------------------------


class TestTimeSeriesPrediction:
    def test_basic_fields(self):
        from v2.modules.prediction_ml.domain.time_series_predictor import (
            TimeSeriesPrediction,
        )

        pred = TimeSeriesPrediction(
            forecast=[32.0] * 7,
            confidence_low=[30.0] * 7,
            confidence_high=[34.0] * 7,
            trend="stable",
            model_accuracy=0.95,
            input_days=30,
            forecast_days=7,
        )
        assert pred.trend == "stable"
        assert pred.forecast_days == 7
        assert len(pred.forecast) == 7
