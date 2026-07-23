"""
Unit tests for AsyncRateLimiter, RateLimiterRegistry, and rate_limited decorator.

FAZ2 (`TASKS/faz2-guvenlik-state-redis.md`): `AsyncRateLimiter` moved from a
per-process token bucket to a Redis-backed fixed-window counter (INCR+EXPIRE),
fail-closed on Redis outage. Tests drive it against an in-memory fake Redis
(`_FakeAsyncRedis`) instead of manipulating token-bucket internals.

The autouse fixture `reset_rate_limiter_registry` in conftest.py clears the
`RateLimiterRegistry` before and after every test, so tests are isolated.
"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from v2.modules.platform_infra.resilience.rate_limiter import (
    AsyncRateLimiter,
    RateLimiterDependency,
    RateLimiterRegistry,
)

pytestmark = pytest.mark.unit


class _FakeAsyncRedis:
    """Minimal in-memory stand-in for `redis.asyncio.Redis` — INCR/EXPIRE/TTL
    only, enough to drive `AsyncRateLimiter`'s fixed-window counter."""

    def __init__(self):
        self._counters: dict = {}

    async def incr(self, key):
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key, seconds):  # noqa: ARG002
        return True

    async def ttl(self, key):  # noqa: ARG002
        return 5

    def reset_key(self, key: str) -> None:
        """Test helper: simulate the fixed window's EXPIRE elapsing."""
        self._counters.pop(key, None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = _FakeAsyncRedis()
    monkeypatch.setattr(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        lambda: type("Mgr", (), {"_redis": fake})(),
    )
    return fake


def _make_request(
    auth_header: str | None = None, client_host: str = "127.0.0.1"
) -> Request:
    """Minimal Starlette Request with optional Authorization header, no mocking."""
    headers = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode("utf-8")))
    scope = {
        "type": "http",
        "headers": headers,
        "client": (client_host, 12345),
        "method": "POST",
        "path": "/test",
    }
    return Request(scope)


