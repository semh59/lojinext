from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.route_service import RouteService


@pytest.fixture
def route_service():
    return RouteService()


@pytest.mark.asyncio
async def test_get_route_details_parses_waycategory_and_returns_analysis(route_service):
    # Setup
    start = (29.0, 40.0)
    end = (32.0, 39.0)

    # Mock external service client response
    # Use MagicMock for client, but AsyncMock for methods that are awaited
    mock_client = MagicMock()
    mock_client.post = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 200

    # Mock ORS response with waycategory and steepness
    mock_response.json.return_value = {
        "features": [
            {
                "properties": {
                    "summary": {"distance": 100000, "duration": 3600},
                    "ascent": 500,
                    "descent": 500,
                    "extras": {
                        "waycategory": {
                            "values": [
                                [0, 5, 1],  # Motorway (0-5)
                                [5, 10, 3],  # Secondary (5-10) -> sehir_ici
                            ]
                        },
                        "steepness": {
                            "values": [
                                [0, 3, 0],  # Flat
                                [3, 5, 2],  # Up
                                [5, 8, 0],  # Flat
                                [8, 10, -2],  # Down
                            ]
                        },
                    },
                },
                "geometry": {
                    "coordinates": [
                        [i, i, 0] for i in range(11)
                    ]  # 11 points for 10 segments
                },
            }
        ]
    }

    # Mock haversine to return steady distance per segment to make math easy
    # Let's mock _get_segment_distance or haversine
    # Actually route_analyzer calculates distance from geometry.
    # For this test, we can mock route_analyzer.analyze_segments to return a fixed structure
    # to verify RouteService integrates it correctly.

    mock_analysis_result = {
        "highway": {"flat": 30.0, "up": 20.0, "down": 0.0},
        "other": {"flat": 10.0, "up": 0.0, "down": 40.0},
    }

    # Set API Key to bypass check
    route_service.api_key = "test_key"

    with (
        patch(
            "app.services.external_service.get_external_service"
        ) as mock_get_ext_service,
        patch(
            "app.domain.services.route_analyzer.route_analyzer.analyze_segments",
            return_value=mock_analysis_result,
        ) as mock_analyze,
        patch("app.services.route_service.get_uow") as mock_get_uow,
        patch(
            "app.services.route_service.get_prediction_service"
        ) as mock_get_pred_service,
    ):
        # Mock dependencies
        # _get_client is async in ExternalService
        mock_get_ext_service.return_value._get_client = AsyncMock(
            return_value=mock_client
        )
        mock_client.post.return_value = mock_response

        # Mock UOW
        mock_uow = MagicMock()
        mock_get_uow.return_value.__aenter__.return_value = mock_uow
        mock_uow.route_repo.get_by_coords.return_value = (
            None  # Cache miss to force API call
        )
        mock_uow.route_repo.save_route = AsyncMock()  # Mock save
        mock_uow.commit = AsyncMock()

        # Mock Prediction Service
        mock_pred_service = MagicMock()
        mock_get_pred_service.return_value = mock_pred_service
        mock_pred_service.predict_consumption = AsyncMock(return_value=150.0)

        # We also need to mock haversine or _get_segment_distance if the service still uses it for otoban_m calculation loop  # noqa: E501
        # Wait, I kept the loop for otoban_m calculation in RouteService?
        # Yes, lines 151-166 in RouteService.py still exist in my previous edit?
        # No, I replaced them in Step 1404 with "Use Domain Service for Analysis".
        # So I don't need to mock _get_segment_distance logic for otoban_m, because it now uses the analysis result.

        # Execute
        result = await route_service.get_route_details(start, end, use_cache=False)

        # Debug
        assert "error" not in result, f"Service returned error: {result}"

        # Verify
        assert result["otoban_mesafe_km"] == 50.0  # 30+20
        assert result["sehir_ici_mesafe_km"] == 50.0  # 10+40
        assert result["route_analysis"] == mock_analysis_result

        # Verify route_analyzer called
        mock_analyze.assert_called_once()
        assert result["sehir_ici_mesafe_km"] == 50.0  # 10+40
        assert result["route_analysis"] == mock_analysis_result

        # Verify route_analyzer called
        mock_analyze.assert_called_once()


@pytest.mark.asyncio
async def test_get_route_details_surfaces_provider_failure(route_service):
    start = (29.0, 40.0)
    end = (32.0, 39.0)

    mock_client = MagicMock()
    mock_client.post = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "upstream failure"

    route_service.api_key = "test_key"

    with (
        patch(
            "app.services.external_service.get_external_service"
        ) as mock_get_ext_service,
        patch("app.services.route_service.get_uow") as mock_get_uow,
    ):
        mock_get_ext_service.return_value._get_client = AsyncMock(
            return_value=mock_client
        )
        mock_client.post.return_value = mock_response

        mock_uow = MagicMock()
        mock_get_uow.return_value.__aenter__.return_value = mock_uow
        mock_uow.route_repo.get_by_coords.return_value = None

        result = await route_service.get_route_details(start, end, use_cache=False)

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
