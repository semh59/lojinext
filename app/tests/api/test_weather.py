"""Weather endpoint tests."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_get_weather_forecast_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test weather forecast retrieval → 200.

    The endpoint is POST /weather/forecast, not GET /weather/forecast.
    WeatherService is injected via WeatherServiceDep; patch get_weather_service.
    """
    from app.core.services.weather_service import WeatherService, get_weather_service
    from app.main import app

    mock_svc = AsyncMock(spec=WeatherService)
    mock_svc.get_forecast_analysis = AsyncMock(
        return_value={
            "success": True,
            "daily": [
                {
                    "date": "2026-06-02",
                    "temperature_max": 25.0,
                    "precipitation_sum": 0.0,
                    "wind_speed_max": 10.0,
                    "impact_factor": 1.0,
                }
            ],
            "fuel_impact_factor": 1.0,
            "recommendation": "Conditions are normal.",
        }
    )

    async def _override():
        return mock_svc

    app.dependency_overrides[get_weather_service] = _override
    try:
        response = await async_client.post(
            "/api/v1/weather/forecast",
            json={"lat": 41.0082, "lon": 28.9784},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "daily" in data
    finally:
        app.dependency_overrides.pop(get_weather_service, None)


@pytest.mark.asyncio
async def test_get_weather_current_conditions(
    async_client, admin_auth_headers, monkeypatch
):
    """Test weather trip-impact → 200.

    There is no GET /current endpoint; use POST /trip-impact instead.
    """
    from app.core.services.weather_service import WeatherService, get_weather_service
    from app.main import app

    mock_svc = AsyncMock(spec=WeatherService)
    mock_svc.get_trip_impact_analysis = AsyncMock(
        return_value={
            "success": True,
            "fuel_impact_factor": 1.05,
            "recommendation": "Mild headwind.",
        }
    )

    async def _override():
        return mock_svc

    app.dependency_overrides[get_weather_service] = _override
    try:
        response = await async_client.post(
            "/api/v1/weather/trip-impact",
            json={
                "cikis_lat": 41.0082,
                "cikis_lon": 28.9784,
                "varis_lat": 39.9334,
                "varis_lon": 32.8597,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "fuel_impact_factor" in data
    finally:
        app.dependency_overrides.pop(get_weather_service, None)


@pytest.mark.asyncio
async def test_weather_requires_auth(async_client):
    """Test weather endpoint requires authentication → 401."""
    response = await async_client.post(
        "/api/v1/weather/forecast",
        json={"lat": 41.0082, "lon": 28.9784},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_weather_invalid_coordinates(async_client, admin_auth_headers):
    """Test weather with invalid coordinates → 422 (Pydantic validation)."""
    response = await async_client.post(
        "/api/v1/weather/forecast",
        json={"lat": "invalid", "lon": "invalid"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422
