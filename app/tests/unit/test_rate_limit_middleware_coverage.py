"""Coverage tests for v2/modules/platform_infra/middleware/rate_limit_middleware.py.

FAZ2 (`TASKS/faz2-guvenlik-state-redis.md`): the silent in-memory fallback
(`_increment_memory`/`_mem_counts`/`_evict_expired`) was removed — Redis
unavailability now fails closed (503 + CRITICAL log), it no longer falls
through to a per-process counter.

Tests cover:
- _get_client_ip (X-Forwarded-For, direct client, unknown)
- _increment_redis (success, redis=None raises, exception propagates)
- dispatch (skip paths, dev env, pytest env, rate limited, Redis-down 503)
- RateLimitMiddleware initialisation
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from v2.modules.platform_infra.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
)

pytestmark = pytest.mark.unit


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_request(path="/api/v1/trips", client_ip="10.0.0.1", headers=None):
    """Create a minimal Starlette Request-like mock."""
    req = MagicMock(spec=Request)
    req.url.path = path
    req.client.host = client_ip
    req.headers = MagicMock()
    req.headers.get = MagicMock(return_value=None)
    req.state = MagicMock()
    req.state.user_id = None
    if headers:
        req.headers.get = lambda key, default=None: headers.get(key, default)
    return req


def _make_middleware():
    """Instantiate middleware with a no-op ASGI app."""

    async def noop_app(scope, receive, send):
        pass

    return RateLimitMiddleware(noop_app, requests_per_minute=10)


# ─── _get_client_ip ───────────────────────────────────────────────────────────


def test_get_client_ip_uses_x_forwarded_for():
    mw = _make_middleware()
    req = _make_request(headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.1"})
    assert mw._get_client_ip(req) == "203.0.113.1"


def test_get_client_ip_trims_whitespace():
    mw = _make_middleware()
    req = _make_request(headers={"X-Forwarded-For": "  1.2.3.4  , 5.6.7.8"})
    assert mw._get_client_ip(req) == "1.2.3.4"


def test_get_client_ip_direct_client():
    mw = _make_middleware()
    req = _make_request(client_ip="192.168.1.1")
    # No X-Forwarded-For header
    assert mw._get_client_ip(req) == "192.168.1.1"


def test_get_client_ip_no_client():
    mw = _make_middleware()
    req = MagicMock(spec=Request)
    req.headers.get = MagicMock(return_value=None)
    req.client = None
    assert mw._get_client_ip(req) == "unknown"


# ─── _increment_redis ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_increment_redis_no_redis_raises():
    """mgr._redis is None → raises (caller must fail closed, no silent 0)."""
    mw = _make_middleware()

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value._redis = None
        with pytest.raises(RuntimeError):
            await mw._increment_redis("bucket")


@pytest.mark.asyncio
async def test_increment_redis_success_first_call():
    """First INCR (count==1) → sets expiry."""
    mw = _make_middleware()

    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value._redis = mock_redis
        result = await mw._increment_redis("bucket")

    assert result == 1
    mock_redis.expire.assert_called_once_with("rl:bucket", mw.window_size)


@pytest.mark.asyncio
async def test_increment_redis_subsequent_calls_no_expire():
    """Count > 1 → expire NOT called again."""
    mw = _make_middleware()

    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=5)
    mock_redis.expire = AsyncMock()

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value._redis = mock_redis
        result = await mw._increment_redis("b2")

    assert result == 5
    mock_redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_increment_redis_exception_propagates():
    """Redis exception → propagates (dispatch() is the one that fails closed)."""
    mw = _make_middleware()

    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        side_effect=Exception("Redis unreachable"),
    ):
        with pytest.raises(Exception, match="Redis unreachable"):
            await mw._increment_redis("b3")


# ─── dispatch ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_skips_docs_path():
    """Requests to /docs are passed through without rate checking.
    In test env, pytest is in sys.modules → dispatch always skips → call_next called."""
    call_next_called = []

    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app, requests_per_minute=10)
    req = _make_request(path="/docs")

    async def call_next(r):
        call_next_called.append(True)
        resp = MagicMock()
        resp.status_code = 200
        return resp

    await mw.dispatch(req, call_next)
    assert call_next_called  # always passes through in test env


@pytest.mark.asyncio
async def test_dispatch_rate_limits_when_over_limit():
    """When Redis returns count > limit, dispatch returns 429."""
    import sys

    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app, requests_per_minute=10)
    req = _make_request(path="/api/v1/trips")

    original_pytest = sys.modules.get("pytest")
    try:
        # Remove pytest from modules so the middleware doesn't short-circuit
        del sys.modules["pytest"]

        async def call_next(r):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        # Patch settings at the source where it's imported inside dispatch
        with patch("app.config.settings") as ms:
            ms.ENVIRONMENT = "production"

            with patch.object(
                mw, "_increment_redis", new_callable=AsyncMock, return_value=11
            ):
                response = await mw.dispatch(req, call_next)

        assert response.status_code == 429
        # 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): 429 yanıtı
        # projenin standart hata zarfını ({"error":{"code","message",
        # "trace_id"}}) bypass ediyordu (sadece {"detail": "..."} dönüyordu)
        # — frontend'in genel hata-zarfı ayrıştırıcısı bunu tanımıyordu,
        # kullanıcı rate-limit'e takılınca hiçbir geri bildirim almıyordu.
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert "error" in body, (
            f"429 yanıtı standart hata zarfını kullanmalı ({{'error': "
            f"{{...}}}}), ama {body!r} döndü."
        )
        assert body["error"]["code"] == "RATE_LIMITED"
        assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    finally:
        if original_pytest is not None:
            sys.modules["pytest"] = original_pytest


@pytest.mark.asyncio
async def test_dispatch_fails_closed_when_redis_unavailable():
    """FAZ2: Redis outage → 503 with the standard error envelope, not a
    silent pass-through to an in-memory counter."""
    import sys

    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app, requests_per_minute=10)
    req = _make_request(path="/api/v1/data")

    original_pytest = sys.modules.get("pytest")
    try:
        del sys.modules["pytest"]

        async def call_next(r):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        with patch("app.config.settings") as ms:
            ms.ENVIRONMENT = "production"

            with patch.object(
                mw,
                "_increment_redis",
                new_callable=AsyncMock,
                side_effect=RuntimeError("no redis client configured"),
            ), patch(
                "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
            ) as mock_aemit:
                response = await mw.dispatch(req, call_next)

        assert response.status_code == 503
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert body["error"]["code"] == "RATE_LIMITER_UNAVAILABLE"
        mock_aemit.assert_called_once()
    finally:
        if original_pytest is not None:
            sys.modules["pytest"] = original_pytest


# ─── Initialization ───────────────────────────────────────────────────────────


def test_middleware_default_limit():
    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app)
    assert mw.requests_per_minute == 60
    assert mw.window_size == 60


def test_middleware_custom_limit():
    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app, requests_per_minute=120)
    assert mw.requests_per_minute == 120
