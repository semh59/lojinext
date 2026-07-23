"""
Additional coverage tests for v2/modules/platform_infra/events/event_bus.py.

Targets uncovered lines:
- _connect_redis: fallback to direct Redis connection when cache is unavailable
- _connect_redis: Redis.ping() raises → fallback to None
- _is_duplicate: Redis set fails → fallback to memory dedup
- _is_duplicate: memory cache trimmed when over _max_processed_cache
- _handle_failure: DLQ overflow (pop oldest), Redis lpush success, Redis lpush failure
- publish: async callback via asyncio.create_task (coroutine branch)
- EventBus singleton: double __new__ returns same instance
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from v2.modules.platform_infra.events.event_bus import (
    Event,
    EventBus,
    get_event_bus,
)
from v2.modules.platform_infra.events.event_types import EventType

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_event_bus():
    """Reset EventBus singleton state before/after each test."""
    bus = EventBus()
    bus.reset_all_for_tests()
    yield bus
    bus.reset_all_for_tests()


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------


def test_singleton_returns_same_instance():
    """Multiple EventBus() calls return the exact same object."""
    b1 = EventBus()
    b2 = EventBus()
    assert b1 is b2


def test_get_event_bus_is_singleton():
    """get_event_bus() and EventBus() return the same instance."""
    assert get_event_bus() is EventBus()


# ---------------------------------------------------------------------------
# _validate_event
# ---------------------------------------------------------------------------


def test_validate_event_large_payload_raises():
    """_validate_event raises ValueError when payload exceeds max size."""
    bus = EventBus()
    big_data = {"x": "A" * (bus._max_payload_size + 100)}
    event = Event(type=EventType.ARAC_ADDED, data=big_data, event_id="big-01")
    with pytest.raises(ValueError, match="payload too large"):
        bus._validate_event(event)


def test_validate_event_none_data_is_replaced():
    """_validate_event sets data to {} when event.data is None."""
    bus = EventBus()
    event = Event(type=EventType.ARAC_ADDED, event_id="null-data")
    event.data = None  # type: ignore[assignment]
    bus._validate_event(event)
    assert event.data == {}


# ---------------------------------------------------------------------------
# _get_event_id
# ---------------------------------------------------------------------------


def test_get_event_id_uses_event_id_when_present():
    """_get_event_id returns event.event_id when it's set."""
    bus = EventBus()
    event = Event(type=EventType.SEFER_ADDED, event_id="explicit-id-xyz")
    assert bus._get_event_id(event) == "explicit-id-xyz"


def test_get_event_id_generates_hash_when_no_event_id():
    """_get_event_id generates a consistent md5 hash when event_id is None."""
    bus = EventBus()
    event = Event(type=EventType.SEFER_ADDED, event_id=None)
    eid1 = bus._get_event_id(event)
    eid2 = bus._get_event_id(event)
    assert eid1 == eid2
    assert len(eid1) == 16


# ---------------------------------------------------------------------------
# _is_duplicate — memory fallback and cache trimming
# ---------------------------------------------------------------------------


def test_is_duplicate_memory_dedup_when_no_redis(clean_event_bus):
    """_is_duplicate uses in-memory set when Redis is None."""
    bus = clean_event_bus
    bus._redis = None

    event = Event(type=EventType.CACHE_INVALIDATED, event_id="mem-dup-01")
    assert bus._is_duplicate(event) is False  # first time
    assert bus._is_duplicate(event) is True  # duplicate


def test_is_duplicate_trims_memory_cache_when_full(clean_event_bus):
    """_is_duplicate trims processed_events set when it exceeds the cap."""
    bus = clean_event_bus
    bus._redis = None
    # Use a large max so we can fill beyond it without hitting default limit prematurely
    bus._max_processed_cache = 1000

    # AUDIT-143: _processed_events artık FIFO eviction için OrderedDict (set değil).
    for i in range(1001):
        bus._processed_events[f"event-{i:04d}"] = None

    assert len(bus._processed_events) == 1001  # over limit

    event = Event(type=EventType.ARAC_ADDED, event_id="trim-test")
    bus._is_duplicate(event)
    # AUDIT-143: FIFO eviction _max_processed_cache'e (1000) kadar popitem(last=False)
    # yapar; eskiden last-500'e indiriliyordu.
    assert len(bus._processed_events) <= bus._max_processed_cache


def test_is_duplicate_redis_failure_falls_back_to_memory(clean_event_bus):
    """_is_duplicate falls back to memory dedup when Redis raises."""
    bus = clean_event_bus
    mock_redis = MagicMock()
    mock_redis.set = MagicMock(side_effect=Exception("redis timeout"))
    bus._redis = mock_redis

    event = Event(type=EventType.ANOMALY_DETECTED, event_id="redis-fail-01")
    result = bus._is_duplicate(event)
    # Should not raise; first occurrence → not a duplicate
    assert result is False


# ---------------------------------------------------------------------------
# _handle_failure — DLQ overflow and Redis write
# ---------------------------------------------------------------------------


