from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.routing.openroute_client import OpenRouteClient


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def client():
    return OpenRouteClient(api_key="mock_key")


async def test_update_route_distance_parses_details(client):
    # Setup
    lokasyon_id = 999

    # Mock return from get_distance (simulation of OK response from API)
    mock_api_result = {
        "distance_km": 100.0,
        "duration_hours": 1.5,
        "ascent_m": 500,
        "descent_m": 500,
        "details": {
            "highway": {"flat": 40.0, "up": 10.0, "down": 10.0},  # Total 60
            "other": {"flat": 20.0, "up": 10.0, "down": 10.0},  # Total 40
        },
    }

    # Mock fetchone to return coordinates
    mock_row = MagicMock()
    mock_row.cikis_lat = 40.0
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 39.0
    mock_row.varis_lon = 32.0

    # Create a proper async session mock
    mock_session = MagicMock()
    select_result = MagicMock()  # Result object (not async)
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)  # execute() is async
    mock_session.commit = AsyncMock()  # commit() is async

    # Mock AsyncSessionLocal (imported inside the method)
    class AsyncContextManager:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    def mock_async_session_factory():
        return AsyncContextManager()

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=mock_async_session_factory,
        ),
        patch.object(
            client, "get_distance", new_callable=AsyncMock, return_value=mock_api_result
        ),
    ):
        # Execute
        result = await client.update_route_distance(lokasyon_id)

        # Verify result
        assert result == mock_api_result

        # Verify SQL update params
        # The second call to execute should be the UPDATE
        # 1st call: SELECT coords
        # 2nd call: UPDATE
        assert mock_session.execute.call_count == 2

        args, kwargs = mock_session.execute.call_args_list[1]
        sql = args[0]
        params = args[1]

        # Assertions
        str_sql = str(sql)
        assert "otoban_mesafe_km = :otoban" in str_sql
        assert "sehir_ici_mesafe_km = :sehir" in str_sql

        assert params["otoban"] == 60.0
        assert params["sehir"] == 40.0
        assert params["id"] == lokasyon_id


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
            "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
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