class TestAsyncRateLimiter:
    async def test_basic_initialization(self):
        """Limiter initialises with correct rate/period/name."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0, name="init_test")

        assert limiter.rate == 10.0
        assert limiter.period == 1.0
        assert limiter.name == "init_test"

    async def test_happy_path_acquire_consumes_slot(self):
        """acquire() succeeds when the window has capacity."""
        limiter = AsyncRateLimiter(rate=5.0, period=1.0, name="happy")

        await limiter.acquire()  # must not raise

    async def test_error_handling_rate_limit_exceeded(self, fake_redis):
        """acquire() raises HTTP 429 once the window's count exceeds rate."""
        limiter = AsyncRateLimiter(rate=1.0, period=1.0, name="exhausted")
        fake_redis._counters["ratelimit:exhausted"] = 1  # already at capacity

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 429

    async def test_edge_case_single_slot_window(self):
        """rate=1 allows first call, rejects second in the same window."""
        limiter = AsyncRateLimiter(rate=1.0, period=1.0, name="single_slot")

        await limiter.acquire()  # first: ok

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()  # second: window already at capacity

        assert exc_info.value.status_code == 429

    async def test_window_resets_after_expire(self, fake_redis):
        """Once the fixed window's key expires, a fresh slot is available."""
        limiter = AsyncRateLimiter(rate=1.0, period=1.0, name="resets")

        await limiter.acquire()  # consumes the single slot
        fake_redis.reset_key("ratelimit:resets")  # simulate EXPIRE elapsing

        await limiter.acquire()  # must not raise — fresh window

    async def test_integration_with_mock(self):
        """Context manager __aenter__/__aexit__ calls acquire and completes."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0, name="ctx_mgr")

        async with limiter:
            pass  # should not raise

    async def test_return_type_validation(self):
        """acquire() returns None (implicitly) on success."""
        limiter = AsyncRateLimiter(rate=5.0, period=1.0, name="return_type")
        result = await limiter.acquire()
        assert result is None

    def test_service_exists(self):
        """AsyncRateLimiter class is importable."""
        from v2.modules.platform_infra.resilience.rate_limiter import (
            AsyncRateLimiter,  # noqa: F401
        )

        assert AsyncRateLimiter is not None

    async def test_retry_after_header_present_on_429(self, fake_redis):
        """429 response includes a Retry-After header."""
        limiter = AsyncRateLimiter(rate=1.0, period=10.0, name="retry_after")
        fake_redis._counters["ratelimit:retry_after"] = 1

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert "Retry-After" in exc_info.value.headers

    async def test_redis_down_raises_503(self, monkeypatch):
        """No Redis client configured → fail-closed 503, not a silent pass."""
        monkeypatch.setattr(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
            lambda: type("Mgr", (), {"_redis": None})(),
        )
        limiter = AsyncRateLimiter(rate=10.0, period=1.0, name="redis_down")

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 503

    async def test_redis_error_raises_503(self, monkeypatch):
        """Redis reachable but erroring (e.g. connection drop mid-call) also
        fails closed, not open."""
        from unittest.mock import AsyncMock

        broken = AsyncMock()
        broken.incr.side_effect = ConnectionError("boom")
        monkeypatch.setattr(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
            lambda: type("Mgr", (), {"_redis": broken})(),
        )
        limiter = AsyncRateLimiter(rate=10.0, period=1.0, name="redis_error")

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 503

    async def test_four_workers_share_one_threshold(self, fake_redis):
        """MEMORY §4.1 acceptance test: 4 separate `AsyncRateLimiter` instances
        for the SAME logical name (simulating 4 uvicorn workers, each with its
        own `RateLimiterRegistry` in its own process) must share one Redis
        counter — a limit of 4 is exhausted by the 5th request TOTAL, not the
        5th request to any single "worker" (pre-fix: each worker had its own
        4-slot bucket, so 4 workers together effectively allowed ~16)."""
        workers = [
            AsyncRateLimiter(rate=4.0, period=60.0, name="shared_bucket")
            for _ in range(4)
        ]

        for i in range(4):
            await workers[i % 4].acquire()  # round-robin, all 4 succeed

        with pytest.raises(HTTPException) as exc_info:
            await workers[0].acquire()  # 5th request total -> over the shared limit
        assert exc_info.value.status_code == 429


class TestRateLimiterRegistry:
    async def test_get_creates_new_limiter(self):
        """Registry creates a new limiter on first get."""
        limiter = await RateLimiterRegistry.get("test_api", rate=5.0)

        assert limiter is not None
        assert isinstance(limiter, AsyncRateLimiter)
        assert limiter.rate == 5.0
        assert limiter.name == "test_api"

    async def test_get_returns_same_instance(self):
        """Registry returns the same limiter for the same name."""
        limiter1 = await RateLimiterRegistry.get("same_api", rate=3.0)
        limiter2 = await RateLimiterRegistry.get("same_api", rate=3.0)

        assert limiter1 is limiter2

    def test_get_sync_creates_limiter(self):
        """get_sync() creates a limiter without an event loop."""
        limiter = RateLimiterRegistry.get_sync("sync_api", rate=2.0)

        assert isinstance(limiter, AsyncRateLimiter)
        assert limiter.rate == 2.0

    async def test_registry_isolation_between_names(self):
        """Different names get different limiter instances (and thus different
        Redis keys — this is the cross-worker correctness property)."""
        limiter_a = await RateLimiterRegistry.get("api_a", rate=5.0)
        limiter_b = await RateLimiterRegistry.get("api_b", rate=10.0)

        assert limiter_a is not limiter_b
        assert limiter_a.rate == 5.0
        assert limiter_b.rate == 10.0
        assert limiter_a.name != limiter_b.name


class TestRateLimiterDependency:
    async def test_dependency_acquires_token(self):
        """RateLimiterDependency.__call__ acquires a slot from the limiter."""
        dep = RateLimiterDependency(key="dep_test", rate=10.0, period=1.0)

        # Should complete without raising (capacity available)
        await dep()

    async def test_dependency_raises_on_exhausted_bucket(self, fake_redis):
        """RateLimiterDependency raises 429 when the window is exhausted."""
        dep = RateLimiterDependency(key="dep_exhausted", rate=1.0, period=1.0)
        fake_redis._counters["ratelimit:dep_exhausted"] = 1

        with pytest.raises(HTTPException) as exc_info:
            await dep()

        assert exc_info.value.status_code == 429


class TestRateLimiterDependencyPerUser:
    """per_user=True opt-in — bucket-per-caller-identity (2026-07-05 tespiti)."""

    async def test_default_per_user_false_shares_one_bucket_across_callers(self):
        """per_user default False: davranış AYNEN — tek global bucket."""
        dep = RateLimiterDependency(key="per_user_default_off", rate=1.0, period=10.0)
        req_a = _make_request("Bearer tokenA")
        req_b = _make_request("Bearer tokenB")

        await dep(req_a)  # consumes the single global slot

        with pytest.raises(HTTPException) as exc_info:
            await dep(req_b)  # same global bucket -> exhausted regardless of caller
        assert exc_info.value.status_code == 429

    async def test_per_user_same_token_second_request_429(self):
        """per_user=True: aynı token'ın 2. isteği aynı bucket'ı tüketir -> 429."""
        dep = RateLimiterDependency(
            key="per_user_same_token", rate=1.0, period=10.0, per_user=True
        )
        req = _make_request("Bearer token-same")

        await dep(req)  # first request for this token succeeds

        with pytest.raises(HTTPException) as exc_info:
            await dep(req)  # second request, same token, same bucket -> 429
        assert exc_info.value.status_code == 429

    async def test_per_user_different_tokens_get_separate_buckets(self):
        """per_user=True: farklı token'lar ayrı bucket -> ikisi de ok (raise etmez)."""
        dep = RateLimiterDependency(
            key="per_user_diff_tokens", rate=1.0, period=10.0, per_user=True
        )
        req_a = _make_request("Bearer token-A")
        req_b = _make_request("Bearer token-B")

        await dep(req_a)  # bucket A: ok
        await dep(req_b)  # bucket B: separate bucket, also ok (proof of isolation)

    async def test_per_user_falls_back_to_client_host_without_auth_header(self):
        """Authorization header yoksa request.client.host bucket kimliği olur."""
        dep = RateLimiterDependency(
            key="per_user_no_auth", rate=1.0, period=10.0, per_user=True
        )
        req = _make_request(auth_header=None, client_host="10.0.0.5")

        await dep(req)  # first request from this host: ok

        with pytest.raises(HTTPException) as exc_info:
            await dep(req)  # second from same host -> same bucket -> 429
        assert exc_info.value.status_code == 429

    def test_bucket_key_ignores_request_when_per_user_false(self):
        dep = RateLimiterDependency(key="bucket_key_test", per_user=False)
        req = _make_request("Bearer whatever")
        assert dep._bucket_key(req) == "bucket_key_test"

    def test_bucket_key_derives_from_auth_header_when_per_user_true(self):
        dep = RateLimiterDependency(key="bucket_key_test2", per_user=True)
        req = _make_request("Bearer some-token")
        key1 = dep._bucket_key(req)
        key2 = dep._bucket_key(_make_request("Bearer some-token"))
        key3 = dep._bucket_key(_make_request("Bearer other-token"))
        assert key1 == key2  # same token -> same derived bucket key
        assert key1 != key3  # different token -> different bucket key
        assert key1.startswith("bucket_key_test2:")
