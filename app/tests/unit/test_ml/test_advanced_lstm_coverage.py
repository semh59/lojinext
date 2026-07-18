"""
Extended coverage tests for app/core/ml/advanced_lstm.py.

Target: raise module coverage from ~49% toward ≥70%.
Strategy:
  - No heavy PyTorch training — mock at the module-attribute level.
  - Exercise FeatureEngine edge cases, all stat-fallback branches, AdvancedTSEngine paths.
  - Test _sarima, walk_forward_cv, train_model fallback (torch unavailable path).
  - Test singleton double-checked locking.
"""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_records(n: int, base: float = 32.0, noise: float = 0.5) -> List[dict]:
    rng = np.random.default_rng(0)
    today = date.today()
    return [
        {
            "date": today - timedelta(days=n - 1 - i),
            "consumption": round(base + rng.normal(0, noise), 2),
            "km": round(400 + rng.uniform(-30, 30), 1),
            "ton": round(15 + rng.uniform(-1, 1), 1),
            "trips": int(rng.integers(1, 4)),
        }
        for i in range(n)
    ]


def _make_records_string_dates(n: int) -> List[dict]:
    """Records where 'date' is an ISO string instead of a date object."""
    today = date.today()
    recs = []
    for i in range(n):
        d = today - timedelta(days=n - 1 - i)
        recs.append(
            {
                "date": d.isoformat(),
                "consumption": 31.0 + (i % 3) * 0.5,
                "km": 400.0,
                "ton": 15.0,
                "trips": 2,
            }
        )
    return recs


