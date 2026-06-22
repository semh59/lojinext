"""
Unit tests for AsyncRateLimiter, RateLimiterRegistry, and rate_limited decorator.

The autouse fixture `reset_rate_limiter_registry` in conftest.py clears the
registry before and after every test, so tests are isolated.
"""

import pytest
from fastapi import HTTPException

from app.infrastructure.resilience.rate_limiter import (
    AsyncRateLimiter,
    RateLimiterDependency,
    RateLimiterRegistry,
)

pytestmark = pytest.mark.unit


class TestAsyncRateLimiter:
    async def test_basic_initialization(self):
        """Limiter initialises with correct rate/period and full token bucket."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0)

        assert limiter.rate == 10.0
        assert limiter.period == 1.0
        assert limiter.tokens == 10.0
        assert limiter._last_update is None  # lazy init

    async def test_happy_path_acquire_consumes_token(self):
        """acquire() succeeds when tokens are available and decrements bucket."""
        limiter = AsyncRateLimiter(rate=5.0, period=1.0)
        initial_tokens = limiter.tokens

        await limiter.acquire()

        # One token consumed (approximately — may vary by tiny elapsed time)
        assert limiter.tokens < initial_tokens

    async def test_error_handling_rate_limit_exceeded(self):
        """acquire() raises HTTP 429 when token bucket is empty."""
        limiter = AsyncRateLimiter(rate=1.0, period=1.0)
        limiter.tokens = 0.0  # exhaust bucket

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 429

    async def test_edge_case_single_token_bucket(self):
        """Bucket of 1 allows first call, rejects second without refill."""
        limiter = AsyncRateLimiter(rate=1.0, period=1.0)

        # First acquire should succeed
        await limiter.acquire()

        # Tokens depleted — second should fail
        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert exc_info.value.status_code == 429

    async def test_edge_case_none_last_update_lazy_init(self):
        """_last_update starts as None; first acquire initialises it."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0)
        assert limiter._last_update is None

        await limiter.acquire()

        assert limiter._last_update is not None

    async def test_integration_with_mock(self):
        """Context manager __aenter__/__aexit__ calls acquire and completes."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0)

        async with limiter:
            pass  # should not raise

        # A token was consumed
        assert limiter.tokens < 10.0

    async def test_return_type_validation(self):
        """acquire() returns None (implicitly) on success."""
        limiter = AsyncRateLimiter(rate=5.0, period=1.0)
        result = await limiter.acquire()
        assert result is None

    def test_service_exists(self):
        """AsyncRateLimiter class is importable."""
        from app.infrastructure.resilience.rate_limiter import (
            AsyncRateLimiter,  # noqa: F401
        )

        assert AsyncRateLimiter is not None

    async def test_retry_after_header_present_on_429(self):
        """429 response includes a Retry-After header."""
        limiter = AsyncRateLimiter(rate=1.0, period=10.0)
        limiter.tokens = 0.0

        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()

        assert "Retry-After" in exc_info.value.headers

    async def test_token_refill_over_time(self):
        """Tokens refill proportionally to elapsed time."""
        limiter = AsyncRateLimiter(rate=10.0, period=1.0)
        limiter.tokens = 0.0

        # Manually backdate _last_update by 0.5 s so refill occurs on next acquire
        import time

        limiter._last_update = time.monotonic() - 0.5

        # Should have approximately 5 tokens refilled — enough for one acquire
        await limiter.acquire()

        # If we get here without 429, refill worked
        assert limiter.tokens >= 0.0


class TestRateLimiterRegistry:
    async def test_get_creates_new_limiter(self):
        """Registry creates a new limiter on first get."""
        limiter = await RateLimiterRegistry.get("test_api", rate=5.0)

        assert limiter is not None
        assert isinstance(limiter, AsyncRateLimiter)
        assert limiter.rate == 5.0

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
        """Different names get different limiter instances."""
        limiter_a = await RateLimiterRegistry.get("api_a", rate=5.0)
        limiter_b = await RateLimiterRegistry.get("api_b", rate=10.0)

        assert limiter_a is not limiter_b
        assert limiter_a.rate == 5.0
        assert limiter_b.rate == 10.0


class TestRateLimiterDependency:
    async def test_dependency_acquires_token(self):
        """RateLimiterDependency.__call__ acquires a token from the limiter."""
        dep = RateLimiterDependency(key="dep_test", rate=10.0, period=1.0)

        # Should complete without raising (tokens available)
        await dep()

    async def test_dependency_raises_on_exhausted_bucket(self):
        """RateLimiterDependency raises 429 when bucket is exhausted."""
        dep = RateLimiterDependency(key="dep_exhausted", rate=1.0, period=1.0)

        # Exhaust bucket first
        limiter = await RateLimiterRegistry.get("dep_exhausted", rate=1.0, period=1.0)
        limiter.tokens = 0.0

        with pytest.raises(HTTPException) as exc_info:
            await dep()

        assert exc_info.value.status_code == 429
