from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.route_simulation.infrastructure.openroute_client import OpenRouteClient


class TestOpenRouteClient:
    """OpenRouteClient birim testleri"""

    @pytest.fixture
    def client(self):
        """Test hazırlığı"""
        return OpenRouteClient(api_key="test-api-key-placeholder")

    def test_validate_coordinates_valid(self, client):
        """Geçerli Türkiye koordinatları"""
        origin = (40.7669, 29.4319)
        destination = (39.9334, 32.8597)
        assert client._validate_coordinates(origin, destination) is True

    def test_validate_coordinates_invalid_latitude(self, client):
        """Geçersiz enlem (Türkiye dışı)"""
        origin = (50.0, 29.0)
        destination = (39.9, 32.8)
        assert client._validate_coordinates(origin, destination) is False

    # test_call_api_success moved 2026-07-30 to
    # app/tests/integration/test_route_api.py::test_call_api_success --
    # its 0-mock conversion to real HTTP against api_stub needs api_stub
    # already running, which this file's CI lane ("Backend unit tests")
    # starts *before*; app/tests/integration/ is excluded from that lane
    # and runs after api_stub is up.

    @pytest.mark.asyncio
    async def test_get_distance_no_api_key(self):
        """API key olmadan çağrı → None"""
        client = OpenRouteClient(api_key=None)
        client.api_key = None
        result = await client.get_distance(
            origin=(40.7669, 29.4319), destination=(39.9334, 32.8597), use_cache=False
        )
        assert result is None


class TestOpenRouteClientIntegration:
    """Entegrasyon testleri (gerçek API çağrısı)"""

    @pytest.mark.skipif(
        not __import__("os").getenv("OPENROUTE_API_KEY"),
        reason="OPENROUTE_API_KEY tanımlanmamış",
    )
    @pytest.mark.asyncio
    @patch(
        "v2.modules.route_simulation.infrastructure.openroute_client.OpenRouteClient._call_api",
        new_callable=AsyncMock,
    )
    async def test_real_api_call(self, mock_call):
        """Gerçek API çağrısı simülasyonu (Gebze -> Ankara)"""
        mock_call.return_value = {
            "distance_km": 450.0,
            "duration_hours": 5.0,
            "ascent_m": 1000,
            "descent_m": 1000,
        }
        client = OpenRouteClient(api_key="test-key")
        result = await client.get_distance(
            origin=(40.7669, 29.4319), destination=(39.9334, 32.8597), use_cache=False
        )
        assert result is not None
        assert 350 < result["distance_km"] < 500
