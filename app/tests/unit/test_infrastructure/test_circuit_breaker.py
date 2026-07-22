"""
Unit tests for CircuitBreaker and CircuitBreakerRegistry.
Redis calls are mocked so no real Redis connection is needed.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.platform_infra.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_protected,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_breaker(name="test_cb", fail_max=3, reset_timeout=60.0):
    """Create a CircuitBreaker with a mocked Redis pubsub manager."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.incr = AsyncMock(return_value=1)

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=mock_redis,
    ):
        cb = CircuitBreaker(name=name, fail_max=fail_max, reset_timeout=reset_timeout)
    cb._redis = mock_redis
    return cb, mock_redis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    async def test_basic_initialization(self):
        """CircuitBreaker starts in CLOSED state with zero failures."""
        cb, _ = _make_breaker("init_test", fail_max=5, reset_timeout=30.0)

        assert cb.name == "init_test"
        assert cb.fail_max == 5
        assert cb.reset_timeout == 30.0
        assert cb._failure_count == 0
        assert cb._state == CircuitState.CLOSED

    async def test_happy_path(self):
        """Successful call returns result and keeps circuit CLOSED."""
        cb, mock_redis = _make_breaker("happy")
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        async def success_fn():
            return "ok"

        result = await cb.call(success_fn)

        assert result == "ok"
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0

    async def test_error_handling_opens_circuit(self):
        """After fail_max failures, circuit transitions to OPEN."""
        cb, mock_redis = _make_breaker("err_test", fail_max=3)

        # incr returns incrementing counts: 1, 2, 3
        mock_redis.incr = AsyncMock(side_effect=[1, 2, 3])
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        async def failing_fn():
            raise ConnectionError("boom")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(failing_fn)

        assert cb._state == CircuitState.OPEN

    async def test_open_circuit_rejects_calls(self):
        """When circuit is OPEN, call() raises CircuitBreakerError immediately."""
        cb, mock_redis = _make_breaker("open_test", fail_max=2)

        # Pre-set to OPEN state
        cb._state = CircuitState.OPEN
        cb._failure_count = 2
        cb._last_failure_time = time.time()

        # Redis reports OPEN state
        mock_redis.get = AsyncMock(
            side_effect=lambda key: "open"
            if ":state" in key
            else ("2" if ":failures" in key else str(time.time()))
        )

        with pytest.raises(CircuitBreakerError):
            await cb.call(AsyncMock(return_value="should_not_run"))

    async def test_edge_case_empty_exclude_exceptions(self):
        """Excluded exceptions do NOT increment failure count."""
        cb, mock_redis = _make_breaker("excl_test", fail_max=3)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)

        cb.exclude_exceptions = (ValueError,)

        async def raises_excluded():
            raise ValueError("ignored")

        with pytest.raises(ValueError):
            await cb.call(raises_excluded)

        # _on_failure should NOT have been called — no incr
        mock_redis.incr.assert_not_called()
        assert cb._failure_count == 0

    async def test_edge_case_none_redis_fallback(self):
        """When Redis raises, circuit_breaker falls back to local state."""
        cb, mock_redis = _make_breaker("redis_fail", fail_max=5)
        mock_redis.get = AsyncMock(side_effect=Exception("redis down"))

        # Should fall back to local state (CLOSED, 0, None)
        state, failures, last_fail = await cb._get_distributed_state()

        assert state == CircuitState.CLOSED
        assert failures == 0
        assert last_fail is None

    async def test_integration_with_mock(self):
        """Sync call_sync path opens circuit after fail_max sync failures."""
        cb, _ = _make_breaker("sync_test", fail_max=3)

        def failing_sync():
            raise RuntimeError("sync fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call_sync(failing_sync)

        assert cb._state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            cb.call_sync(lambda: "nope")

    async def test_return_type_validation(self):
        """get_status() returns a dict with expected keys."""
        cb, _ = _make_breaker("status_test")

        status = cb.get_status()

        assert isinstance(status, dict)
        assert set(status.keys()) == {
            "name",
            "state",
            "failure_count",
            "fail_max",
            "reset_timeout",
        }
        assert status["name"] == "status_test"
        assert status["state"] in {"closed", "open", "half_open"}

    def test_service_exists(self):
        """CircuitBreaker class is importable and instantiable."""
        from v2.modules.platform_infra.resilience.circuit_breaker import (
            CircuitBreaker,  # noqa: F401
        )

        assert CircuitBreaker is not None

    async def test_reset_clears_state(self):
        """reset() returns circuit to CLOSED with zero failures."""
        cb, _ = _make_breaker("reset_test", fail_max=2)
        cb._state = CircuitState.OPEN
        cb._failure_count = 5
        cb._last_failure_time = time.time()

        cb.reset()

        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._last_failure_time is None

    async def test_max_failures_alias(self):
        """max_failures kwarg is an alias for fail_max."""
        mock_redis = AsyncMock()
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=mock_redis,
        ):
            cb = CircuitBreaker(name="alias_test", max_failures=7)

        assert cb.fail_max == 7

    async def test_half_open_state_after_timeout(self):
        """OPEN circuit transitions to HALF_OPEN once reset_timeout elapses."""
        cb, _ = _make_breaker("half_open_test", fail_max=2, reset_timeout=0.0)
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.time() - 1.0  # past the timeout

        assert cb.state == CircuitState.HALF_OPEN

    async def test_context_manager_success(self):
        """Circuit breaker as async context manager records success."""
        cb, mock_redis = _make_breaker("ctx_test")
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        async with cb:
            pass  # no exception = success

        assert cb._state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def setup_method(self):
        """Clear registry before each test."""
        CircuitBreakerRegistry.clear()

    async def test_registry_get_creates_new_breaker(self):
        """Registry creates a new breaker on first get."""
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=AsyncMock(),
        ):
            cb = await CircuitBreakerRegistry.get("reg_test", fail_max=3)

        assert cb is not None
        assert cb.name == "reg_test"
        assert cb.fail_max == 3

    async def test_registry_get_returns_same_instance(self):
        """Registry returns the same breaker for the same name."""
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=AsyncMock(),
        ):
            cb1 = await CircuitBreakerRegistry.get("same_test")
            cb2 = await CircuitBreakerRegistry.get("same_test")

        assert cb1 is cb2

    def test_registry_reset_returns_true_for_existing(self):
        """Registry reset returns True for a known breaker."""
        mock_redis = AsyncMock()
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=mock_redis,
        ):
            cb = CircuitBreakerRegistry.get_sync("reset_reg")

        cb._state = CircuitState.OPEN
        result = CircuitBreakerRegistry.reset("reset_reg")

        assert result is True
        assert cb._state == CircuitState.CLOSED

    def test_registry_reset_returns_false_for_unknown(self):
        """Registry reset returns False for an unknown name."""
        result = CircuitBreakerRegistry.reset("nonexistent_cb")
        assert result is False


