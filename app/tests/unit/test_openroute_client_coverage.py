"""
Unit tests for OpenRouteClient — targeting ≥75% coverage.

All HTTP calls are mocked; no real network I/O.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import RouteProcessingError
from app.infrastructure.routing.openroute_client import (
    OpenRouteClient,
    get_route_client,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(api_key: str = "test-key") -> OpenRouteClient:
    return OpenRouteClient(api_key=api_key)


def _make_breaker(delegate: bool = True):
    """Returns a MagicMock circuit breaker that delegates .call to the real fn."""
    breaker = MagicMock()
    if delegate:

        async def _delegate(func, *args, **kwargs):
            return await func(*args, **kwargs)

        breaker.call = AsyncMock(side_effect=_delegate)
    return breaker


def _make_api_response(status: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if body is not None:
        resp.json.return_value = body
    resp.text = "error"
    return resp


# ---------------------------------------------------------------------------
# _validate_coordinates
# ---------------------------------------------------------------------------


def test_validate_coordinates_valid_turkey():
    client = _make_client()
    assert client._validate_coordinates((40.0, 29.0), (39.9, 32.8)) is True


def test_validate_coordinates_lat_out_of_range():
    client = _make_client()
    # lat < 35 (outside Turkey bounding box)
    assert client._validate_coordinates((10.0, 29.0), (39.9, 32.8)) is False


def test_validate_coordinates_lon_out_of_range():
    client = _make_client()
    # lon > 46 (outside Turkey bounding box)
    assert client._validate_coordinates((40.0, 50.0), (39.9, 32.8)) is False


def test_validate_coordinates_wrong_length():
    client = _make_client()
    assert client._validate_coordinates((40.0,), (39.9, 32.8)) is False  # type: ignore


def test_validate_coordinates_not_tuple():
    client = _make_client()
    assert client._validate_coordinates("bad", (39.9, 32.8)) is False  # type: ignore


# ---------------------------------------------------------------------------
# get_distance — validation failures
# ---------------------------------------------------------------------------


async def test_get_distance_invalid_coords_returns_none():
    client = _make_client()
    result = await client.get_distance((0.0, 0.0), (39.9, 32.8))
    assert result is None


async def test_get_distance_no_api_key_no_cache_returns_none():
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction

    with patch.object(
        client, "_get_from_cache", new_callable=AsyncMock, return_value=None
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)
    assert result is None


# ---------------------------------------------------------------------------
# get_distance — happy path via _call_api mock
# ---------------------------------------------------------------------------


async def test_get_distance_api_success_returns_source_api():
    client = _make_client()
    breaker = _make_breaker()

    api_result = {
        "distance_km": 452.3,
        "duration_hours": 5.5,
        "ascent_m": 1200,
        "descent_m": 1100,
    }

    # RouteValidator is imported lazily inside the method → patch at source module
    with (
        patch(
            "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=None
        ),
        patch.object(client, "_save_to_cache", new_callable=AsyncMock),
        patch.object(
            client, "_call_api", new_callable=AsyncMock, return_value=api_result
        ),
        patch(
            "app.core.services.route_validator.RouteValidator.validate_and_correct",
            side_effect=lambda x: x,
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=False)

    assert result is not None
    assert result["source"] == "api"
    assert result["distance_km"] == 452.3


async def test_get_distance_cache_hit_returns_source_cache():
    client = _make_client()
    cached = {
        "distance_km": 100.0,
        "duration_hours": 1.5,
        "ascent_m": 0,
        "descent_m": 0,
    }

    with (
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=cached
        ),
        patch(
            "app.core.services.route_validator.RouteValidator.validate_and_correct",
            side_effect=lambda x: x,
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)

    assert result is not None
    assert result["source"] == "cache"
    assert result["distance_km"] == 100.0


# ---------------------------------------------------------------------------
# get_distance — circuit breaker open
# ---------------------------------------------------------------------------


async def test_get_distance_circuit_breaker_open_returns_none():
    from app.infrastructure.resilience.circuit_breaker import CircuitBreakerError

    client = _make_client()
    breaker = MagicMock()
    breaker.call = AsyncMock(side_effect=CircuitBreakerError("open"))

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
# _call_api — HTTP status error codes
# ---------------------------------------------------------------------------


async def test_call_api_403_raises_route_processing_error():
    client = _make_client()
    resp = _make_api_response(403)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((40.0, 29.0), (39.9, 32.8))

    assert exc_info.value.provider_status == 403


async def test_call_api_404_raises_route_processing_error():
    client = _make_client()
    resp = _make_api_response(404)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((40.0, 29.0), (39.9, 32.8))

    assert exc_info.value.provider_status == 404


async def test_call_api_429_raises_route_processing_error():
    client = _make_client()
    resp = _make_api_response(429)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((40.0, 29.0), (39.9, 32.8))

    assert exc_info.value.provider_status == 429


async def test_call_api_500_raises_route_processing_error():
    client = _make_client()
    resp = _make_api_response(500)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((40.0, 29.0), (39.9, 32.8))

    assert exc_info.value.provider_status == 500


async def test_call_api_200_success_parses_result():
    client = _make_client()
    body = {
        "routes": [
            {
                "summary": {
                    "distance": 452300,
                    "duration": 19800,
                    "ascent": 1200,
                    "descent": 1100,
                },
            }
        ]
    }
    resp = _make_api_response(200, body)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    result = await client._call_api((40.0, 29.0), (39.9, 32.8), include_details=False)

    assert result is not None
    assert result["distance_km"] == pytest.approx(452.3, abs=0.1)
    assert result["duration_hours"] == pytest.approx(5.5, abs=0.1)
    assert result["ascent_m"] == 1200
    assert result["descent_m"] == 1100


async def test_call_api_200_with_geometry_polyline_string():
    """Geometry as polyline string triggers PolylineDecoder path."""
    client = _make_client()
    body = {
        "routes": [
            {
                "summary": {
                    "distance": 100000,
                    "duration": 3600,
                    "ascent": 500,
                    "descent": 400,
                },
                "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",  # encoded polyline string
                "extras": {},
            }
        ]
    }
    resp = _make_api_response(200, body)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with (
        patch(
            "app.infrastructure.routing.openroute_client.PolylineDecoder.decode",
            return_value=[(40.0, 29.0), (39.5, 30.0)],
        ),
        patch(
            "app.infrastructure.routing.openroute_client.route_analyzer.analyze_segments",
            return_value={"highway": {"flat": 50.0}},
        ),
    ):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=True
        )

    assert result is not None
    assert "details" in result


async def test_call_api_network_error_raises_route_processing_error():
    """ConnectError → wrapped as RouteProcessingError."""
    client = _make_client()

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError):
        await client._call_api((40.0, 29.0), (39.9, 32.8))


async def test_call_api_timeout_raises_route_processing_error():
    """ReadTimeout → wrapped as RouteProcessingError."""
    client = _make_client()

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    client._client = async_client_mock

    with pytest.raises(RouteProcessingError):
        await client._call_api((40.0, 29.0), (39.9, 32.8))


# ---------------------------------------------------------------------------
# geocode
# ---------------------------------------------------------------------------


async def test_geocode_empty_text_returns_none():
    client = _make_client()
    result = await client.geocode("")
    assert result is None


async def test_geocode_no_api_key_returns_none():
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction
    result = await client.geocode("Ankara")
    assert result is None


async def test_geocode_success_returns_lat_lon():
    client = _make_client()
    breaker = _make_breaker()

    geocode_body = {
        "features": [
            {
                "geometry": {
                    "coordinates": [32.8597, 39.9334]  # [lon, lat]
                }
            }
        ]
    }
    resp = _make_api_response(200, geocode_body)

    async_client_mock = AsyncMock()
    async_client_mock.get = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with patch(
        "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
        return_value=breaker,
    ):
        result = await client.geocode("Ankara")

    assert result is not None
    lat, lon = result
    assert lat == pytest.approx(39.9334, abs=0.001)
    assert lon == pytest.approx(32.8597, abs=0.001)


async def test_geocode_no_features_returns_none():
    client = _make_client()
    breaker = _make_breaker()

    resp = _make_api_response(200, {"features": []})

    async_client_mock = AsyncMock()
    async_client_mock.get = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with patch(
        "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
        return_value=breaker,
    ):
        result = await client.geocode("Unknown Place XYZ")

    assert result is None


async def test_geocode_api_error_status_returns_none():
    client = _make_client()
    breaker = _make_breaker()

    resp = _make_api_response(401)

    async_client_mock = AsyncMock()
    async_client_mock.get = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with patch(
        "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
        return_value=breaker,
    ):
        result = await client.geocode("Ankara")

    assert result is None


# ---------------------------------------------------------------------------
# get_route_client — singleton
# ---------------------------------------------------------------------------


async def test_get_route_client_returns_singleton():
    import app.infrastructure.routing.openroute_client as mod

    # Reset singleton for clean test
    mod._client_instance = None

    with patch(
        "app.infrastructure.routing.openroute_client.OpenRouteClient"
    ) as MockCls:
        instance = MagicMock()
        MockCls.return_value = instance

        c1 = await get_route_client()
        c2 = await get_route_client()

    assert c1 is c2
    MockCls.assert_called_once()

    # cleanup
    mod._client_instance = None


# ---------------------------------------------------------------------------
# db property (deprecated)
# ---------------------------------------------------------------------------


def test_db_property_returns_none():
    client = _make_client()
    assert client.db is None


# ---------------------------------------------------------------------------
# _call_api — lazy client creation
# ---------------------------------------------------------------------------


async def test_call_api_creates_httpx_client_if_none():
    """When _client is None, _call_api creates an httpx.AsyncClient."""
    client = _make_client()
    assert client._client is None

    body = {
        "routes": [
            {
                "summary": {
                    "distance": 50000,
                    "duration": 1800,
                    "ascent": 100,
                    "descent": 80,
                }
            }
        ]
    }
    resp = _make_api_response(200, body)

    with patch(
        "app.infrastructure.routing.openroute_client.httpx.AsyncClient"
    ) as MockHttpx:
        mock_http_instance = AsyncMock()
        mock_http_instance.post = AsyncMock(return_value=resp)
        MockHttpx.return_value = mock_http_instance

        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=False
        )

    assert result is not None
    MockHttpx.assert_called_once()


# ---------------------------------------------------------------------------
# get_distance — no api_key after cache miss (lines 117-118)
# ---------------------------------------------------------------------------


async def test_get_distance_no_api_key_after_cache_miss_returns_none():
    """api_key=None but use_cache=True and cache misses → None (line 117-118)."""
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction

    with patch.object(
        client, "_get_from_cache", new_callable=AsyncMock, return_value=None
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)

    assert result is None


# ---------------------------------------------------------------------------
# _call_api — no api_key returns None early
# ---------------------------------------------------------------------------


async def test_call_api_no_api_key_returns_none():
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction bypasses settings fallback
    result = await client._call_api((40.0, 29.0), (39.9, 32.8))
    assert result is None


# ---------------------------------------------------------------------------
# _call_api — geometry list path (already-decoded GeoJSON)
# ---------------------------------------------------------------------------


async def test_call_api_geometry_as_list():
    """geometry as a list (already decoded) should be used directly."""
    client = _make_client()
    body = {
        "routes": [
            {
                "summary": {
                    "distance": 80000,
                    "duration": 3000,
                    "ascent": 200,
                    "descent": 180,
                },
                "geometry": [[29.0, 40.0], [30.0, 39.5], [32.0, 39.0]],
                "extras": {"steepness": {}},
            }
        ]
    }
    resp = _make_api_response(200, body)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with patch(
        "app.infrastructure.routing.openroute_client.route_analyzer.analyze_segments",
        return_value={"highway": {"flat": 40.0}},
    ):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=True
        )

    assert result is not None
    assert "details" in result


# ---------------------------------------------------------------------------
# _call_api — polyline decode error (line 280-284)
# ---------------------------------------------------------------------------


async def test_call_api_polyline_decode_error_no_details():
    """If polyline decode raises, result still returns without details."""
    client = _make_client()
    body = {
        "routes": [
            {
                "summary": {
                    "distance": 80000,
                    "duration": 3000,
                    "ascent": 200,
                    "descent": 180,
                },
                "geometry": "INVALID_POLYLINE_STRING",
                "extras": {},
            }
        ]
    }
    resp = _make_api_response(200, body)

    async_client_mock = AsyncMock()
    async_client_mock.post = AsyncMock(return_value=resp)
    client._client = async_client_mock

    with patch(
        "app.infrastructure.routing.openroute_client.PolylineDecoder.decode",
        side_effect=Exception("bad polyline"),
    ):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=True
        )

    assert result is not None
    assert "details" not in result  # no details when decode fails


# ---------------------------------------------------------------------------
# _get_from_cache (lines 341-391)
# ---------------------------------------------------------------------------


async def test_get_from_cache_returns_none_when_no_row():
    """DB query returns no row → None."""
    client = _make_client()

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=select_result)

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=AsyncCtx,
        ),
        patch(
            "app.infrastructure.cache.redis_pubsub.get_redis_val",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is None


async def test_get_from_cache_returns_dict_when_row_exists():
    """DB row found → returns distance/duration dict."""
    client = _make_client()

    mock_row = MagicMock()
    mock_row.api_mesafe_km = 250.0
    mock_row.api_sure_saat = 3.5
    mock_row.ascent_m = 800
    mock_row.descent_m = 750
    mock_row.route_analysis = None

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is not None
    assert result["distance_km"] == 250.0
    assert result["duration_hours"] == 3.5


async def test_get_from_cache_includes_details_when_route_analysis_present():
    """DB row with route_analysis → includes details key."""
    client = _make_client()

    mock_row = MagicMock()
    mock_row.api_mesafe_km = 200.0
    mock_row.api_sure_saat = 2.0
    mock_row.ascent_m = 0
    mock_row.descent_m = 0
    mock_row.route_analysis = {"highway": {"flat": 100.0}}

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=select_result)

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is not None
    assert "details" in result


async def test_get_from_cache_exception_returns_none():
    """DB execute raises → returns None gracefully."""
    client = _make_client()

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=AsyncCtx,
        ),
        patch(
            "app.infrastructure.cache.redis_pubsub.get_redis_val",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is None


# ---------------------------------------------------------------------------
# _save_to_cache (lines 400-453)
# ---------------------------------------------------------------------------


async def test_save_to_cache_updates_existing_row():
    """When existing row found → UPDATE is executed."""
    client = _make_client()

    mock_existing = MagicMock()
    mock_existing.id = 5

    mock_session = MagicMock()
    # First call: SELECT → row found; second call: UPDATE
    select_result = MagicMock()
    select_result.fetchone.return_value = mock_existing
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    result_data = {
        "distance_km": 300.0,
        "duration_hours": 4.0,
        "ascent_m": 500,
        "descent_m": 450,
    }

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        await client._save_to_cache((40.0, 29.0), (39.9, 32.8), result_data)

    mock_session.commit.assert_called_once()


async def test_save_to_cache_no_existing_row_logs_debug():
    """When no existing row → no UPDATE, just a debug log."""
    client = _make_client()

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    result_data = {"distance_km": 300.0, "duration_hours": 4.0}

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        await client._save_to_cache((40.0, 29.0), (39.9, 32.8), result_data)

    # commit should NOT have been called (no update without existing row)
    mock_session.commit.assert_not_called()


async def test_save_to_cache_exception_does_not_raise():
    """Exception in DB → silently logged, no re-raise."""
    client = _make_client()

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        # Should not raise
        await client._save_to_cache((40.0, 29.0), (39.9, 32.8), {"distance_km": 100.0})
