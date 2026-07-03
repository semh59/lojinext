"""
Additional coverage tests for OpenRouteClient.

Targets missed lines:
  60        — __init__: no api_key warning
  141-142   — get_distance: generic exception from breaker.call_async
  164-169   — geocode: circuit breaker open + generic exception
  182       — _call_geocode_api: lazy client creation
  195-196   — _call_geocode_api: non-200 status
  213-214   — _call_geocode_api: request exception
  234       — _call_api: rate-limiting sleep path
  297-298   — _call_api: route_analysis error (analyze_segments raises)
  459-562   — update_route_distance: full path (row found, api success, update DB;
                 row not found; api returns None; exception)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.infrastructure.routing.openroute_client import OpenRouteClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(api_key: str = "test-key") -> OpenRouteClient:
    return OpenRouteClient(api_key=api_key)


def _make_breaker(delegate: bool = True):
    breaker = MagicMock()
    if delegate:

        async def _delegate(func, *args, **kwargs):
            return await func(*args, **kwargs)

        breaker.call_async = AsyncMock(side_effect=_delegate)
    return breaker


def _make_api_response(status: int, body=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if body is not None:
        resp.json.return_value = body
    resp.text = "error"
    return resp


class _AsyncCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *a):
        pass


# ---------------------------------------------------------------------------
# __init__: no api_key → warning logged (line 60)
# ---------------------------------------------------------------------------


def test_init_no_api_key_warns():
    """When no api_key is found, a warning is logged (line 60)."""
    with (
        patch("os.getenv", return_value=None),
        patch("app.infrastructure.routing.openroute_client.settings") as mock_settings,
    ):
        mock_settings.OPENROUTESERVICE_API_KEY = None
        mock_settings.OPENROUTE_API_BASE_URL = "https://api.openrouteservice.org/v2"
        client = OpenRouteClient(api_key=None)
    assert client.api_key is None


# ---------------------------------------------------------------------------
# get_distance: generic exception from breaker.call_async (lines 141-142)
# ---------------------------------------------------------------------------


async def test_get_distance_generic_exception_returns_none():
    """When breaker.call_async raises a non-CircuitBreakerError exception → None."""
    client = _make_client()

    breaker = MagicMock()
    breaker.call_async = AsyncMock(side_effect=RuntimeError("unexpected failure"))

    with (
        patch(
            "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=None
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=False)

    assert result is None


# ---------------------------------------------------------------------------
# geocode: circuit breaker open (lines 164-165)
# geocode: generic exception (lines 166-167)
# ---------------------------------------------------------------------------


async def test_geocode_circuit_breaker_open_returns_none():
    """CircuitBreakerError on geocode → returns None."""
    from app.infrastructure.resilience.circuit_breaker import CircuitBreakerError

    client = _make_client()
    breaker = MagicMock()
    breaker.call_async = AsyncMock(side_effect=CircuitBreakerError("geo cb open"))

    with patch(
        "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
        return_value=breaker,
    ):
        result = await client.geocode("Ankara")

    assert result is None


async def test_geocode_generic_exception_returns_none():
    """Non-CircuitBreaker exception from geocode breaker → returns None."""
    client = _make_client()
    breaker = MagicMock()
    breaker.call_async = AsyncMock(side_effect=RuntimeError("geo error"))

    with patch(
        "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
        return_value=breaker,
    ):
        result = await client.geocode("Ankara")

    assert result is None


# ---------------------------------------------------------------------------
# _call_geocode_api: lazy client creation (line 182)
# ---------------------------------------------------------------------------


async def test_call_geocode_api_creates_httpx_client_lazily():
    """_call_geocode_api creates AsyncClient when _client is None."""
    client = _make_client()
    assert client._client is None

    geocode_body = {"features": [{"geometry": {"coordinates": [32.8597, 39.9334]}}]}
    resp = _make_api_response(200, geocode_body)

    with patch(
        "app.infrastructure.routing.openroute_client.httpx.AsyncClient"
    ) as MockHttpx:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=resp)
        MockHttpx.return_value = mock_http

        result = await client._call_geocode_api("Ankara")

    MockHttpx.assert_called_once()
    assert result is not None
    lat, lon = result
    assert lat == pytest.approx(39.9334, abs=0.001)


# ---------------------------------------------------------------------------
# _call_geocode_api: non-200 status (lines 195-196)
# ---------------------------------------------------------------------------


async def test_call_geocode_api_non_200_returns_none():
    """Non-200 from geocode API → returns None."""
    client = _make_client()
    resp = _make_api_response(401)

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=resp)
    client._client = mock_http

    result = await client._call_geocode_api("Ankara")
    assert result is None


# ---------------------------------------------------------------------------
# _call_geocode_api: request exception (lines 213-214)
# ---------------------------------------------------------------------------


async def test_call_geocode_api_request_exception_returns_none():
    """httpx exception during geocode → returns None."""
    client = _make_client()

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    client._client = mock_http

    result = await client._call_geocode_api("Ankara")
    assert result is None


# ---------------------------------------------------------------------------
# _call_api: rate-limiting sleep path (line 234)
# ---------------------------------------------------------------------------


async def test_call_api_rate_limiting_sleep_when_too_fast():
    """When elapsed < MIN_REQUEST_INTERVAL, asyncio.sleep is called."""
    client = _make_client()
    # Force last_request_time to "now" so elapsed ≈ 0
    client._last_request_time = asyncio.get_event_loop().time()

    body = {
        "routes": [
            {
                "summary": {
                    "distance": 100000,
                    "duration": 3600,
                    "ascent": 0,
                    "descent": 0,
                }
            }
        ]
    }
    resp = _make_api_response(200, body)

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=resp)
    client._client = mock_http

    sleep_called = []

    async def patched_sleep(t):
        sleep_called.append(t)

    with patch("asyncio.sleep", side_effect=patched_sleep):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=False
        )

    assert result is not None
    assert len(sleep_called) > 0  # sleep was invoked


# ---------------------------------------------------------------------------
# _call_api: route analyze_segments raises (lines 297-298)
# ---------------------------------------------------------------------------


async def test_call_api_analyze_segments_exception_skips_details():
    """analyze_segments raising → details not included but result still returned."""
    client = _make_client()
    body = {
        "routes": [
            {
                "summary": {
                    "distance": 80000,
                    "duration": 3000,
                    "ascent": 200,
                    "descent": 150,
                },
                "geometry": [[29.0, 40.0], [30.0, 39.5]],
                "extras": {"steepness": {}},
            }
        ]
    }
    resp = _make_api_response(200, body)

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=resp)
    client._client = mock_http

    with patch(
        "app.infrastructure.routing.openroute_client.route_analyzer.analyze_segments",
        side_effect=RuntimeError("analysis fail"),
    ):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=True
        )

    assert result is not None
    assert "details" not in result  # analysis failed so no details


# ---------------------------------------------------------------------------
# update_route_distance — full success path (lines 459-562)
# ---------------------------------------------------------------------------


async def test_update_route_distance_success():
    """Full happy path: row found, get_distance returns result, DB updated."""
    client = _make_client()

    # Mock DB row
    mock_row = MagicMock()
    mock_row.cikis_lat = 40.0
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 39.9
    mock_row.varis_lon = 32.8

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()

    api_result = {
        "distance_km": 452.3,
        "duration_hours": 5.5,
        "ascent_m": 1200,
        "descent_m": 1100,
        "details": {"highway": {"flat": 200.0}, "other": {"flat": 50.0}},
        "source": "api",
    }

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=lambda: _AsyncCtx(mock_session),
        ),
        patch.object(
            client, "get_distance", new_callable=AsyncMock, return_value=api_result
        ),
    ):
        result = await client.update_route_distance(lokasyon_id=1)

    assert result is not None
    assert result["distance_km"] == 452.3
    mock_session.commit.assert_awaited()


async def test_update_route_distance_row_not_found_returns_none():
    """When DB row not found → returns None."""
    client = _make_client()

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=select_result)

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=lambda: _AsyncCtx(mock_session),
    ):
        result = await client.update_route_distance(lokasyon_id=999)

    assert result is None


async def test_update_route_distance_missing_coordinates_returns_none():
    """Row found but coordinates are None → returns None."""
    client = _make_client()

    mock_row = MagicMock()
    mock_row.cikis_lat = None  # missing coordinate
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 39.9
    mock_row.varis_lon = 32.8

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=lambda: _AsyncCtx(mock_session),
    ):
        result = await client.update_route_distance(lokasyon_id=2)

    assert result is None


async def test_update_route_distance_api_returns_none():
    """get_distance returns None → returns None."""
    client = _make_client()

    mock_row = MagicMock()
    mock_row.cikis_lat = 40.0
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 39.9
    mock_row.varis_lon = 32.8

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=lambda: _AsyncCtx(mock_session),
        ),
        patch.object(client, "get_distance", new_callable=AsyncMock, return_value=None),
    ):
        result = await client.update_route_distance(lokasyon_id=3)

    assert result is None


async def test_update_route_distance_exception_returns_none():
    """DB exception → returns None gracefully."""
    client = _make_client()

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=lambda: _AsyncCtx(mock_session),
    ):
        result = await client.update_route_distance(lokasyon_id=4)

    assert result is None


async def test_update_route_distance_no_details_key():
    """get_distance result without details key → otoban/sehir_ici default to 0."""
    client = _make_client()

    mock_row = MagicMock()
    mock_row.cikis_lat = 40.0
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 39.9
    mock_row.varis_lon = 32.8

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()

    api_result = {
        "distance_km": 200.0,
        "duration_hours": 3.0,
        "ascent_m": 500,
        "descent_m": 400,
        # No 'details' key
        "source": "api",
    }

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=lambda: _AsyncCtx(mock_session),
        ),
        patch.object(
            client, "get_distance", new_callable=AsyncMock, return_value=api_result
        ),
    ):
        result = await client.update_route_distance(lokasyon_id=5)

    assert result is not None
    assert result["distance_km"] == 200.0
