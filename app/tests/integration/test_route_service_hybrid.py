"""Real-object integration tests for RouteService hybrid / self-heal routing.

0-mock epigi (Faz1 dilim4): ORS (`httpx.AsyncClient.post`) and Mapbox
(`MapboxClient.get_route`) in-process mocks replaced with real HTTP against
api_stub (`--profile test`). Sentinel coordinates (0,0)->(0,999) select the
stub's deliberately-bad-elevation ORS scenario (ascent 5000m) so
RouteValidator flags an anomaly and the hybrid/self-heal path engages --
same sentinel-coordinate technique used elsewhere in this epic (real HTTP
behavior, not a mock). Everything internal runs for real:
  - the UnitOfWork / route_repo cache lookup + save_route hit the real test DB
    (db_session fixture monkeypatches AsyncSessionLocal),
  - MapboxClient.get_route runs for real against api_stub's Mapbox endpoint
    (already exercised in Faz1 dilim1's mapbox_client tests),
  - get_route_details' real prediction_service call runs (arac_id=0 general
    model, physics fallback) -- this is the route->uow->prediction seam that
    was previously mocked away with a hand-crafted dict.
"""

import logging

import pytest

from app.config import settings

logger = logging.getLogger(__name__)

_SENTINEL_START = (0.0, 0.0)
_SENTINEL_END = (0.0, 999.0)


def _patch_ors_and_mapbox_base_urls(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    monkeypatch.setattr(
        settings,
        "MAPBOX_API_BASE_URL",
        "http://localhost:9000/directions/v5/mapbox/driving-traffic",
    )


@pytest.mark.asyncio
class TestRouteServiceHybrid:
    async def test_route_service_falls_back_to_mapbox_on_anomaly(
        self, db_session, monkeypatch
    ):
        """get_route_details switches to Mapbox when RouteValidator detects an anomaly."""
        from v2.modules.route_simulation.application.get_route_details import (
            get_route_details,
        )

        _patch_ors_and_mapbox_base_urls(monkeypatch)
        monkeypatch.setattr(settings, "MAPBOX_API_KEY", "pk.test_key")
        monkeypatch.setattr(settings, "OPENROUTESERVICE_API_KEY", "test_key")

        result = await get_route_details(
            _SENTINEL_START, _SENTINEL_END, use_cache=False
        )

        assert result["source"] == "mapbox_hybrid"
        # api_stub's canned Mapbox directions response (Faz1 dilim1): 450km/19800s.
        assert result["distance_km"] == 450.0
        assert result["duration_min"] == 330.0
        assert isinstance(result["route_analysis"], dict)

    async def test_route_service_self_heals_if_mapbox_fails(
        self, db_session, monkeypatch
    ):
        """get_route_details falls back to ORS self-correction when Mapbox fails."""
        from v2.modules.route_simulation.application.get_route_details import (
            get_route_details,
        )

        _patch_ors_and_mapbox_base_urls(monkeypatch)
        # No Mapbox API key configured -> MapboxClient.get_route short-circuits
        # to None for real (see mapbox_client.py's "API Key missing" guard),
        # forcing the self-heal (corrected-ORS) path instead of a Mapbox call.
        monkeypatch.setattr(settings, "MAPBOX_API_KEY", None)
        monkeypatch.setattr(settings, "OPENROUTESERVICE_API_KEY", "test_key")

        result = await get_route_details(
            _SENTINEL_START, _SENTINEL_END, use_cache=False
        )

        assert result["source"] == "api"
        assert (
            result["ascent_m"] == 2250.0
        )  # RouteValidator-corrected (raw 5000*0.6=3000)
        assert result["is_corrected"] is True
