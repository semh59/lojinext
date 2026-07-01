"""Coverage tests for app/infrastructure/middleware/rate_limit_middleware.py.

Tests cover:
- _get_client_ip (X-Forwarded-For, direct client, unknown)
- _increment_memory (first hit, within window, window expiry)
- _evict_expired
- _increment_redis (success, redis=None, exception)
- dispatch (skip paths, dev env, pytest env, rate limited, cleanup trigger)
- RateLimitMiddleware initialisation
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from app.infrastructure.middleware.rate_limit_middleware import RateLimitMiddleware

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


# ─── _increment_memory ────────────────────────────────────────────────────────


def test_increment_memory_first_hit():
    mw = _make_middleware()
    count = mw._increment_memory("bucket1")
    assert count == 1


def test_increment_memory_increments_within_window():
    mw = _make_middleware()
    mw._increment_memory("b")
    mw._increment_memory("b")
    count = mw._increment_memory("b")
    assert count == 3


def test_increment_memory_resets_after_window():
    mw = _make_middleware()
    # Manually set an old window start
    mw._mem_counts["b"] = (50, time.time() - 61)
    count = mw._increment_memory("b")
    assert count == 1  # fresh window


def test_increment_memory_independent_buckets():
    mw = _make_middleware()
    for _ in range(5):
        mw._increment_memory("alpha")
    count = mw._increment_memory("beta")
    assert count == 1


# ─── _evict_expired ───────────────────────────────────────────────────────────


def test_evict_expired_removes_stale_buckets():
    mw = _make_middleware()
    now = time.time()
    mw._mem_counts["old"] = (5, now - 100)  # expired
    mw._mem_counts["new"] = (3, now - 10)  # fresh

    mw._evict_expired(now)

    assert "old" not in mw._mem_counts
    assert "new" in mw._mem_counts


def test_evict_expired_empty_dict():
    mw = _make_middleware()
    mw._evict_expired(time.time())  # must not raise


def test_evict_expired_boundary_not_removed():
    mw = _make_middleware()
    now = time.time()
    # window_size=60; exactly 59 seconds old → NOT expired
    mw._mem_counts["borderline"] = (1, now - 59)
    mw._evict_expired(now)
    assert "borderline" in mw._mem_counts


# ─── _increment_redis ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_increment_redis_no_redis():
    """mgr._redis is None → returns 0."""
    mw = _make_middleware()

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value._redis = None
        result = await mw._increment_redis("bucket")

    assert result == 0


@pytest.mark.asyncio
async def test_increment_redis_success_first_call():
    """First INCR (count==1) → sets expiry."""
    mw = _make_middleware()

    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
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

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value._redis = mock_redis
        result = await mw._increment_redis("b2")

    assert result == 5
    mock_redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_increment_redis_exception_returns_zero():
    """Redis exception → returns 0 (fallback to memory)."""
    mw = _make_middleware()

    with patch(
        "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
        side_effect=Exception("Redis unreachable"),
    ):
        result = await mw._increment_redis("b3")

    assert result == 0


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
async def test_dispatch_memory_fallback_when_redis_zero():
    """Redis returns 0 → uses memory counter. Below limit → 200."""
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
                mw, "_increment_redis", new_callable=AsyncMock, return_value=0
            ):
                with patch.object(mw, "_increment_memory", return_value=1):
                    response = await mw.dispatch(req, call_next)

        assert response.status_code == 200
    finally:
        if original_pytest is not None:
            sys.modules["pytest"] = original_pytest


@pytest.mark.asyncio
async def test_dispatch_evict_triggered_every_500():
    """After 500 dispatches, _evict_expired is called."""
    import sys

    async def noop_app(scope, receive, send):
        pass

    mw = RateLimitMiddleware(noop_app, requests_per_minute=100)
    mw._dispatch_count = 499

    original_pytest = sys.modules.get("pytest")
    evict_called = []
    original_evict = mw._evict_expired

    try:
        del sys.modules["pytest"]

        async def call_next(r):
            resp = MagicMock()
            resp.status_code = 200
            return resp

        mw._evict_expired = lambda now: evict_called.append(now)

        with patch("app.config.settings") as ms:
            ms.ENVIRONMENT = "production"

            with patch.object(
                mw, "_increment_redis", new_callable=AsyncMock, return_value=1
            ):
                req = _make_request(path="/api/v1/something")
                await mw.dispatch(req, call_next)

    finally:
        mw._evict_expired = original_evict
        if original_pytest is not None:
            sys.modules["pytest"] = original_pytest

    assert len(evict_called) == 1


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
