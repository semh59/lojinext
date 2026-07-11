"""container_health.get_container_status — real httpx client wired to an
httpx.MockTransport (exercises the actual request/response/JSON-decode path,
not a mocked module) standing in for docker-socket-proxy, since spinning up
a real Docker daemon in unit tests isn't practical."""

from unittest.mock import patch

import httpx
import pytest

from app.infrastructure.monitoring.container_health import get_container_status

pytestmark = pytest.mark.unit

_RealAsyncClient = httpx.AsyncClient


def _client_with(handler):
    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealAsyncClient(*args, **kwargs)

    return _factory


@pytest.mark.asyncio
async def test_running_healthy_container():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"State": "running", "Status": "Up 2 hours (healthy)"}],
        )

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-ops-bot")

    assert result == {"found": True, "running": True, "health": "healthy"}


@pytest.mark.asyncio
async def test_running_no_healthcheck_defined():
    """Driver bot has no HEALTHCHECK in docker-compose.yml — Status has no
    parenthetical suffix at all."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"State": "running", "Status": "Up 3 days"}],
        )

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-driver-bot")

    assert result == {"found": True, "running": True, "health": None}


@pytest.mark.asyncio
async def test_unhealthy_container():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"State": "running", "Status": "Up 5 minutes (unhealthy)"}],
        )

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-ops-bot")

    assert result == {"found": True, "running": True, "health": "unhealthy"}


@pytest.mark.asyncio
async def test_stopped_container():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"State": "exited", "Status": "Exited (1) 10 minutes ago"}],
        )

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-driver-bot")

    assert result == {"found": True, "running": False, "health": None}


@pytest.mark.asyncio
async def test_no_matching_container():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-driver-bot")

    assert result == {"found": False, "running": False, "health": None}


@pytest.mark.asyncio
async def test_proxy_unreachable_never_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-driver-bot")

    assert result == {"found": False, "running": False, "health": None}


@pytest.mark.asyncio
async def test_proxy_5xx_never_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    with patch("httpx.AsyncClient", new=_client_with(handler)):
        result = await get_container_status("telegram-driver-bot")

    assert result == {"found": False, "running": False, "health": None}
