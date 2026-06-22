from unittest.mock import AsyncMock

import pytest

from app.core.services.weather_service import WeatherService


@pytest.mark.asyncio
async def test_get_forecast_analysis_fails_closed_when_provider_is_unavailable():
    service = WeatherService(external_service=AsyncMock())
    service.external_service.get_weather_forecast.return_value = {
        "error": "Weather provider request failed.",
        "error_code": "SERVICE_UNAVAILABLE",
    }

    result = await service.get_forecast_analysis(41.0, 29.0)

    assert result["success"] is False
    assert result["offline"] is True
    assert result["error_code"] == "SERVICE_UNAVAILABLE"
    assert result["fuel_impact_factor"] is None
    assert result["daily"] == []


@pytest.mark.asyncio
async def test_trip_impact_analysis_fails_closed_when_any_endpoint_weather_is_missing():
    service = WeatherService(external_service=AsyncMock())
    service.external_service.get_weather_forecast = AsyncMock(
        side_effect=[
            {
                "daily": {
                    "temperature_2m_max": [20],
                    "precipitation_sum": [0],
                    "wind_speed_10m_max": [10],
                }
            },
            {
                "error": "Weather provider request failed.",
                "error_code": "SERVICE_UNAVAILABLE",
            },
        ]
    )

    result = await service.get_trip_impact_analysis(41.0, 29.0, 40.0, 32.0)

    assert result["success"] is False
    assert result["error_code"] == "SERVICE_UNAVAILABLE"
    assert "fuel_impact_factor" not in result
