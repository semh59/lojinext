"""
Additional coverage tests for OpenRouteClient.

Targets missed lines:
  60        — __init__: no api_key warning
  141-142   — get_distance: generic exception from breaker.call_async
  234       — _call_api: rate-limiting sleep path
  297-298   — _call_api: route_analysis error (analyze_segments raises)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from v2.modules.route_simulation.infrastructure.openroute_client import OpenRouteClient

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(api_key: str = "test-key") -> OpenRouteClient:
    client = OpenRouteClient(api_key=api_key)
    client.base_url = "http://localhost:9000/v2"
    client.geocode_url = "http://localhost:9000/geocode/search"
    return client


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
        patch(
            "v2.modules.route_simulation.infrastructure.openroute_client.settings"
        ) as mock_settings,
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
            "v2.modules.route_simulation.infrastructure.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=None
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=False)

    assert result is None


# ---------------------------------------------------------------------------
# _call_api: rate-limiting sleep path (line 234)
# ---------------------------------------------------------------------------


async def test_call_api_rate_limiting_sleep_when_too_fast():
    """When elapsed < MIN_REQUEST_INTERVAL, asyncio.sleep is called.
    0-mock epiği: gerçek stub'a gider, sadece asyncio.sleep gözlemlenir
    (gerçek rate-limit gecikmesi testi yavaşlatmasın diye patched — bu
    zamanlama davranışı, HTTP davranışı değil)."""
    client = _make_client()
    # Force last_request_time to "now" so elapsed ≈ 0
    client._last_request_time = asyncio.get_event_loop().time()

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
    """analyze_segments raising → details not included but result still
    returned. 0-mock epiği: gerçek stub'ın 777 sentinel senaryosu (liste
    geometry) kullanılır, sadece analyze_segments zorla raise ettirilir."""
    client = _make_client()

    with patch(
        "v2.modules.route_simulation.infrastructure.openroute_client.route_analyzer.analyze_segments",
        side_effect=RuntimeError("analysis fail"),
    ):
        result = await client._call_api((0.0, 0.0), (0.0, 777.0), include_details=True)

    assert result is not None
    assert "details" not in result  # analysis failed so no details
