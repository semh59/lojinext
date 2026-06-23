"""Real-object integration tests for RouteService hybrid / self-heal routing.

Only the *external* routing providers are stubbed (ORS via httpx, Mapbox via
MapboxClient.get_route) — calling those for real would mean live API keys, cost
and rate limits. Everything internal runs for real:
  - the UnitOfWork / route_repo cache lookup + save_route hit the real test DB
    (db_session fixture monkeypatches AsyncSessionLocal),
  - get_route_details' real prediction_service call runs (arac_id=0 general model,
    physics fallback) — this is the route->uow->prediction seam that was previously
    mocked away with a hand-crafted {"prediction_liters": 30.0} dict.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.route_service import RouteService

logger = logging.getLogger(__name__)

# ORS response carrying deliberately bad elevation (ascent 5000m) so the
# RouteValidator flags an anomaly and the hybrid/self-heal path engages.
_ORS_BAD_ELEVATION = {
    "features": [
        {
            "properties": {
                "summary": {"distance": 100000, "duration": 4800},
                "ascent": 5000.0,
                "descent": 0.0,
                "extras": {
                    "waycategory": {"values": [[0, 1, 1]]},
                    "waytype": {"values": [[0, 1, 1]]},
                    "steepness": {"values": [[0, 1, 1]]},
                },
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[28.0, 41.0, 0], [32.0, 39.0, 0]],
            },
        }
    ]
}


@pytest.mark.asyncio
class TestRouteServiceHybrid:
    async def test_route_service_falls_back_to_mapbox_on_anomaly(self, db_session):
        """RouteService switches to Mapbox when RouteValidator detects an anomaly."""
        service = RouteService()

        mapbox_mock_result = {
            "distance_km": 101.0,
            "duration_min": 75.0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "otoban_mesafe_km": 92.0,
            "sehir_ici_mesafe_km": 9.0,
            "flat_distance_km": 101.0,
            "source": "mapbox_smart_fallback",
            "route_analysis": {
                "ratios": {"otoyol": 0.82, "devlet_yolu": 0.09, "sehir_ici": 0.09},
                "motorway": {"flat": 72.0, "up": 0, "down": 0},
                "trunk": {"flat": 20.0, "up": 0, "down": 0},
                "residential": {"flat": 9.0, "up": 0, "down": 0},
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[28.0, 41.0, 0], [32.0, 39.0, 0]],
            },
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _ORS_BAD_ELEVATION

        with (
            patch.object(settings, "MAPBOX_API_KEY", "pk.test_key"),
            patch(
                "httpx.AsyncClient.post",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "app.infrastructure.routing.mapbox_client.MapboxClient.get_route",
                new_callable=AsyncMock,
                return_value=mapbox_mock_result,
            ),
        ):
            # Real UoW (route cache get + save_route) and real prediction_service.
            result = await service.get_route_details(
                (28.0, 41.0), (32.0, 39.0), use_cache=False
            )

        assert result["source"] == "mapbox_hybrid"
        assert result["distance_km"] == 101.0
        assert result["ascent_m"] == 2250.0
        assert result["otoban_mesafe_km"] == 92.0
        assert result["sehir_ici_mesafe_km"] == 9.0
        assert result["route_analysis"]["ratios"]["otoyol"] == 0.82

    async def test_route_service_self_heals_if_mapbox_fails(self, db_session):
        """RouteService falls back to ORS self-correction when Mapbox fails."""
        service = RouteService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _ORS_BAD_ELEVATION

        with (
            patch.object(settings, "MAPBOX_API_KEY", "pk.test_key"),
            patch(
                "httpx.AsyncClient.post",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "app.infrastructure.routing.mapbox_client.MapboxClient.get_route",
                side_effect=Exception("Mapbox Timeout"),
            ),
        ):
            result = await service.get_route_details(
                (28.0, 41.0), (32.0, 39.0), use_cache=False
            )

        assert result["source"] == "api"
        assert result["ascent_m"] == 2250.0
        assert result["is_corrected"] is True
