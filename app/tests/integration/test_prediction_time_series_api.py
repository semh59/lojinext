import pytest


@pytest.mark.asyncio
async def test_time_series_forecast_returns_structured_precondition_error(
    async_client, auth_headers, monkeypatch
):
    class StubTimeSeriesService:
        async def predict_weekly(self, arac_id):
            return {
                "success": False,
                "error_code": "PRECONDITION_NOT_MET",
                "error": "At least 30 daily aggregates are required for forecasting.",
                "status_code": 409,
            }

    monkeypatch.setattr(
        "app.services.time_series_service.get_time_series_service",
        lambda: StubTimeSeriesService(),
    )

    response = await async_client.post(
        "/api/v1/predictions/time-series/forecast",
        headers=auth_headers,
    )
    payload = response.json()

    assert response.status_code == 409
    assert payload == {
        "success": False,
        "error_code": "PRECONDITION_NOT_MET",
        "error_message": "At least 30 daily aggregates are required for forecasting.",
        "request_id": payload["request_id"],
        "timestamp": payload["timestamp"],
    }


@pytest.mark.asyncio
async def test_time_series_trend_returns_structured_service_error(
    async_client, auth_headers, monkeypatch
):
    class StubTimeSeriesService:
        async def get_trend_analysis(self, arac_id, days):
            return {
                "success": False,
                "error_code": "MODEL_EXECUTION_FAILED",
                "error": "Time-series trend analysis is unavailable.",
                "status_code": 503,
            }

    monkeypatch.setattr(
        "app.services.time_series_service.get_time_series_service",
        lambda: StubTimeSeriesService(),
    )

    response = await async_client.get(
        "/api/v1/predictions/time-series/trend",
        headers=auth_headers,
    )
    payload = response.json()

    assert response.status_code == 503
    assert payload == {
        "success": False,
        "error_code": "MODEL_EXECUTION_FAILED",
        "error_message": "Time-series trend analysis is unavailable.",
        "request_id": payload["request_id"],
        "timestamp": payload["timestamp"],
    }
