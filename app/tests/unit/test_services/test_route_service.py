"""Unit tests for RouteService.

0-mock epigi (Faz1 dilim4): ORS `httpx.AsyncClient.post` -> real HTTP against
api_stub (sentinel coordinates select scenario). route_analyzer.analyze_segments
runs for real (no longer mocked) -- it is internal domain logic, not an
external boundary. get_uow -> real db_session/UnitOfWork. Only
get_prediction_service (ML domain, separate slice) stays documented-mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from v2.modules.route_simulation.application.get_route_details import RouteService

pytestmark = pytest.mark.integration


@pytest.fixture
def route_service():
    return RouteService()


@pytest.mark.asyncio
async def test_get_route_details_parses_waycategory_and_returns_analysis(
    route_service, db_session, monkeypatch
):
    """Real ORS call (api_stub) + real RouteAnalyzer segment classification;
    only the fuel-prediction ML call stays documented-mocked."""
    start = (0.0, 0.0)
    end = (0.0, 777.0)

    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    route_service.base_url = settings.OPENROUTE_API_BASE_URL
    route_service.api_key = "test_key"

    with patch(
        "app.services.prediction_service.get_prediction_service"
    ) as mock_get_pred_service:
        mock_pred_service = MagicMock()
        mock_get_pred_service.return_value = mock_pred_service
        mock_pred_service.predict_consumption = AsyncMock(return_value=150.0)

        result = await route_service.get_route_details(start, end, use_cache=False)

    assert "error" not in result, f"Service returned error: {result}"
    assert isinstance(result["route_analysis"], dict)
    assert "highway" in result["route_analysis"]
    assert "other" in result["route_analysis"]
    # Real haversine-derived otoban/sehir_ici split from the stub's real
    # multi-leg geometry (motorway 0-5, secondary 5-10) -- not a hand-crafted
    # mock value.
    assert result["otoban_mesafe_km"] > 0
    assert result["sehir_ici_mesafe_km"] > 0


@pytest.mark.asyncio
async def test_get_route_details_surfaces_provider_failure(
    route_service, db_session, monkeypatch
):
    """Real ORS call against api_stub; sentinel coords (0,0)->(0,500) trigger
    a real 500 response."""
    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    route_service.base_url = settings.OPENROUTE_API_BASE_URL
    route_service.api_key = "test_key"

    result = await route_service.get_route_details(
        (0.0, 0.0), (0.0, 500.0), use_cache=False
    )

    assert result["error_code"] == "SERVICE_UNAVAILABLE"
    assert result["source"] == "provider_error"
    assert "distance_km" not in result
    assert "route_analysis" not in result


def test_route_service_prefers_canonical_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTESERVICE_API_KEY", "canonical-key")
    monkeypatch.setenv("OPENROUTE_API_KEY", "legacy-key")

    service = RouteService()

    assert service.api_key == "canonical-key"


def test_route_service_uses_settings_key_when_env_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTESERVICE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTE_API_KEY", raising=False)

    with patch.object(settings, "OPENROUTESERVICE_API_KEY", "settings-key"):
        service = RouteService()

    assert service.api_key == "settings-key"
