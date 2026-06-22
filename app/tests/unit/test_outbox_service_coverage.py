"""
Coverage tests for app/infrastructure/events/outbox_service.py
Tests OutboxService.save_event, relay_pending_events, get_outbox_service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uow(session=None):
    """Build a mock UnitOfWork context manager."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.commit = AsyncMock()
    mock_uow.session = session or AsyncMock()
    return mock_uow


def _fake_outbox_event(
    id=1, event_type="sefer_added", payload=None, processed=False, retry_count=0
):
    obj = MagicMock()
    obj.id = id
    obj.event_type = event_type
    obj.payload = payload or {}
    obj.processed = processed
    obj.retry_count = retry_count
    obj.correlation_id = "corr-123"
    obj.error_message = None
    obj.processed_at = None
    return obj


# ---------------------------------------------------------------------------
# OutboxService.save_event
# ---------------------------------------------------------------------------


async def test_save_event_returns_id():
    """Happy path: event is added to session, id returned."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    mock_uow = _make_uow(session)

    from app.infrastructure.events.outbox_service import OutboxService

    svc = OutboxService(uow=mock_uow)

    # Make db_event.id accessible after flush
    def fake_add(obj):
        obj.id = 42

    session.add.side_effect = fake_add

    result = await svc.save_event("sefer_added", {"sefer_id": 1})

    assert result == 42
    session.add.assert_called_once()
    session.flush.assert_called_once()


async def test_save_event_raises_without_uow():
    """No UoW → RuntimeError."""
    from app.infrastructure.events.outbox_service import OutboxService

    svc = OutboxService()  # no uow

    with pytest.raises(RuntimeError, match="UnitOfWork"):
        await svc.save_event("test_event", {})


async def test_save_event_uses_passed_uow_over_instance_uow():
    """Explicit uow param overrides self.uow."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    passed_uow = _make_uow(session)
    instance_uow = _make_uow()  # should not be used

    from app.infrastructure.events.outbox_service import OutboxService

    svc = OutboxService(uow=instance_uow)

    def fake_add(obj):
        obj.id = 7

    session.add.side_effect = fake_add

    result = await svc.save_event("test_event", {"x": 1}, uow=passed_uow)

    assert result == 7
    # instance_uow session should NOT have been called
    instance_uow.session.add.assert_not_called()


async def test_save_event_uses_correlation_id():
    """correlation_id from context is attached to the OutboxEvent."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    mock_uow = _make_uow(session)

    captured = {}

    def fake_add(obj):
        obj.id = 1
        captured["correlation_id"] = obj.correlation_id

    session.add.side_effect = fake_add

    with patch(
        "app.infrastructure.events.outbox_service.get_correlation_id",
        return_value="test-correlation-xyz",
    ):
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService(uow=mock_uow)
        await svc.save_event("yakit_added", {"lt": 100})

    assert captured["correlation_id"] == "test-correlation-xyz"


async def test_save_event_payload_stored():
    """payload dict is set on the OutboxEvent."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    mock_uow = _make_uow(session)

    captured = {}

    def fake_add(obj):
        obj.id = 5
        captured["payload"] = obj.payload

    session.add.side_effect = fake_add

    from app.infrastructure.events.outbox_service import OutboxService

    svc = OutboxService(uow=mock_uow)
    await svc.save_event("arac_updated", {"arac_id": 3, "plaka": "34ABC"})

    assert captured["payload"] == {"arac_id": 3, "plaka": "34ABC"}


# ---------------------------------------------------------------------------
# OutboxService.relay_pending_events
# ---------------------------------------------------------------------------


async def test_relay_pending_events_returns_zero_when_empty():
    """No pending events → returns 0 immediately (no commit)."""
    import app.database.unit_of_work as uow_mod

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_uow = _make_uow(mock_session)

    original = uow_mod.UnitOfWork

    class _FakeUoW:
        async def __aenter__(self):
            return mock_uow

        async def __aexit__(self, *a):
            pass

    uow_mod.UnitOfWork = _FakeUoW
    try:
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService()
        count = await svc.relay_pending_events()
    finally:
        uow_mod.UnitOfWork = original

    assert count == 0


