"""0-mock epiği: gerçek httpx isteği api_stub sunucusuna gider (`?simulate=
error` / sentinel latitude=999 ile Open-Meteo'nun gerçek bir hata dönüşünü
simüle eder) — in-process `ExternalService.get_weather_forecast` mock'u
değil, gerçek HTTP round-trip. Daha önce `external_service.py`'nin
`OPENMETEO_URL`'i hardcoded olduğu için (settings.
OPEN_METEO_FORECAST_API_BASE_URL'i hiç okumuyordu) bu testler api_stub'a
hiç yönlendirilemiyordu, mock'lamak zorundaydı; her ikisi de 2026-07-30'da
düzeltildi (api_stub/main.py'ye yeni /v1/forecast endpoint'i eklendi).
"""

import pytest

from app.config import settings
from v2.modules.route_simulation.application.weather_service import WeatherService
from v2.modules.route_simulation.infrastructure.external_service import (
    ExternalService,
)


@pytest.mark.asyncio
async def test_get_forecast_analysis_fails_closed_when_provider_is_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "OPEN_METEO_FORECAST_API_BASE_URL",
        "http://localhost:9000/v1/forecast?simulate=error",
    )
    service = WeatherService(external_service=ExternalService())

    result = await service.get_forecast_analysis(41.0, 29.0)

    assert result["success"] is False
    assert result["offline"] is True
    assert result["error_code"] == "SERVICE_UNAVAILABLE"
    assert result["fuel_impact_factor"] is None
    assert result["daily"] == []


@pytest.mark.asyncio
async def test_trip_impact_analysis_fails_closed_when_any_endpoint_weather_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "OPEN_METEO_FORECAST_API_BASE_URL",
        "http://localhost:9000/v1/forecast",
    )
    service = WeatherService(external_service=ExternalService())

    # Sentinel latitude=999 (varis_lat) -> api_stub returns a provider error
    # for only that one call; cikis_lat=41.0 gets a normal response.
    result = await service.get_trip_impact_analysis(41.0, 29.0, 999.0, 32.0)

    assert result["success"] is False
    assert result["error_code"] == "SERVICE_UNAVAILABLE"
    assert "fuel_impact_factor" not in result
