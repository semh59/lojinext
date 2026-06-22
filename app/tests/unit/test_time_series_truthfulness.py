from unittest.mock import AsyncMock, patch

import pytest

from app.core.ml.advanced_lstm import ForecastResult
from app.services.time_series_service import TimeSeriesService


@pytest.mark.asyncio
async def test_predict_weekly_fails_closed_when_daily_data_is_insufficient():
    service = TimeSeriesService()

    with patch.object(service, "get_daily_summary", new=AsyncMock(return_value=[])):
        result = await service.predict_weekly(arac_id=None)

    assert result["success"] is False
    assert result["error_code"] == "PRECONDITION_NOT_MET"
    assert "forecast" not in result


@pytest.mark.asyncio
async def test_predict_weekly_does_not_fabricate_mock_forecast_on_model_failure():
    service = TimeSeriesService()
    sufficient_data = [
        {
            "tarih": f"2026-01-{index + 1:02d}",
            "ort_tuketim": 32.0,
            "toplam_km": 450.0,
            "ort_ton": 10.0,
            "sefer_sayisi": 1,
        }
        for index in range(35)
    ]

    with (
        patch.object(
            service,
            "get_daily_summary",
            new=AsyncMock(return_value=sufficient_data),
        ),
        patch.object(
            service.engine,
            "forecast",
            side_effect=RuntimeError("model failed"),
        ),
    ):
        result = await service.predict_weekly(arac_id=None)

    assert result["success"] is False
    assert result["error_code"] == "MODEL_EXECUTION_FAILED"
    assert "forecast" not in result


@pytest.mark.asyncio
async def test_get_trend_analysis_fails_closed_when_daily_data_is_insufficient():
    service = TimeSeriesService()

    with patch.object(
        service,
        "get_daily_summary",
        new=AsyncMock(return_value=[]),
    ):
        result = await service.get_trend_analysis(arac_id=None, days=30)

    assert result["success"] is False
    assert result["error_code"] == "PRECONDITION_NOT_MET"
    assert "daily_values" not in result


@pytest.mark.asyncio
async def test_predict_weekly_uses_real_predictor_output():
    service = TimeSeriesService()
    sufficient_data = [
        {
            "tarih": f"2026-01-{index + 1:02d}",
            "ort_tuketim": 32.0 + (index * 0.01),
            "toplam_km": 450.0,
            "ort_ton": 10.0,
            "sefer_sayisi": 1,
        }
        for index in range(35)
    ]
    fake_result = ForecastResult(
        success=True,
        forecast=[31.5] * 7,
        lower_95=[30.5] * 7,
        upper_95=[32.5] * 7,
        trend="stable",
        method="holt_winters",
        input_days=35,
        forecast_days=7,
    )

    with (
        patch.object(
            service,
            "get_daily_summary",
            new=AsyncMock(return_value=sufficient_data),
        ),
        patch.object(service.engine, "forecast", return_value=fake_result),
    ):
        result = await service.predict_weekly(arac_id=7)

    assert result["success"] is True
    assert result["method"] == "holt_winters"
    assert result["forecast"] == [31.5] * 7
