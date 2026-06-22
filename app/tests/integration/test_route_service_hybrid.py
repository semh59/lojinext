import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.route_service import RouteService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
class TestRouteServiceHybrid:
    async def test_route_service_falls_back_to_mapbox_on_anomaly(self):
        """Verify that RouteService switches to Mapbox when RouteValidator detects anomaly"""
        service = RouteService()

        # Mock MapboxClient response
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

        # Setup Mock UOW properly
        # We need a MagicMock that works with 'async with'
        mock_uow = MagicMock()
        mock_uow_instance = AsyncMock()
        mock_uow.__aenter__.return_value = mock_uow_instance
        mock_uow.__aexit__.return_value = AsyncMock(return_value=None)

        mock_uow_instance.route_repo = AsyncMock()
        mock_uow_instance.route_repo.get_by_coords.return_value = None
        mock_uow_instance.route_repo.save_route = AsyncMock(return_value=1)

        # Mock Prediction Service - it is NOT async in terms of the function call itself, but it HAS async methods
        mock_pred = MagicMock()
        mock_pred.predict_consumption = AsyncMock(
            return_value={"prediction_liters": 30.0}
        )

        with (
            patch.object(settings, "MAPBOX_API_KEY", "pk.test_key"),
            patch("app.services.route_service.get_uow", return_value=mock_uow),
            patch(
                "app.services.route_service.get_prediction_service",
                return_value=mock_pred,
            ),
        ):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                # Mock ORS Success return (but with bad data)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
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
                mock_post.return_value = mock_response

                # Patch MapboxClient.get_route to return clean data
                with patch(
                    "app.infrastructure.routing.mapbox_client.MapboxClient.get_route",
                    new_callable=AsyncMock,
                ) as mock_mb:
                    mock_mb.return_value = mapbox_mock_result

                    # Call Service
                    result = await service.get_route_details(
                        (28.0, 41.0), (32.0, 39.0), use_cache=False
                    )

                    # Verification
                    assert result["source"] == "mapbox_hybrid"
                    assert result["distance_km"] == 101.0
                    assert result["ascent_m"] == 2250.0
                    assert result["otoban_mesafe_km"] == 92.0
                    assert result["sehir_ici_mesafe_km"] == 9.0
                    assert result["route_analysis"]["ratios"]["otoyol"] == 0.82

    async def test_route_service_self_heals_if_mapbox_fails(self):
        """Verify that RouteService uses ORS correction if Mapbox fallback fails"""
        service = RouteService()

        # Mock ORS Success return (but with bad data)
        ors_mock_json = {
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

        # Setup Mock UOW properly
        mock_uow = MagicMock()
        mock_uow_instance = AsyncMock()
        mock_uow.__aenter__.return_value = mock_uow_instance
        mock_uow.__aexit__.return_value = AsyncMock(return_value=None)

        mock_uow_instance.route_repo = AsyncMock()
        mock_uow_instance.route_repo.get_by_coords.return_value = None
        mock_uow_instance.route_repo.save_route = AsyncMock(return_value=1)

        # Mock Prediction Service
        mock_pred = MagicMock()
        mock_pred.predict_consumption = AsyncMock(
            return_value={"prediction_liters": 30.0}
        )

        with patch.object(settings, "MAPBOX_API_KEY", "pk.test_key"):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = ors_mock_json
                mock_post.return_value = mock_response

                with (
                    patch(
                        "app.infrastructure.routing.mapbox_client.MapboxClient.get_route",
                        side_effect=Exception("Mapbox Timeout"),
                    ),
                    patch("app.services.route_service.get_uow", return_value=mock_uow),
                    patch(
                        "app.services.route_service.get_prediction_service",
                        return_value=mock_pred,
                    ),
                ):
                    result = await service.get_route_details(
                        (28.0, 41.0), (32.0, 39.0), use_cache=False
                    )

                    # Verification
                    assert result["source"] == "api"
                    assert result["ascent_m"] == 2250.0
                    assert result["is_corrected"] is True
