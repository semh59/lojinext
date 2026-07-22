"""
Additional coverage tests for v2/modules/platform_infra/resilience/circuit_breaker.py.

Targets uncovered lines:
- CircuitBreaker._get_distributed_state: OPEN → HALF_OPEN after reset_timeout
- CircuitBreaker._on_success: half-open → closed with Redis persistence
- CircuitBreaker._on_success: Redis set fails (continues silently)
- CircuitBreaker._on_failure: failure count < fail_max (no open transition)
- CircuitBreaker._on_failure: HALF_OPEN → OPEN (test failed)
- CircuitBreaker._on_failure: Redis set for last_fail raises
- CircuitBreaker._on_failure_sync: half-open → open (sync path)
- CircuitBreaker._get_state: returns OPEN when Redis count >= fail_max
- CircuitBreaker._get_state: Redis error → fallback to local state
- CircuitBreaker.__aenter__: OPEN raises CircuitBreakerError
- CircuitBreaker.__aexit__: excluded exception skips _on_failure
- CircuitBreakerRegistry.get_sync: creates and caches breaker
- CircuitBreakerRegistry.get_all_status: returns list of statuses
- circuit_protected: decorator re-raises CircuitBreakerError when no fallback
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

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
# Helper
# ---------------------------------------------------------------------------


def _make_breaker(name="test_cb", fail_max=3, reset_timeout=60.0, exclude=()):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.incr = AsyncMock(return_value=1)

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=mock_redis,
    ):
        cb = CircuitBreaker(
            name=name,
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            exclude_exceptions=exclude,
        )
    cb._redis = mock_redis
    return cb, mock_redis


# ---------------------------------------------------------------------------
# _get_distributed_state: OPEN → HALF_OPEN transition
# ---------------------------------------------------------------------------


async def test_get_distributed_state_open_to_half_open():
    """When Redis reports OPEN but last_fail was > reset_timeout ago → HALF_OPEN."""
    cb, mock_redis = _make_breaker("dist-half", fail_max=3, reset_timeout=1.0)

    old_time = str(time.time() - 10.0)  # 10 seconds ago, past reset_timeout=1s

    async def mock_get(key):
        if ":state" in key:
            return "open"
        if ":failures" in key:
            return "3"
        if ":last_fail" in key:
            return old_time
        return None

    mock_redis.get = mock_get

    state, failures, last_fail = await cb._get_distributed_state()
    assert state == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# _get_distributed_state: OPEN with recent failure stays OPEN
# ---------------------------------------------------------------------------


async def test_get_distributed_state_open_stays_open_recently():
    """OPEN with last_fail within reset_timeout remains OPEN."""
    cb, mock_redis = _make_breaker("dist-open", fail_max=3, reset_timeout=60.0)

    recent_time = str(time.time() - 5.0)  # 5s ago, within 60s timeout

    async def mock_get(key):
        if ":state" in key:
            return "open"
        if ":failures" in key:
            return "3"
        if ":last_fail" in key:
            return recent_time
        return None

    mock_redis.get = mock_get

    state, failures, last_fail = await cb._get_distributed_state()
    assert state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# _on_success: HALF_OPEN → CLOSED with Redis persistence
# ---------------------------------------------------------------------------


async def test_on_success_from_half_open_logs_and_closes():
    """_on_success from HALF_OPEN state closes circuit and persists to Redis."""
    cb, mock_redis = _make_breaker("success-half")
    cb._state = CircuitState.HALF_OPEN
    cb._failure_count = 2

    await cb._on_success()

    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0
    mock_redis.set.assert_called()


async def test_on_success_redis_failure_silently_continues():
    """_on_success continues even when Redis set raises."""
    cb, mock_redis = _make_breaker("success-redis-fail")
    mock_redis.set = AsyncMock(side_effect=Exception("redis down"))

    # Should not raise
    await cb._on_success()
    assert cb._state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# _on_failure: failure count below fail_max
# ---------------------------------------------------------------------------


async def test_on_failure_below_fail_max_stays_closed():
    """_on_failure increments but does not open circuit when below fail_max."""
    cb, mock_redis = _make_breaker("below-max", fail_max=5)
    mock_redis.incr = AsyncMock(return_value=2)  # below fail_max=5

    await cb._on_failure()

    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 2


async def test_on_failure_at_fail_max_opens_circuit():
    """_on_failure opens circuit when failure_count reaches fail_max."""
    cb, mock_redis = _make_breaker("at-max", fail_max=3)
    mock_redis.incr = AsyncMock(return_value=3)  # == fail_max

    await cb._on_failure()

    assert cb._state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# _on_failure: HALF_OPEN → OPEN (test call failed)
# ---------------------------------------------------------------------------


async def test_on_failure_half_open_reopens():
    """_on_failure in HALF_OPEN state transitions back to OPEN."""
    cb, mock_redis = _make_breaker("half-reopen", fail_max=5)
    cb._state = CircuitState.HALF_OPEN
    mock_redis.incr = AsyncMock(return_value=1)  # count still below fail_max

    await cb._on_failure()

    assert cb._state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# _on_failure: Redis set for last_fail raises
# ---------------------------------------------------------------------------


async def test_on_failure_redis_last_fail_set_raises():
    """_on_failure continues even when Redis set for last_fail raises."""
    cb, mock_redis = _make_breaker("fail-redis", fail_max=5)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.set = AsyncMock(side_effect=Exception("redis timeout"))

    # Should not raise
    await cb._on_failure()
    assert cb._failure_count == 1


# ---------------------------------------------------------------------------
# _on_failure_sync: HALF_OPEN → OPEN
# ---------------------------------------------------------------------------


def test_on_failure_sync_half_open_reopens():
    """_on_failure_sync in HALF_OPEN state transitions to OPEN."""
    cb, _ = _make_breaker("sync-half-reopen", fail_max=5)
    cb._state = CircuitState.HALF_OPEN
    cb._failure_count = 1

    cb._on_failure_sync()

    assert cb._state == CircuitState.OPEN


def test_on_failure_sync_below_fail_max():
    """_on_failure_sync increments but doesn't open when below fail_max."""
    cb, _ = _make_breaker("sync-below", fail_max=5)
    cb._failure_count = 0

    cb._on_failure_sync()

    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 1


