from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.routing.openroute_client import OpenRouteClient


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

    @pytest.mark.asyncio
    async def test_call_api_success(self, client):
        """Başarılı API çağrısı (_call_api async, httpx.AsyncClient kullanır)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [
                {
                    "summary": {
                        "distance": 452300,
                        "duration": 19800,
                        "ascent": 1250,
                        "descent": 1180,
                    }
                }
            ]
        }

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client._call_api(
                origin=(40.7669, 29.4319), destination=(39.9334, 32.8597)
            )

        assert result is not None
        assert result["distance_km"] == 452.3
        assert result["duration_hours"] == 5.5

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
        "app.infrastructure.routing.openroute_client.OpenRouteClient._call_api",
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