class TestCircuitProtectedDecorator:
    def setup_method(self):
        CircuitBreakerRegistry.clear()

    async def test_decorator_passes_result_through(self):
        """@circuit_protected passes return value through on success."""
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=AsyncMock(
                get=AsyncMock(return_value=None),
                set=AsyncMock(return_value=True),
                incr=AsyncMock(return_value=0),
            ),
        ):

            @circuit_protected("dec_test", fail_max=3)
            async def my_func():
                return 42

            result = await my_func()

        assert result == 42

    async def test_decorator_uses_fallback_when_open(self):
        """@circuit_protected calls fallback when circuit is OPEN."""
        with patch(
            "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
            return_value=AsyncMock(
                get=AsyncMock(return_value="open"),
                set=AsyncMock(return_value=True),
                incr=AsyncMock(return_value=5),
            ),
        ):

            @circuit_protected(
                "dec_fallback", fail_max=2, fallback=lambda: "fallback_val"
            )
            async def my_fn():
                return "real"

            # Force registry to have an OPEN breaker
            cb = await CircuitBreakerRegistry.get("dec_fallback", fail_max=2)
            cb._state = CircuitState.OPEN
            cb._failure_count = 2
            cb._last_failure_time = time.time()

            result = await my_fn()

        assert result == "fallback_val"