def test_on_success_sync_from_half_open():
    """_on_success_sync from HALF_OPEN logs recovery and closes circuit."""
    cb, _ = _make_breaker("sync-success-half")
    cb._state = CircuitState.HALF_OPEN
    cb._failure_count = 2

    cb._on_success_sync()

    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# _get_state
# ---------------------------------------------------------------------------


async def test_get_state_open_when_redis_count_ge_fail_max():
    """_get_state returns 'OPEN' when Redis failure count >= fail_max."""
    cb, mock_redis = _make_breaker("get-state-open", fail_max=3)
    mock_redis.get = AsyncMock(return_value="3")  # == fail_max

    state_str = await cb._get_state()
    assert state_str == "OPEN"


async def test_get_state_returns_local_on_redis_error():
    """_get_state falls back to local state when Redis raises."""
    cb, mock_redis = _make_breaker("get-state-fallback")
    mock_redis.get = AsyncMock(side_effect=Exception("redis down"))
    cb._state = CircuitState.CLOSED

    state_str = await cb._get_state()
    assert state_str == "CLOSED"


async def test_get_state_closed_when_below_fail_max():
    """_get_state returns local CLOSED state when count < fail_max."""
    cb, mock_redis = _make_breaker("get-state-closed", fail_max=5)
    mock_redis.get = AsyncMock(return_value="2")  # below fail_max
    cb._state = CircuitState.CLOSED

    state_str = await cb._get_state()
    assert state_str == "CLOSED"


# ---------------------------------------------------------------------------
# __aenter__: OPEN raises CircuitBreakerError
# ---------------------------------------------------------------------------


async def test_aenter_raises_when_open():
    """__aenter__ raises CircuitBreakerError when circuit is OPEN."""
    cb, mock_redis = _make_breaker("aenter-open", fail_max=2)

    async def mock_get(key):
        if ":state" in key:
            return "open"
        if ":failures" in key:
            return "2"
        if ":last_fail" in key:
            return str(time.time() - 1.0)  # recent
        return None

    mock_redis.get = mock_get
    cb._state = CircuitState.OPEN
    cb._failure_count = 2
    cb._last_failure_time = time.time()

    with pytest.raises(CircuitBreakerError):
        async with cb:
            pass


# ---------------------------------------------------------------------------
# __aexit__: excluded exception skips _on_failure
# ---------------------------------------------------------------------------


