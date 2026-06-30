"""
Coverage tests for TimeSeriesService (services/time_series_service.py).
Focuses on _failure, _to_engine_records, _filter_outliers, get_daily_summary,
train_model, predict_weekly (vehicle fallback to fleet), get_trend_analysis,
get_model_status, and the factory function.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ml.advanced_lstm import ForecastResult
from app.database.unit_of_work import UnitOfWork
from app.services.time_series_service import (
    TimeSeriesDataUnavailable,
    TimeSeriesService,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _daily_row(index: int, consumption: float = 32.0) -> dict:
    return {
        "tarih": f"2026-01-{index + 1:02d}",
        "ort_tuketim": consumption,
        "toplam_km": 450.0,
        "ort_ton": 10.0,
        "sefer_sayisi": 1,
    }


def _daily_data(n: int, consumption: float = 32.0):
    return [_daily_row(i, consumption) for i in range(n)]


def _make_service():
    svc = TimeSeriesService()
    return svc


def _patch_uow(mock_repo):
    """AUDIT-131: get_daily_summary artık session'lı UnitOfWork kullanır."""
    mock_uow = MagicMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = mock_repo
    stack = ExitStack()
    stack.enter_context(
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow))
    )
    stack.enter_context(
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False))
    )
    return stack


# ---------------------------------------------------------------------------
# Tests: _failure helper
# ---------------------------------------------------------------------------


class TestFailure:
    def test_sets_success_false(self):
        result = TimeSeriesService._failure(
            error_code="TEST", error_message="err", status_code=400
        )
        assert result["success"] is False

    def test_contains_error_code(self):
        result = TimeSeriesService._failure(
            error_code="MY_CODE", error_message="msg", status_code=409
        )
        assert result["error_code"] == "MY_CODE"

    def test_contains_status_code(self):
        result = TimeSeriesService._failure(
            error_code="X", error_message="m", status_code=503
        )
        assert result["status_code"] == 503

    def test_extra_kwargs_included(self):
        result = TimeSeriesService._failure(
            error_code="X",
            error_message="m",
            status_code=400,
            vehicle_id=42,
        )
        assert result["vehicle_id"] == 42


# ---------------------------------------------------------------------------
# Tests: _to_engine_records
# ---------------------------------------------------------------------------


class TestToEngineRecords:
    def test_maps_tarih_to_date(self):
        rows = [_daily_row(0)]
        records = TimeSeriesService._to_engine_records(rows)
        assert records[0]["date"] == "2026-01-01"

    def test_maps_ort_tuketim_to_consumption(self):
        rows = [_daily_row(0, consumption=35.5)]
        records = TimeSeriesService._to_engine_records(rows)
        assert records[0]["consumption"] == pytest.approx(35.5)

    def test_maps_toplam_km_to_km(self):
        rows = [_daily_row(0)]
        records = TimeSeriesService._to_engine_records(rows)
        assert records[0]["km"] == 450.0

    def test_maps_sefer_sayisi_to_trips(self):
        rows = [_daily_row(0)]
        records = TimeSeriesService._to_engine_records(rows)
        assert records[0]["trips"] == 1

    def test_none_values_default_to_zero(self):
        rows = [
            {
                "tarih": None,
                "ort_tuketim": None,
                "toplam_km": None,
                "ort_ton": None,
                "sefer_sayisi": None,
            }
        ]
        records = TimeSeriesService._to_engine_records(rows)
        assert records[0]["consumption"] == 0.0
        assert records[0]["km"] == 0.0
        assert records[0]["trips"] == 0

    def test_empty_list_returns_empty(self):
        assert TimeSeriesService._to_engine_records([]) == []


# ---------------------------------------------------------------------------
# Tests: _filter_outliers
# ---------------------------------------------------------------------------


class TestFilterOutliers:
    def test_fewer_than_10_rows_unchanged(self):
        svc = _make_service()
        data = _daily_data(5)
        result = svc._filter_outliers(data)
        assert result == data

    def test_removes_extreme_outlier(self):
        svc = _make_service()
        data = _daily_data(15, consumption=32.0)
        # Add extreme outlier
        data[7]["ort_tuketim"] = 9999.0
        filtered = svc._filter_outliers(data, threshold=3.0)
        assert len(filtered) < len(data)
        assert all(d["ort_tuketim"] < 9999.0 for d in filtered)

    def test_no_removal_when_uniform(self):
        svc = _make_service()
        data = _daily_data(15, consumption=32.0)
        filtered = svc._filter_outliers(data)
        assert len(filtered) == len(data)

    def test_zero_std_returns_unchanged(self):
        svc = _make_service()
        # All same values → std=0 → no filtering
        data = [_daily_row(i, consumption=32.0) for i in range(12)]
        filtered = svc._filter_outliers(data)
        assert len(filtered) == len(data)