def _patch_uow(mock_uow_inner):
    """
    Context manager that replaces UnitOfWork in app.database.unit_of_work
    with a fake that uses mock_uow_inner as the async-with result.
    The local import inside relay_pending_events picks this up.
    """
    import contextlib

    import app.database.unit_of_work as uow_mod

    class _FakeUoW:
        async def __aenter__(self):
            return mock_uow_inner

        async def __aexit__(self, *a):
            pass

    @contextlib.contextmanager
    def _ctx():
        original = uow_mod.UnitOfWork
        uow_mod.UnitOfWork = _FakeUoW
        try:
            yield
        finally:
            uow_mod.UnitOfWork = original

    return _ctx()


async def test_relay_pending_events_processes_events():
    """Events are published and marked as processed."""
    ev1 = _fake_outbox_event(id=1, event_type="sefer_added", payload={"id": 1})

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ev1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_uow = _make_uow(mock_session)

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()

    with (
        _patch_uow(mock_uow),
        patch(
            "app.infrastructure.events.outbox_service.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "app.infrastructure.events.outbox_service.is_stopping", return_value=False
        ),
    ):
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService()
        count = await svc.relay_pending_events()

    assert count == 1
    assert ev1.processed is True
    assert ev1.processed_at is not None
    mock_bus.publish_async.assert_called_once()


async def test_relay_pending_events_increments_retry_on_failure():
    """If publish fails, retry_count is incremented and error_message set."""
    ev1 = _fake_outbox_event(id=2, event_type="sefer_added", retry_count=0)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ev1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_uow = _make_uow(mock_session)

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock(side_effect=RuntimeError("bus error"))

    with (
        _patch_uow(mock_uow),
        patch(
            "app.infrastructure.events.outbox_service.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "app.infrastructure.events.outbox_service.is_stopping", return_value=False
        ),
    ):
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService()
        count = await svc.relay_pending_events()

    assert count == 0
    assert ev1.retry_count == 1
    assert "bus error" in ev1.error_message


async def test_relay_pending_events_stops_on_shutdown():
    """is_stopping() returns True on first check → breaks before processing."""
    ev1 = _fake_outbox_event(id=10, event_type="sefer_added")
    ev2 = _fake_outbox_event(id=11, event_type="sefer_updated")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ev1, ev2]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_uow = _make_uow(mock_session)

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()

    call_count = 0

    def stopping_side_effect():
        nonlocal call_count
        # Returns True immediately → no events processed
        call_count += 1
        return True

    with (
        _patch_uow(mock_uow),
        patch(
            "app.infrastructure.events.outbox_service.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "app.infrastructure.events.outbox_service.is_stopping",
            side_effect=stopping_side_effect,
        ),
    ):
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService()
        count = await svc.relay_pending_events()

    # is_stopping was True from the start → 0 processed
    assert count == 0
    mock_bus.publish_async.assert_not_called()


async def test_relay_pending_events_commits():
    """UoW.commit is called after relay loop when events exist."""
    ev1 = _fake_outbox_event(id=5, event_type="sefer_added", payload={})

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ev1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_uow = _make_uow(mock_session)

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()

    with (
        _patch_uow(mock_uow),
        patch(
            "app.infrastructure.events.outbox_service.get_event_bus",
            return_value=mock_bus,
        ),
        patch(
            "app.infrastructure.events.outbox_service.is_stopping", return_value=False
        ),
    ):
        from app.infrastructure.events.outbox_service import OutboxService

        svc = OutboxService()
        await svc.relay_pending_events()

    mock_uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_outbox_service factory
# ---------------------------------------------------------------------------


def test_get_outbox_service_returns_instance():
    from app.infrastructure.events.outbox_service import (
        OutboxService,
        get_outbox_service,
    )

    svc = get_outbox_service()
    assert isinstance(svc, OutboxService)
    assert svc.uow is None


def test_get_outbox_service_returns_new_each_time():
    from app.infrastructure.events.outbox_service import get_outbox_service

    svc1 = get_outbox_service()
    svc2 = get_outbox_service()
    assert svc1 is not svc2