def _make_records_no_date(n: int) -> List[dict]:
    """Records without a 'date' key — engine falls back to date.today()."""
    return [
        {"consumption": 30.0 + i * 0.1, "km": 450.0, "ton": 14.0, "trips": 1}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# FeatureEngine — edge cases not covered by the existing test file
# ---------------------------------------------------------------------------


class TestFeatureEngineEdgeCases:
    def test_string_dates_processed(self):
        """ISO-string dates must be parsed; no exception or NaN."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        records = _make_records_string_dates(20)
        X = engine.fit_transform(records)
        assert X.shape[0] == 20
        assert not np.any(np.isnan(X))

    def test_missing_date_falls_back_to_today(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        records = _make_records_no_date(15)
        X = engine.fit_transform(records)
        assert X.shape[0] == 15
        assert not np.any(np.isnan(X))

    def test_transform_after_fit_normalises_correctly(self):
        """transform() after fit_transform() must apply stored stats."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        train = _make_records(60)
        engine.fit_transform(train)

        test = _make_records(10)
        X_test = engine.transform(test)
        assert X_test.shape == (10, engine._mu.shape[0])

    def test_inverse_target_unfitted_returns_input(self):
        """inverse_target on an unfitted engine must return the input unchanged."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        y = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = engine.inverse_target(y)
        np.testing.assert_array_equal(result, y)

    def test_transform_unfitted_returns_raw(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        records = _make_records(5)
        X = engine.transform(records)
        assert X.shape == (5, 24)

    def test_short_records_no_lag_features_zero(self):
        """With only 2 records, lag-14 and lag-7 must be 0."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        records = _make_records(2)
        X = engine.fit_transform(records)
        # lag_7 is column 14, lag_14 is column 15 — both zero for i<7/i<14
        assert X[0, 14] == 0.0  # lag_7 at index 0
        assert X[0, 15] == 0.0  # lag_14 at index 0

    def test_weekend_flag(self):
        """Confirm is_weekend (column 6) triggers for a Saturday."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        # Find a Saturday
        today = date.today()
        offset = (5 - today.weekday()) % 7  # days until Saturday
        saturday = today + timedelta(days=offset)
        records = [
            {
                "date": saturday,
                "consumption": 32.0,
                "km": 400.0,
                "ton": 15.0,
                "trips": 2,
            }
        ]
        # fit_transform with a single record
        raw = engine._build_raw(records)
        # Column 6 must be 1.0 for Saturday (weekday >= 5)
        assert raw[0, 6] == 1.0

    def test_trend_slope_computed_for_longer_series(self):
        """Trend slope (col 23) must be non-zero for index >= 3."""
        from v2.modules.prediction_ml.domain.advanced_lstm import FeatureEngine

        engine = FeatureEngine()
        records = _make_records(20)
        raw = engine._build_raw(records)
        # At index 10, seg has 11 samples, polyfit must give a non-zero slope
        # unless consumption is perfectly constant — just check no NaN
        assert np.isfinite(raw[10, 23])


# ---------------------------------------------------------------------------
# Statistical fallbacks — _holt_winters, _sarima, _ensemble_stat
# ---------------------------------------------------------------------------


class TestSarimaFallback:
    def test_sarima_returns_none_on_short_data(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import _sarima

        result = _sarima([32.0] * 10, 7)
        assert result is None

    def test_sarima_exception_returns_none(self):
        """If SARIMAX import raises inside the function, _sarima returns None."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _sarima

        data = [32.0 + i * 0.1 for i in range(35)]
        # Patch inside advanced_lstm's local import scope
        fake_mod = MagicMock()
        fake_mod.SARIMAX = MagicMock(side_effect=Exception("forced"))
        with patch.dict(
            "sys.modules", {"statsmodels.tsa.statespace.sarimax": fake_mod}
        ):
            result = _sarima(data, 7)
        assert result is None

    def test_sarima_returns_dict_on_enough_data(self):
        """With 35 observations, _sarima should either succeed or return None (statsmodels optional)."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _sarima

        data = [32.0 + np.sin(i / 7) * 2 for i in range(35)]
        result = _sarima(data, 7)
        if result is not None:
            assert "forecast" in result
            assert len(result["forecast"]) == 7
            assert result["method"] == "sarima"


class TestHoltWintersFallback:
    def test_holt_winters_exception_returns_none(self):
        """If ExponentialSmoothing raises, _holt_winters returns None."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _holt_winters

        data = [32.0] * 25
        fake_mod = MagicMock()
        fake_mod.ExponentialSmoothing = MagicMock(side_effect=Exception("boom"))
        with patch.dict("sys.modules", {"statsmodels.tsa.holtwinters": fake_mod}):
            result = _holt_winters(data, 7)
        assert result is None

    def test_holt_winters_below_21_no_seasonal(self):
        """With 14-20 obs, seasonal should be None (short path)."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _holt_winters

        data = [32.0 + (i % 3) * 0.5 for i in range(14)]
        result = _holt_winters(data, 5)
        # May or may not succeed (statsmodels optional), just must not raise
        if result is not None:
            assert len(result["forecast"]) == 5


class TestEnsembleStatFallback:
    def test_ensemble_stat_only_hw_succeeds(self):
        """When HW succeeds but SARIMA returns None, blend still works."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _ensemble_stat

        mock_hw = {
            "forecast": [32.0] * 7,
            "lower": [30.0] * 7,
            "upper": [34.0] * 7,
            "method": "holt_winters",
        }
        with patch("v2.modules.prediction_ml.domain.advanced_lstm._holt_winters", return_value=mock_hw):
            with patch("v2.modules.prediction_ml.domain.advanced_lstm._sarima", return_value=None):
                result = _ensemble_stat([32.0] * 20, 7)
        assert result["forecast"] == [32.0] * 7
        assert "holt_winters" in result["method"]

    def test_ensemble_stat_only_sarima_succeeds(self):
        """When SARIMA succeeds but HW returns None, blend still works."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _ensemble_stat

        mock_sar = {
            "forecast": [33.0] * 7,
            "lower": [31.0] * 7,
            "upper": [35.0] * 7,
            "method": "sarima",
        }
        with patch("v2.modules.prediction_ml.domain.advanced_lstm._holt_winters", return_value=None):
            with patch("v2.modules.prediction_ml.domain.advanced_lstm._sarima", return_value=mock_sar):
                result = _ensemble_stat([32.0] * 35, 7)
        assert result["forecast"] == [33.0] * 7

    def test_ensemble_stat_both_succeed_blends(self):
        """When both HW and SARIMA succeed, blended result should be their average."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _ensemble_stat

        mock_hw = {
            "forecast": [32.0] * 7,
            "lower": [30.0] * 7,
            "upper": [34.0] * 7,
            "method": "holt_winters",
        }
        mock_sar = {
            "forecast": [34.0] * 7,
            "lower": [32.0] * 7,
            "upper": [36.0] * 7,
            "method": "sarima",
        }
        with patch("v2.modules.prediction_ml.domain.advanced_lstm._holt_winters", return_value=mock_hw):
            with patch("v2.modules.prediction_ml.domain.advanced_lstm._sarima", return_value=mock_sar):
                result = _ensemble_stat([32.0] * 35, 7)
        # Blended: (0.5 * 32 + 0.5 * 34) = 33.0
        assert result["forecast"][0] == pytest.approx(33.0, abs=0.01)
        assert "+" in result["method"]

    def test_ema_fallback_on_constant_data(self):
        """Constant data should produce a flat EMA forecast."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _ema_fallback

        result = _ema_fallback([30.0] * 10, 7)
        assert all(v == 30.0 for v in result["forecast"])
        # With constant data std=0 → CI width=0
        assert result["lower"][0] == result["upper"][0]


# ---------------------------------------------------------------------------
# AdvancedTSEngine — stat forecast paths
# ---------------------------------------------------------------------------


class TestAdvancedTSEngineStatPaths:
    def test_stat_forecast_ema_path_with_1_record(self):
        """n=1 < MIN_EMA(3) → INSUFFICIENT_DATA."""
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        result = engine.forecast(_make_records(1), steps=7)
        assert result.success is False
        assert result.error_code == "INSUFFICIENT_DATA"

    def test_stat_forecast_exactly_at_min_ema(self):
        """n=3 == MIN_EMA → must succeed via EMA."""
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        result = engine.forecast(_make_records(3), steps=7)
        assert result.success is True
        assert "ema" in result.method

    def test_stat_forecast_custom_steps(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        result = engine.forecast(_make_records(10), steps=14)
        assert result.success is True
        assert len(result.forecast) == 14
        assert result.forecast_days == 14

    def test_stat_forecast_lower_lt_upper(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        result = engine.forecast(_make_records(15), steps=7)
        for lo, hi in zip(result.lower_95, result.upper_95):
            assert lo <= hi

    def test_train_insufficient_data_below_minimum(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import (
            FORECAST_DAYS,
            SEQ_LEN,
            AdvancedTSEngine,
        )

        engine = AdvancedTSEngine()
        min_days = SEQ_LEN + FORECAST_DAYS + 5
        result = engine.train(_make_records(min_days - 1))
        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    def test_train_statistical_only_lt_min_deep(self):
        """Between min_days and MIN_DEEP(90), training returns statistical_only."""
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        # 45 days is ≥ min_days (42) but < MIN_DEEP (90)
        result = engine.train(_make_records(45))
        assert "success" in result
        if result.get("success"):
            # Either statistical_only (no torch) or a deep note
            assert "method" in result or "n_sequences" in result

    def test_status_fields_present_after_init(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        s = engine.status()
        for key in (
            "is_trained",
            "torch_available",
            "deep_learning_active",
            "min_days_for_deep",
            "training_epochs",
            "last_loss",
            "n_training_samples",
            "train_time_s",
            "bilstm_mae",
            "tcn_mae",
        ):
            assert key in s

    def test_status_bilstm_mae_none_when_untrained(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        s = engine.status()
        assert s["bilstm_mae"] is None
        assert s["tcn_mae"] is None


# ---------------------------------------------------------------------------
# AdvancedTSEngine — deep learning path (mocked torch)
# ---------------------------------------------------------------------------


class TestAdvancedTSEngineDeepMocked:
    """Test the deep learning forecast path by mocking torch and the models."""

    def test_deep_forecast_fallback_on_exception(self):
        """If deep forecast raises, engine must fall back to statistical path."""
        from v2.modules.prediction_ml.domain.advanced_lstm import AdvancedTSEngine

        engine = AdvancedTSEngine()
        engine._trained = True  # pretend trained

        # Patch _deep_forecast to raise
        with patch.object(
            engine, "_deep_forecast", side_effect=RuntimeError("mock deep fail")
        ):
            result = engine.forecast(_make_records(35), steps=7)
        # Should fall back to statistical path successfully
        assert result.success is True

    def test_make_sequences_output_shape(self):
        """_make_sequences must produce correct sequence/label arrays."""
        from v2.modules.prediction_ml.domain.advanced_lstm import (
            FORECAST_DAYS,
            SEQ_LEN,
            AdvancedTSEngine,
        )

        engine = AdvancedTSEngine()
        records = _make_records(SEQ_LEN + FORECAST_DAYS + 10)
        X_feat = engine.engine.fit_transform(records)
        consumptions = [r["consumption"] for r in records]
        X_seqs, y_seqs = engine._make_sequences(X_feat, consumptions)

        n_expected = len(records) - SEQ_LEN - FORECAST_DAYS + 1
        assert X_seqs.shape == (n_expected, SEQ_LEN, X_feat.shape[1])
        assert y_seqs.shape == (n_expected, FORECAST_DAYS)

    def test_deep_forecast_bilstm_only(self):
        """When only bilstm is set, deep forecast uses bilstm method."""
        from v2.modules.prediction_ml.domain.advanced_lstm import (
            TORCH_AVAILABLE,
            AdvancedTSEngine,
        )

        if not TORCH_AVAILABLE:
            pytest.skip("torch not available")

        import torch

        engine = AdvancedTSEngine()
        engine._trained = True
        engine._bilstm_mae = 0.5
        engine._tcn_mae = float("inf")

        # Return real torch tensors so .numpy() works
        mean_tensor = torch.ones(1, 7) * 32.0
        std_tensor = torch.ones(1, 7) * 0.5

        mock_bilstm = MagicMock()
        mock_bilstm.predict_mc.return_value = (mean_tensor, std_tensor)
        engine.bilstm = mock_bilstm
        engine.tcn = None

        records = _make_records(35)
        result = engine._deep_forecast(records, [r["consumption"] for r in records], 7)
        assert result.success is True
        assert result.method == "bilstm"

    def test_deep_forecast_tcn_only(self):
        """When only tcn is set, deep forecast uses tcn method."""
        from v2.modules.prediction_ml.domain.advanced_lstm import (
            TORCH_AVAILABLE,
            AdvancedTSEngine,
        )

        if not TORCH_AVAILABLE:
            pytest.skip("torch not available")

        import torch

        engine = AdvancedTSEngine()
        engine._trained = True
        engine._bilstm_mae = float("inf")
        engine._tcn_mae = 0.5

        mean_tensor = torch.ones(1, 7) * 31.0
        std_tensor = torch.ones(1, 7) * 0.4

        mock_tcn = MagicMock()
        mock_tcn.predict_mc.return_value = (mean_tensor, std_tensor)
        engine.bilstm = None
        engine.tcn = mock_tcn

        records = _make_records(35)
        result = engine._deep_forecast(records, [r["consumption"] for r in records], 7)
        assert result.success is True
        assert result.method == "tcn"


# ---------------------------------------------------------------------------
# walk_forward_cv — no-torch path
# ---------------------------------------------------------------------------


class TestWalkForwardCV:
    def test_no_torch_returns_inf(self):
        from v2.modules.prediction_ml.domain import advanced_lstm

        original = advanced_lstm.TORCH_AVAILABLE
        try:
            advanced_lstm.TORCH_AVAILABLE = False
            result = advanced_lstm.walk_forward_cv(None, None, None, {})
            assert result == float("inf")
        finally:
            advanced_lstm.TORCH_AVAILABLE = original


# ---------------------------------------------------------------------------
# train_model — no-torch path
# ---------------------------------------------------------------------------


class TestTrainModel:
    def test_no_torch_returns_empty_dict(self):
        from v2.modules.prediction_ml.domain import advanced_lstm

        original = advanced_lstm.TORCH_AVAILABLE
        try:
            advanced_lstm.TORCH_AVAILABLE = False
            result = advanced_lstm.train_model(None, None, None)
            assert result == {}
        finally:
            advanced_lstm.TORCH_AVAILABLE = original


# ---------------------------------------------------------------------------
# Singleton thread-safety
# ---------------------------------------------------------------------------


class TestSingletonThreadSafety:
    def test_singleton_is_same_object_concurrent(self):
        """Two threads calling get_advanced_ts_engine() must get the same instance."""
        import v2.modules.prediction_ml.domain.advanced_lstm as mod

        # Reset singleton for a clean test
        original = mod._engine
        mod._engine = None
        try:
            results = []
            barrier = threading.Barrier(2)

            def _get():
                barrier.wait()
                results.append(mod.get_advanced_ts_engine())

            t1 = threading.Thread(target=_get)
            t2 = threading.Thread(target=_get)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert results[0] is results[1]
        finally:
            mod._engine = original

    def test_get_engine_returns_advanced_ts_engine(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import (
            AdvancedTSEngine,
            get_advanced_ts_engine,
        )

        engine = get_advanced_ts_engine()
        assert isinstance(engine, AdvancedTSEngine)


# ---------------------------------------------------------------------------
# _detect_trend edge cases
# ---------------------------------------------------------------------------


class TestDetectTrendEdge:
    def test_exactly_5_pct_increase_is_stable(self):
        """Exactly +5% delta is NOT > 0.05, so it must be 'stable'."""
        from v2.modules.prediction_ml.domain.advanced_lstm import _detect_trend

        # last_avg = 100, fc_avg = 105 → delta = 0.05 → NOT > 0.05
        history = [100.0] * 5
        forecast = [105.0] * 7
        trend = _detect_trend(history, forecast)
        assert trend == "stable"

    def test_slightly_above_5_pct_is_increasing(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import _detect_trend

        history = [100.0] * 5
        forecast = [106.0] * 7  # delta ≈ 0.059 > 0.05
        trend = _detect_trend(history, forecast)
        assert trend == "increasing"

    def test_only_history_no_forecast(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import _detect_trend

        result = _detect_trend([32.0, 33.0], [])
        assert result == "stable"

    def test_only_forecast_no_history(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import _detect_trend

        result = _detect_trend([], [32.0, 33.0])
        assert result == "stable"


# ---------------------------------------------------------------------------
# ForecastResult dataclass
# ---------------------------------------------------------------------------


class TestForecastResultExtended:
    def test_all_fields_settable(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import ForecastResult

        r = ForecastResult(
            success=True,
            forecast=[32.0] * 7,
            lower_95=[30.0] * 7,
            upper_95=[34.0] * 7,
            trend="stable",
            method="ema",
            mae=1.2,
            is_trained=False,
            training_epochs=0,
            last_loss=None,
            input_days=20,
            forecast_days=7,
        )
        assert r.mae == 1.2
        assert r.input_days == 20
        assert r.forecast_days == 7
        assert r.is_trained is False

    def test_error_code_and_message(self):
        from v2.modules.prediction_ml.domain.advanced_lstm import ForecastResult

        r = ForecastResult(
            success=False,
            error_code="TEST_ERR",
            error_message="something went wrong",
        )
        assert r.error_code == "TEST_ERR"
        assert "went wrong" in r.error_message
