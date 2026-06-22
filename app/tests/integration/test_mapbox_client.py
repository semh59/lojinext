import pytest

from app.config import settings
from app.infrastructure.routing.mapbox_client import MapboxClient


@pytest.mark.asyncio
class TestMapboxClientIntegration:
    async def test_mapbox_get_route_success(self, monkeypatch):
        """Test Mapbox routing with mocked HTTP client."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [
                {
                    "distance": 450000.0,
                    "duration": 18000.0,
                    "geometry": {"type": "LineString", "coordinates": []},
                    "legs": [],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        fake_key = MagicMock()
        fake_key.__bool__ = lambda self: True
        fake_key.get_secret_value = lambda: "fake_test_key"

        with patch("httpx.AsyncClient", return_value=mock_client):
            monkeypatch.setattr(settings, "MAPBOX_API_KEY", fake_key)
            client = MapboxClient()
            result = await client.get_route((28.9784, 41.0082), (28.9850, 41.0370))

        assert result is not None
        assert "distance_km" in result
        assert "duration_min" in result
        assert result["distance_km"] == 450.0
        assert result["source"] == "mapbox"

    async def test_mapbox_get_route_no_key(self, monkeypatch):
        """Should return None if API key is missing"""
        monkeypatch.setattr(settings, "MAPBOX_API_KEY", None)
        client = MapboxClient()
        # Use simple coords
        result = await client.get_route((0, 0), (1, 1))
        assert result is None
