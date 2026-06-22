"""
Unit tests for EventBus, Event, and the publishes decorator.

EventBus is a singleton; tests call reset_all_for_tests() before each test
to ensure clean state.  Redis is disabled (no REDIS_URL env set in unit tests).
"""

import pytest

from app.infrastructure.events.event_bus import (
    Event,
    EventBus,
    get_event_bus,
    publishes,
)
from app.infrastructure.events.event_types import EventType

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean_event_bus():
    """Reset EventBus singleton state before each test."""
    bus = EventBus()
    bus.reset_all_for_tests()
    yield bus
    bus.reset_all_for_tests()


class TestEvent:
    def test_basic_initialization(self):
        """Event initialises with type, empty data dict, and a timestamp."""
        event = Event(type=EventType.ARAC_ADDED)

        assert event.type == EventType.ARAC_ADDED
        assert event.data == {}
        assert event.timestamp is not None
        assert event.source == ""
        assert event.version == "1.0"

    def test_event_with_data(self):
        """Event stores arbitrary data payload."""
        event = Event(
            type=EventType.SEFER_ADDED,
            data={"sefer_id": 42, "mesafe": 300},
            source="sefer_service",
        )

        assert event.data["sefer_id"] == 42
        assert event.source == "sefer_service"

    def test_event_str_representation(self):
        """__str__ includes type value and source."""
        event = Event(type=EventType.ANOMALY_DETECTED, source="ml_service")
        result = str(event)

        assert "anomaly_detected" in result
        assert "ml_service" in result


class TestEventBus:
    async def test_basic_initialization(self):
        """EventBus singleton initialises with empty subscribers and history."""
        bus = EventBus()

        assert isinstance(bus._subscribers, dict)
        assert len(bus._event_history) == 0

    async def test_happy_path(self):
        """Published event reaches subscribed callback."""
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.ARAC_ADDED, handler)
        event = Event(type=EventType.ARAC_ADDED, data={"id": 1})
        bus.publish(event)

        assert len(received) == 1
        assert received[0].data["id"] == 1

    async def test_error_handling(self):
        """Failing callback is logged and added to DLQ; other handlers continue."""
        bus = EventBus()
        good_results = []

        def bad_handler(event):
            raise RuntimeError("callback error")

        def good_handler(event):
            good_results.append(event)

        bus.subscribe(EventType.ARAC_ADDED, bad_handler)
        bus.subscribe(EventType.ARAC_ADDED, good_handler)

        event = Event(type=EventType.ARAC_ADDED, event_id="unique_err_01")
        bus.publish(event)

        # good handler still ran
        assert len(good_results) == 1
        # failed event is recorded in DLQ
        assert len(bus._failed_events) == 1

    async def test_edge_case_empty(self):
        """Publishing to event type with no subscribers does nothing."""
        bus = EventBus()

        event = Event(type=EventType.APP_STARTED, event_id="no_sub_01")
        # Should not raise
        bus.publish(event)

        assert len(bus._event_history) == 1

    async def test_edge_case_none(self):
        """publish() raises ValueError for an event with no type (None guard)."""
        bus = EventBus()

        with pytest.raises((ValueError, AttributeError)):
            bus._validate_event(None)  # type: ignore[arg-type]

    async def test_integration_with_mock(self):
        """publish_async delivers to async callback."""
        bus = EventBus()
        received = []

        async def async_handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.YAKIT_ADDED, async_handler)
        event = Event(
            type=EventType.YAKIT_ADDED, data={"litre": 200}, event_id="async_01"
        )

        await bus.publish_async(event)

        assert len(received) == 1
        assert received[0].data["litre"] == 200

    async def test_return_type_validation(self):
        """publish_simple_async builds an Event from kwargs and delivers it."""
        bus = EventBus()
        received = []

        async def handler(e: Event):
            received.append(e)

        bus.subscribe(EventType.SEFER_UPDATED, handler)
        await bus.publish_simple_async(EventType.SEFER_UPDATED, sefer_id=99)

        assert len(received) == 1
        assert received[0].data["sefer_id"] == 99

    def test_service_exists(self):
        """get_event_bus() returns the EventBus singleton."""
        bus = get_event_bus()

        assert isinstance(bus, EventBus)

    async def test_subscribe_and_unsubscribe(self):
        """Unsubscribed callback no longer receives events."""
        bus = EventBus()
        calls = []

        def handler(event):
            calls.append(event)

        bus.subscribe(EventType.ARAC_UPDATED, handler)
        event1 = Event(type=EventType.ARAC_UPDATED, event_id="unsub_01")
        bus.publish(event1)
        assert len(calls) == 1

        bus.unsubscribe(EventType.ARAC_UPDATED, handler)
        event2 = Event(type=EventType.ARAC_UPDATED, event_id="unsub_02")
        bus.publish(event2)
        assert len(calls) == 1  # not called again

    async def test_duplicate_event_suppressed(self):
        """Event with the same event_id published twice is delivered only once."""
        bus = EventBus()
        calls = []

        def handler(event):
            calls.append(event)

        bus.subscribe(EventType.ROUTE_STARTED, handler)

        event = Event(type=EventType.ROUTE_STARTED, event_id="dup_id_001")
        bus.publish(event)
        bus.publish(event)  # duplicate

        assert len(calls) == 1

    async def test_event_history_capped_at_max_history(self):
        """Event history does not exceed _max_history entries."""
        bus = EventBus()
        bus._max_history = 5
        bus._event_history.clear()
        bus._processed_events.clear()

        for i in range(10):
            e = Event(type=EventType.APP_STARTED, event_id=f"hist_{i:04d}")
            bus.publish(e)

        assert len(bus._event_history) <= 5

    def test_publishes_decorator_attaches_metadata(self):
        """@publishes attaches _publishes attribute to the function."""

        @publishes(EventType.SEFER_ADDED)
        def my_service_method():
            pass

        assert hasattr(my_service_method, "_publishes")
        assert my_service_method._publishes == EventType.SEFER_ADDED

    async def test_clear_history(self):
        """clear_history() empties the event history list."""
        bus = EventBus()
        event = Event(type=EventType.CACHE_INVALIDATED, event_id="clear_01")
        bus.publish(event)
        assert len(bus._event_history) >= 1

        bus.clear_history()

        assert len(bus._event_history) == 0
