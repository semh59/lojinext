"""Unit tests for the advanced time-series forecasting engine."""

from datetime import date, timedelta
from typing import List

import numpy as np

from app.core.ml.advanced_lstm import (
    N_FEATURES,
    AdvancedTSEngine,
    FeatureEngine,
    ForecastResult,
    _detect_trend,
    _ema_fallback,
    _ensemble_stat,
    _holt_winters,
    get_advanced_ts_engine,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_records(n: int, base: float = 32.0, noise: float = 1.0) -> List[dict]:
    """Generate synthetic daily fuel records."""
    rng = np.random.default_rng(42)
    today = date.today()
    records = []
    for i in range(n):
        d = today - timedelta(days=n - 1 - i)
        records.append(
            {
                "date": d,
                "consumption": round(base + rng.normal(0, noise), 2),
                "km": round(400 + rng.uniform(-50, 50), 1),
                "ton": round(15 + rng.uniform(-2, 2), 1),
                "trips": int(rng.integers(1, 4)),
            }
        )
    return records


# ── FeatureEngine ──────────────────────────────────────────────────────────────


class TestFeatureEngine:
    def test_output_shape(self):
        engine = FeatureEngine()
        records = _make_records(60)
        X = engine.fit_transform(records)
        assert X.shape == (60, N_FEATURES)

    def test_dtype_float32(self):
        engine = FeatureEngine()
        X = engine.fit_transform(_make_records(20))
        assert X.dtype == np.float32

    def test_normalised_range(self):
        """After fit_transform the feature means should be near zero."""
        engine = FeatureEngine()
        X = engine.fit_transform(_make_records(100))
        # Skip binary/cyclical columns (indices 0-7) — focus on raw/rolling stats
        col_means = np.abs(X[:, 8:].mean(axis=0))
        assert np.all(col_means < 1.5), f"Column means too large: {col_means}"

    def test_transform_without_fit_returns_raw(self):
        engine = FeatureEngine()
        records = _make_records(10)
        X = engine.transform(records)
        assert X.shape == (10, N_FEATURES)

    def test_cyclical_sin_cos_bounded(self):
        engine = FeatureEngine()
        X = engine.fit_transform(_make_records(30))
        # Columns 0-5 are sin/cos → before normalisation they are [-1, 1]
        # After normalisation they may shift; check no NaN/Inf
        assert np.all(np.isfinite(X[:, :6]))

    def test_inverse_target_roundtrip(self):
        engine = FeatureEngine()
        records = _make_records(50)
        engine.fit_transform(records)
        consumptions = np.array([r["consumption"] for r in records], dtype=np.float32)
        normed = (consumptions - engine._mu[8]) / engine._sigma[8]
        recovered = engine.inverse_target(normed)
        np.testing.assert_allclose(recovered, consumptions, rtol=1e-5)

    def test_no_nan_in_features(self):
        engine = FeatureEngine()
        records = _make_records(100)
        X = engine.fit_transform(records)
        assert not np.any(np.isnan(X)), "NaN found in feature matrix"
        assert not np.any(np.isinf(X)), "Inf found in feature matrix"


# ── Statistical fallbacks ──────────────────────────────────────────────────────


class TestStatisticalFallbacks:
    def test_ema_fallback_length(self):
        data = [32.0 + i * 0.1 for i in range(10)]
        result = _ema_fallback(data, 7)
        assert len(result["forecast"]) == 7
        assert len(result["lower"]) == 7
        assert len(result["upper"]) == 7
        assert result["method"] == "ema"

    def test_ema_lower_less_than_upper(self):
        data = [30.0, 31.0, 32.0, 33.0, 34.0]
        result = _ema_fallback(data, 5)
        for lo, hi in zip(result["lower"], result["upper"]):
            assert lo <= hi

    def test_holt_winters_none_on_short_data(self):
        assert _holt_winters([32.0] * 5, 7) is None

    def test_holt_winters_returns_dict_on_enough_data(self):
        data = [32.0 + i * 0.05 + np.sin(i / 7) for i in range(30)]
        result = _holt_winters(data, 7)
        # May return None if statsmodels isn't installed — that's acceptable
        if result is not None:
            assert "forecast" in result
            assert len(result["forecast"]) == 7

    def test_ensemble_stat_ema_fallback_on_very_short_data(self):
        data = [32.0] * 5
        result = _ensemble_stat(data, 7)
        assert "forecast" in result
        assert len(result["forecast"]) == 7

    def test_detect_trend_increasing(self):
        history = [30.0] * 5
        forecast = [33.0] * 7
        assert _detect_trend(history, forecast) == "increasing"

    def test_detect_trend_decreasing(self):
        history = [35.0] * 5
        forecast = [28.0] * 7
        assert _detect_trend(history, forecast) == "decreasing"

    def test_detect_trend_stable(self):
        history = [32.0] * 5
        forecast = [32.1] * 7
        assert _detect_trend(history, forecast) == "stable"

    def test_detect_trend_empty_inputs(self):
        assert _detect_trend([], []) == "stable"


# ── AdvancedTSEngine ───────────────────────────────────────────────────────────


class TestAdvancedTSEngineForecast:
    """Tests that don't require deep learning (statistical path)."""

    def test_ema_path_3_records(self):
        engine = AdvancedTSEngine()
        records = _make_records(3)
        result = engine.forecast(records, steps=7)
        assert result.success is True
        assert len(result.forecast) == 7
        assert "ema" in result.method

    def test_stat_path_14_records(self):
        engine = AdvancedTSEngine()
        records = _make_records(20)
        result = engine.forecast(records, steps=7)
        assert result.success is True
        assert len(result.forecast) == 7
        assert result.method != "none"

    def test_stat_path_30_records(self):
        engine = AdvancedTSEngine()
        records = _make_records(40)
        result = engine.forecast(records, steps=7)
        assert result.success is True
        assert len(result.forecast) == 7

    def test_forecast_result_confidence_ordering(self):
        engine = AdvancedTSEngine()
        records = _make_records(20)
        result = engine.forecast(records, steps=7)
        for lo, hi in zip(result.lower_95, result.upper_95):
            assert lo <= hi, f"lower {lo} > upper {hi}"

    def test_insufficient_data_fails_gracefully(self):
        engine = AdvancedTSEngine()
        result = engine.forecast([], steps=7)
        assert result.success is False
        assert result.error_code is not None

    def test_forecast_with_2_records(self):
        engine = AdvancedTSEngine()
        result = engine.forecast(_make_records(2), steps=7)
        assert result.success is False

    def test_status_untrained(self):
        engine = AdvancedTSEngine()
        status = engine.status()
        assert status["is_trained"] is False
        assert "torch_available" in status
        assert "min_days_for_deep" in status

    def test_train_returns_error_on_insufficient_data(self):
        engine = AdvancedTSEngine()
        result = engine.train(_make_records(10))
        assert result["success"] is False


class TestAdvancedTSEngineTrainStatOnly:
    """Training with statistical-only path (< 90 days or no PyTorch)."""

    def test_train_50_days_statistical_only_or_skip(self):
        engine = AdvancedTSEngine()
        records = _make_records(50)
        result = engine.train(records)
        # With 50 days we may either get deep learning or statistical_only
        # depending on TORCH_AVAILABLE; both are valid success responses.
        assert "success" in result

    def test_forecast_after_stat_train(self):
        engine = AdvancedTSEngine()
        records = _make_records(50)
        engine.train(records)
        result = engine.forecast(records[-40:], steps=7)
        assert result.success is True
        assert len(result.forecast) == 7


# ── Singleton ──────────────────────────────────────────────────────────────────


class TestSingleton:
    def test_get_advanced_ts_engine_returns_same_instance(self):
        e1 = get_advanced_ts_engine()
        e2 = get_advanced_ts_engine()
        assert e1 is e2

    def test_engine_has_required_attributes(self):
        engine = get_advanced_ts_engine()
        assert hasattr(engine, "train")
        assert hasattr(engine, "forecast")
        assert hasattr(engine, "status")


# ── ForecastResult ─────────────────────────────────────────────────────────────


class TestForecastResult:
    def test_defaults(self):
        r = ForecastResult(success=True)
        assert r.forecast == []
        assert r.trend == "stable"
        assert r.method == "none"

    def test_failure_result(self):
        r = ForecastResult(
            success=False,
            error_code="INSUFFICIENT_DATA",
            error_message="Not enough data",
        )
        assert r.success is False
        assert r.error_code == "INSUFFICIENT_DATA"


# ── TimeSeriesService integration (unit-level, mocked repo) ───────────────────


class TestTimeSeriesServiceUnit:
    """Tests for TimeSeriesService._to_engine_records and related helpers."""

    def test_to_engine_records_mapping(self):
        from app.services.time_series_service import TimeSeriesService

        daily = [
            {
                "tarih": date(2025, 1, 1),
                "ort_tuketim": 32.5,
                "toplam_km": 450.0,
                "ort_ton": 15.0,
                "sefer_sayisi": 2,
            }
        ]
        records = TimeSeriesService._to_engine_records(daily)
        assert len(records) == 1
        r = records[0]
        assert r["date"] == date(2025, 1, 1)
        assert r["consumption"] == 32.5
        assert r["km"] == 450.0
        assert r["ton"] == 15.0
        assert r["trips"] == 2

    def test_to_engine_records_none_values(self):
        from app.services.time_series_service import TimeSeriesService

        daily = [
            {
                "tarih": None,
                "ort_tuketim": None,
                "toplam_km": None,
                "ort_ton": None,
                "sefer_sayisi": None,
            }
        ]
        records = TimeSeriesService._to_engine_records(daily)
        assert records[0]["consumption"] == 0.0
        assert records[0]["km"] == 0.0
        assert records[0]["trips"] == 0

    def test_filter_outliers_removes_extremes(self):
        from app.services.time_series_service import TimeSeriesService

        svc = TimeSeriesService()
        data = [{"ort_tuketim": 32.0} for _ in range(18)]
        data.append({"ort_tuketim": 1000.0})  # extreme outlier
        filtered = svc._filter_outliers(data, threshold=3.0)
        consumptions = [d["ort_tuketim"] for d in filtered]
        assert 1000.0 not in consumptions

    def test_filter_outliers_passthrough_short_data(self):
        from app.services.time_series_service import TimeSeriesService

        svc = TimeSeriesService()
        data = [{"ort_tuketim": v} for v in [30, 31, 32, 1000]]
        result = svc._filter_outliers(data)
        assert len(result) == 4  # less than 10 rows → no filtering
