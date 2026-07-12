from unittest.mock import MagicMock

import pytest

from app.config import settings
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient


@pytest.mark.asyncio
class TestMapboxClientIntegration:
    async def test_mapbox_get_route_success(self, monkeypatch):
        """0-mock epiği: gerçek httpx isteği api_stub (Faz 0) sunucusuna gider —
        in-process httpx.AsyncClient mock'u değil, gerçek HTTP round-trip."""
        fake_key = MagicMock()
        fake_key.__bool__ = lambda self: True
        fake_key.get_secret_value = lambda: "fake_test_key"

        monkeypatch.setattr(settings, "MAPBOX_API_KEY", fake_key)
        monkeypatch.setattr(
            settings,
            "MAPBOX_API_BASE_URL",
            "http://localhost:9000/directions/v5/mapbox/driving-traffic",
        )
        client = MapboxClient()
        result = await client.get_route((28.9784, 41.0082), (28.9850, 41.0370))

        assert result is not None
        assert "distance_km" in result
        assert "duration_min" in result
        # api_stub'ın deterministik canned response'u: 450km, 19800s.
        assert result["distance_km"] == 450.0
        assert result["duration_min"] == 330.0
        assert result["source"] == "mapbox"

    async def test_mapbox_get_route_no_key(self, monkeypatch):
        """Should return None if API key is missing"""
        monkeypatch.setattr(settings, "MAPBOX_API_KEY", None)
        client = MapboxClient()
        # Use simple coords
        result = await client.get_route((0, 0), (1, 1))
        assert result is None
