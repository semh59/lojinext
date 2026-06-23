"""Real-object integration tests for the time-series prediction endpoints.

Previously these stubbed get_time_series_service with a StubTimeSeriesService that
hand-returned the failure dicts — so the real service->endpoint contract (does the
real service emit the error_code/status_code the endpoint maps into the
{success, error_code, error_message, request_id, timestamp} envelope?) was never
exercised. Here the real TimeSeriesService runs against an empty test DB, which
naturally yields its real precondition/insufficient-data error paths.
"""

import pytest

pytestmark = pytest.mark.asyncio


async def test_time_series_forecast_returns_structured_precondition_error(
    async_client, auth_headers
):
    """Empty DB → fewer than MIN_FORECAST_DAYS aggregates → the real service returns
    PRECONDITION_NOT_MET, which the endpoint maps to 409 + the flat envelope."""
    response = await async_client.post(
        "/api/v1/predictions/time-series/forecast",
        headers=auth_headers,
    )
    payload = response.json()

    assert response.status_code == 409
    assert payload["success"] is False
    assert payload["error_code"] == "PRECONDITION_NOT_MET"
    assert isinstance(payload["error_message"], str) and payload["error_message"]
    assert "request_id" in payload
    assert "timestamp" in payload


async def test_time_series_trend_returns_structured_service_error(
    async_client, auth_headers
):
    """Empty DB → the real trend analysis cannot run; the endpoint must still return
    the structured error envelope (not a bare 500 / FastAPI default shape)."""
    response = await async_client.get(
        "/api/v1/predictions/time-series/trend",
        headers=auth_headers,
    )
    payload = response.json()

    assert response.status_code >= 400
    assert payload["success"] is False
    assert isinstance(payload["error_code"], str) and payload["error_code"]
    assert isinstance(payload["error_message"], str) and payload["error_message"]
    assert "request_id" in payload
    assert "timestamp" in payload
