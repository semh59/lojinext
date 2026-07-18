from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.route_simulation.infrastructure.openroute_client import OpenRouteClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    return OpenRouteClient(api_key="mock_key")


def test_openroute_client_prefers_canonical_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTESERVICE_API_KEY", "canonical-key")
    monkeypatch.setenv("OPENROUTE_API_KEY", "legacy-key")

    client = OpenRouteClient(api_key=None)

    assert client.api_key == "canonical-key"


async def test_get_distance_requests_details_by_default(monkeypatch):
    client = OpenRouteClient(api_key="mock-key")
    breaker = MagicMock()

    # CircuitBreaker.call is async; AsyncMock delegates to the real fn.
    async def mock_call(func, *args, **kwargs):
        return await func(*args, **kwargs)

    breaker.call = AsyncMock(side_effect=mock_call)

    with (
        patch(
            "v2.modules.route_simulation.infrastructure.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(client, "_save_to_cache"),
        patch.object(
            client,
            "_call_api",
            new_callable=AsyncMock,
            return_value={
                "distance_km": 100.0,
                "duration_hours": 1.5,
                "ascent_m": 500.0,
                "descent_m": 450.0,
            },
        ) as mock_call_api,
    ):
        result = await client.get_distance((40.0, 29.0), (39.0, 32.0), use_cache=False)

    assert result["source"] == "api"
    assert mock_call_api.call_args.kwargs["include_details"] is True