def test_handle_failure_pops_oldest_when_dlq_full(clean_event_bus):
    """_handle_failure evicts the oldest entry when DLQ is at capacity."""
    bus = clean_event_bus
    bus._max_dlq_size = 3
    bus._redis = None

    event = Event(type=EventType.SEFER_UPDATED, event_id="dlq-overflow")
    # Fill DLQ to max
    for i in range(3):
        bus._failed_events.append((event, f"cb_{i}", "err", None))

    bus._handle_failure(event, "new_callback", "new_error")
    assert len(bus._failed_events) == 3  # still at max, oldest evicted


def test_handle_failure_pushes_to_redis_dlq(clean_event_bus):
    """_handle_failure sends failed event JSON to Redis DLQ."""
    bus = clean_event_bus
    mock_redis = MagicMock()
    mock_redis.lpush = MagicMock(return_value=1)
    bus._redis = mock_redis

    event = Event(type=EventType.YAKIT_ADDED, event_id="dlq-redis-01")
    bus._handle_failure(event, "some_callback", "some_error")

    mock_redis.lpush.assert_called_once()
    key, payload = mock_redis.lpush.call_args[0]
    assert "dlq" in key


def test_handle_failure_redis_push_exception_swallowed(clean_event_bus):
    """_handle_failure continues silently if Redis lpush raises."""
    bus = clean_event_bus
    mock_redis = MagicMock()
    mock_redis.lpush = MagicMock(side_effect=Exception("redis down"))
    bus._redis = mock_redis

    event = Event(type=EventType.APP_STARTED, event_id="dlq-fail-01")
    # Should not raise
    bus._handle_failure(event, "cb_name", "error_msg")
    assert len(bus._failed_events) == 1


# ---------------------------------------------------------------------------
# publish — async callback branch (asyncio.create_task)
# ---------------------------------------------------------------------------


async def test_publish_schedules_async_callback(clean_event_bus):
    """publish() schedules async handlers via asyncio.create_task."""
    bus = clean_event_bus
    bus._redis = None
    received = []

    async def async_handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.ROUTE_STARTED, async_handler)
    event = Event(type=EventType.ROUTE_STARTED, event_id="async-task-01")
    bus.publish(event)

    # Give the task time to run
    await asyncio.sleep(0.05)

    assert len(received) == 1


# ---------------------------------------------------------------------------
# publish_async — failing async callback → DLQ
# ---------------------------------------------------------------------------


async def test_publish_async_failing_handler_recorded_in_dlq(clean_event_bus):
    """publish_async records failing async handler in failed_events."""
    bus = clean_event_bus
    bus._redis = None

    async def bad_async_handler(event: Event):
        raise RuntimeError("async callback error")

    bus.subscribe(EventType.ANOMALY_DETECTED, bad_async_handler)
    event = Event(type=EventType.ANOMALY_DETECTED, event_id="async-fail-01")
    await bus.publish_async(event)

    assert len(bus._failed_events) == 1
    assert bus._failed_events[0][1] == "bad_async_handler"


# ---------------------------------------------------------------------------
# subscribe — duplicate subscribe guard
# ---------------------------------------------------------------------------


def test_subscribe_same_handler_twice_not_duplicated(clean_event_bus):
    """Subscribing the same handler twice does not add it twice."""
    bus = clean_event_bus

    def handler(e):
        pass

    bus.subscribe(EventType.ARAC_ADDED, handler)
    bus.subscribe(EventType.ARAC_ADDED, handler)  # second subscribe

    assert bus._subscribers[EventType.ARAC_ADDED].count(handler) == 1


# ---------------------------------------------------------------------------
# unsubscribe — removing non-existent handler
# ---------------------------------------------------------------------------


def test_unsubscribe_nonexistent_handler_noop(clean_event_bus):
    """Unsubscribing a handler that was never subscribed does not raise."""
    bus = clean_event_bus

    def handler(e):
        pass

    # Should not raise
    bus.unsubscribe(EventType.SEFER_ADDED, handler)


# ---------------------------------------------------------------------------
# Event history trim
# ---------------------------------------------------------------------------


def test_event_history_trim_maintains_max(clean_event_bus):
    """Event history trims to _max_history by removing from the front."""
    bus = clean_event_bus
    bus._redis = None
    bus._max_history = 3

    for i in range(5):
        event = Event(type=EventType.APP_STARTED, event_id=f"hist-trim-{i}")
        bus.publish(event)

    assert len(bus._event_history) == 3
    # The most recent events should be at the end
    assert bus._event_history[-1].event_id == "hist-trim-4"


# ---------------------------------------------------------------------------
# _connect_redis: Redis ping failure path
# ---------------------------------------------------------------------------


def test_connect_redis_ping_failure_sets_redis_none():
    """_connect_redis sets _redis=None when ping() raises."""
    bus = EventBus()
    # Simulate fresh connection attempt
    mock_redis_instance = MagicMock()
    mock_redis_instance.ping = MagicMock(side_effect=Exception("connection refused"))

    mock_redis_class = MagicMock()
    mock_redis_class.from_url = MagicMock(return_value=mock_redis_instance)

    with (
        patch("v2.modules.platform_infra.events.event_bus.get_redis_cache") as mock_cache,
        patch("redis.Redis", mock_redis_class),
    ):
        mock_cache.side_effect = Exception("cache unavailable")
        bus._redis = None  # reset
        bus._connect_redis()

    # _redis stays None if ping fails
    assert bus._redis is None