# ---------------------------------------------------------------------------
# Tests: get_daily_summary
# ---------------------------------------------------------------------------


class TestGetDailySummary:
    async def test_returns_formatted_rows(self):
        svc = _make_service()
        mock_repo = MagicMock()
        raw = [
            {
                "tarih": "2026-01-01",
                "ort_tuketim": 32.0,
                "toplam_km": 450.0,
                "ort_ton": 10.0,
                "sefer_sayisi": 1,
            }
        ]
        mock_repo.get_daily_summary_for_ml = AsyncMock(return_value=raw)

        with _patch_uow(mock_repo):
            result = await svc.get_daily_summary(days=90)

        assert len(result) == 1
        assert "tarih" in result[0]
        assert "ort_tuketim" in result[0]

    async def test_raises_unavailable_on_repo_exception(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_repo.get_daily_summary_for_ml = AsyncMock(
            side_effect=RuntimeError("DB down")
        )

        with _patch_uow(mock_repo):
            with pytest.raises(TimeSeriesDataUnavailable):
                await svc.get_daily_summary(days=90)

    async def test_days_clamped_to_365(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_repo.get_daily_summary_for_ml = AsyncMock(return_value=[])

        with _patch_uow(mock_repo):
            await svc.get_daily_summary(days=9999)

        call_kwargs = mock_repo.get_daily_summary_for_ml.call_args
        passed_days = call_kwargs.kwargs.get("days") or call_kwargs.args[0]
        assert passed_days <= 365

    async def test_days_clamped_to_at_least_1(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_repo.get_daily_summary_for_ml = AsyncMock(return_value=[])

        with _patch_uow(mock_repo):
            await svc.get_daily_summary(days=0)

        call_kwargs = mock_repo.get_daily_summary_for_ml.call_args
        passed_days = call_kwargs.kwargs.get("days") or call_kwargs.args[0]
        assert passed_days >= 1


# ---------------------------------------------------------------------------
# Tests: train_model
# ---------------------------------------------------------------------------


class TestTrainModel:
    async def test_insufficient_data_returns_precondition_not_met(self):
        svc = _make_service()
        with patch.object(
            svc, "get_daily_summary", new=AsyncMock(return_value=_daily_data(10))
        ):
            result = await svc.train_model()
        assert result["success"] is False
        assert result["error_code"] == "PRECONDITION_NOT_MET"

    async def test_service_unavailable_on_repo_failure(self):
        svc = _make_service()
        with patch.object(
            svc,
            "get_daily_summary",
            new=AsyncMock(side_effect=TimeSeriesDataUnavailable("down")),
        ):
            result = await svc.train_model()
        assert result["success"] is False
        assert result["error_code"] == "SERVICE_UNAVAILABLE"

    async def test_train_calls_engine_when_sufficient_data(self):
        svc = _make_service()
        sufficient = _daily_data(50)

        with (
            patch.object(
                svc, "get_daily_summary", new=AsyncMock(return_value=sufficient)
            ),
            patch.object(
                svc.engine, "train", return_value={"success": True}
            ) as mock_train,
        ):
            result = await svc.train_model()

        mock_train.assert_called_once()
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests: predict_weekly
# ---------------------------------------------------------------------------


class TestPredictWeeklyExtended:
    async def test_service_unavailable_propagated(self):
        svc = _make_service()
        with patch.object(
            svc,
            "get_daily_summary",
            new=AsyncMock(side_effect=TimeSeriesDataUnavailable("down")),
        ):
            result = await svc.predict_weekly(arac_id=1)
        assert result["success"] is False
        assert result["error_code"] == "SERVICE_UNAVAILABLE"

    async def test_vehicle_fallback_to_fleet_when_insufficient(self):
        """Vehicle with insufficient data falls back to fleet-wide."""
        svc = _make_service()

        # Vehicle call returns 0 rows, fleet call returns sufficient
        call_count = 0

        async def fake_daily(arac_id=None, days=90):
            nonlocal call_count
            call_count += 1
            if arac_id is not None:
                return []  # insufficient for vehicle
            return _daily_data(35)  # sufficient for fleet

        fake_result = ForecastResult(
            success=True,
            forecast=[32.0] * 7,
            lower_95=[30.0] * 7,
            upper_95=[34.0] * 7,
            trend="stable",
            method="ema",
            input_days=35,
            forecast_days=7,
        )

        with (
            patch.object(svc, "get_daily_summary", side_effect=fake_daily),
            patch.object(svc.engine, "forecast", return_value=fake_result),
        ):
            result = await svc.predict_weekly(arac_id=5)

        # Result should come from the fleet fallback
        assert result.get("success") is True

    async def test_forecast_failed_result_returns_error(self):
        svc = _make_service()
        sufficient = _daily_data(35)
        failed_result = ForecastResult(
            success=False,
            error_code="NO_DATA",
            error_message="Failed",
        )
        with (
            patch.object(
                svc, "get_daily_summary", new=AsyncMock(return_value=sufficient)
            ),
            patch.object(svc.engine, "forecast", return_value=failed_result),
        ):
            result = await svc.predict_weekly(arac_id=None)

        assert result["success"] is False

    async def test_success_response_has_forecast_dates(self):
        svc = _make_service()
        sufficient = _daily_data(35)
        fake_result = ForecastResult(
            success=True,
            forecast=[32.0] * 7,
            lower_95=[30.0] * 7,
            upper_95=[34.0] * 7,
            trend="stable",
            method="ema",
            input_days=35,
            forecast_days=7,
        )
        with (
            patch.object(
                svc, "get_daily_summary", new=AsyncMock(return_value=sufficient)
            ),
            patch.object(svc.engine, "forecast", return_value=fake_result),
        ):
            result = await svc.predict_weekly(arac_id=None)

        assert "forecast_dates" in result
        assert len(result["forecast_dates"]) == 7


# ---------------------------------------------------------------------------
# Tests: get_trend_analysis
# ---------------------------------------------------------------------------


class TestGetTrendAnalysisExtended:
    async def test_service_unavailable_propagated(self):
        svc = _make_service()
        with patch.object(
            svc,
            "get_daily_summary",
            new=AsyncMock(side_effect=TimeSeriesDataUnavailable("down")),
        ):
            result = await svc.get_trend_analysis(arac_id=None, days=30)
        assert result["success"] is False
        assert result["error_code"] == "SERVICE_UNAVAILABLE"

    async def test_insufficient_data_returns_error(self):
        svc = _make_service()
        with patch.object(
            svc, "get_daily_summary", new=AsyncMock(return_value=_daily_data(3))
        ):
            result = await svc.get_trend_analysis(arac_id=None, days=30)
        assert result["success"] is False
        assert result["error_code"] == "PRECONDITION_NOT_MET"

    async def test_trend_increasing_detected(self):
        svc = _make_service()
        # Strictly increasing consumptions
        data = [_daily_row(i, consumption=28.0 + i * 1.0) for i in range(15)]
        with patch.object(svc, "get_daily_summary", new=AsyncMock(return_value=data)):
            result = await svc.get_trend_analysis(arac_id=None, days=15)
        assert result["success"] is True
        assert result["trend"] == "increasing"

    async def test_trend_decreasing_detected(self):
        svc = _make_service()
        data = [_daily_row(i, consumption=42.0 - i * 1.0) for i in range(15)]
        with patch.object(svc, "get_daily_summary", new=AsyncMock(return_value=data)):
            result = await svc.get_trend_analysis(arac_id=None, days=15)
        assert result["success"] is True
        assert result["trend"] == "decreasing"

    async def test_trend_stable_detected(self):
        svc = _make_service()
        data = _daily_data(15, consumption=32.0)
        with patch.object(svc, "get_daily_summary", new=AsyncMock(return_value=data)):
            result = await svc.get_trend_analysis(arac_id=None, days=15)
        assert result["success"] is True
        assert result["trend"] == "stable"

    async def test_result_has_expected_keys(self):
        svc = _make_service()
        data = _daily_data(15)
        with patch.object(svc, "get_daily_summary", new=AsyncMock(return_value=data)):
            result = await svc.get_trend_analysis(arac_id=None, days=15)
        for key in [
            "trend",
            "slope",
            "current_avg",
            "daily_values",
            "dates",
            "days_analyzed",
        ]:
            assert key in result

    async def test_moving_average_7_present(self):
        svc = _make_service()
        data = _daily_data(20)
        with patch.object(svc, "get_daily_summary", new=AsyncMock(return_value=data)):
            result = await svc.get_trend_analysis(arac_id=None, days=20)
        assert "moving_average_7" in result
        assert isinstance(result["moving_average_7"], list)


# ---------------------------------------------------------------------------
# Tests: get_model_status
# ---------------------------------------------------------------------------


class TestGetModelStatus:
    def test_returns_dict(self):
        svc = _make_service()
        status = svc.get_model_status()
        assert isinstance(status, dict)


# ---------------------------------------------------------------------------
# Tests: TimeSeriesDataUnavailable exception
# ---------------------------------------------------------------------------


class TestTimeSeriesDataUnavailable:
    def test_is_runtime_error(self):
        exc = TimeSeriesDataUnavailable("test message")
        assert isinstance(exc, RuntimeError)
        assert "test message" in str(exc)