async def test_aexit_excluded_exception_skips_on_failure():
    """__aexit__ does not call _on_failure for excluded exception types."""
    cb, mock_redis = _make_breaker("aexit-excl")
    cb.exclude_exceptions = (ValueError,)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)

    original_failure_count = cb._failure_count

    with pytest.raises(ValueError):
        async with cb:
            raise ValueError("excluded error")

    # Failure count should not have changed
    assert cb._failure_count == original_failure_count


async def test_aexit_records_success():
    """__aexit__ calls _on_success when no exception."""
    cb, mock_redis = _make_breaker("aexit-success")
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)

    cb._state = CircuitState.CLOSED

    async with cb:
        pass  # no exception

    assert cb._state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry: get_sync and get_all_status
# ---------------------------------------------------------------------------


def test_registry_get_sync_creates_and_caches():
    """Registry.get_sync creates a new breaker and returns same instance on re-call."""
    CircuitBreakerRegistry.clear()

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=MagicMock(),
    ):
        cb1 = CircuitBreakerRegistry.get_sync("sync-reg-1", fail_max=7)
        cb2 = CircuitBreakerRegistry.get_sync("sync-reg-1")

    assert cb1 is cb2
    assert cb1.fail_max == 7
    CircuitBreakerRegistry.clear()


def test_registry_get_all_status_returns_list():
    """Registry.get_all_status returns list of status dicts."""
    CircuitBreakerRegistry.clear()

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=MagicMock(),
    ):
        CircuitBreakerRegistry.get_sync("status-a")
        CircuitBreakerRegistry.get_sync("status-b")

    statuses = CircuitBreakerRegistry.get_all_status()
    assert isinstance(statuses, list)
    assert len(statuses) == 2
    names = {s["name"] for s in statuses}
    assert "status-a" in names
    assert "status-b" in names
    CircuitBreakerRegistry.clear()


# ---------------------------------------------------------------------------
# circuit_protected: re-raises CircuitBreakerError when no fallback
# ---------------------------------------------------------------------------


async def test_circuit_protected_reraises_when_no_fallback():
    """@circuit_protected raises CircuitBreakerError when circuit is open and no fallback."""
    CircuitBreakerRegistry.clear()

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=AsyncMock(
            get=AsyncMock(return_value="open"),
            set=AsyncMock(return_value=True),
            incr=AsyncMock(return_value=5),
        ),
    ):

        @circuit_protected("no-fallback-cb", fail_max=2)
        async def my_fn():
            return "real"

        cb = await CircuitBreakerRegistry.get("no-fallback-cb", fail_max=2)
        cb._state = CircuitState.OPEN
        cb._failure_count = 2
        cb._last_failure_time = time.time()

        with pytest.raises(CircuitBreakerError):
            await my_fn()

    CircuitBreakerRegistry.clear()


# ---------------------------------------------------------------------------
# circuit_protected: non-callable fallback value
# ---------------------------------------------------------------------------


async def test_circuit_protected_non_callable_fallback():
    """@circuit_protected returns static fallback value (not callable)."""
    CircuitBreakerRegistry.clear()

    with patch(
        "v2.modules.platform_infra.resilience.circuit_breaker.get_pubsub_manager",
        return_value=AsyncMock(
            get=AsyncMock(return_value="open"),
            set=AsyncMock(return_value=True),
            incr=AsyncMock(return_value=5),
        ),
    ):

        @circuit_protected("static-fallback-cb", fail_max=2, fallback="static_value")
        async def my_fn():
            return "real"

        cb = await CircuitBreakerRegistry.get("static-fallback-cb", fail_max=2)
        cb._state = CircuitState.OPEN
        cb._failure_count = 2
        cb._last_failure_time = time.time()

        result = await my_fn()

    assert result == "static_value"
    CircuitBreakerRegistry.clear()


# ---------------------------------------------------------------------------
# call_sync: excluded exception does not trigger _on_failure_sync
# ---------------------------------------------------------------------------


def test_call_sync_excluded_exception_skipped():
    """call_sync does not update failure count for excluded exceptions."""
    cb, _ = _make_breaker("sync-excl", fail_max=3)
    cb.exclude_exceptions = (KeyError,)
    cb._state = CircuitState.CLOSED

    original_count = cb._failure_count

    with pytest.raises(KeyError):
        cb.call_sync(lambda: (_ for _ in ()).throw(KeyError("excluded")))

    assert cb._failure_count == original_count
