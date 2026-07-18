import asyncio
from unittest.mock import AsyncMock

import pytest

from app.core.services.weather_service import WeatherService


@pytest.mark.asyncio
async def test_weather_service_parallelism():
    """Verify WeatherService fetches start/end weather in parallel"""
    # Mock ExternalService
    mock_ext = AsyncMock()
    service = WeatherService(external_service=mock_ext)

    async def delayed_weather(*args):
        await asyncio.sleep(0.1)
        return {"daily": {}}

    mock_ext.get_weather_forecast.side_effect = delayed_weather

    import time

    start = time.time()
    await service.get_trip_impact_analysis(0, 0, 1, 1)
    end = time.time()

    assert (end - start) < 0.18, "Weather fetch should be parallel"
