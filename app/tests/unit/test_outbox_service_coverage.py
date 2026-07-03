"""OutboxService tests — real DB, no mocked UoW/session.

The transactional outbox is a reliability-critical seam, so previously mocking the
UnitOfWork/session and asserting inner calls (session.add.assert_called_once(),
mock_uow.commit.assert_called_once()) hid the actual persistence contract. Here the
service runs against the real test DB (db_session monkeypatches AsyncSessionLocal,
so both save_event's UoW and relay_pending_events' internal UnitOfWork use the test
session) and we assert the real outbox_events rows (saved / processed / retried).

Only the event bus (external Redis pub/sub) and the shutdown flag are stubbed —
calling those for real would mean live Redis / process-shutdown machinery.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import insert, select

from app.database.models import OutboxEvent
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.outbox_service import OutboxService, get_outbox_service

pytestmark = pytest.mark.integration
_BUS = "app.infrastructure.events.outbox_service.get_event_bus"
_STOPPING = "app.infrastructure.events.outbox_service.is_stopping"


async def _seed_outbox(
    db_session,
    event_type="sefer_added",
    payload=None,
    *,
    processed=False,
    retry_count=0,
) -> int:
    oid = (
        await db_session.execute(
            insert(OutboxEvent).values(
                event_type=event_type,
                payload=payload or {},
                processed=processed,
                retry_count=retry_count,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return oid


async def _get_outbox(db_session, oid):
    return (
        await db_session.execute(select(OutboxEvent).where(OutboxEvent.id == oid))
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# save_event                                                                   #
# --------------------------------------------------------------------------- #


async def test_save_event_returns_id(db_session):
    """save_event persists a real outbox_events row and returns its id."""
    async with UnitOfWork() as uow:
        result = await OutboxService(uow=uow).save_event("sefer_added", {"sefer_id": 1})
        await uow.commit()

    assert isinstance(result, int) and result > 0
    row = await _get_outbox(db_session, result)
    assert row is not None
    assert row.event_type == "sefer_added"
    assert row.payload == {"sefer_id": 1}
    assert row.processed is False


async def test_save_event_raises_without_uow():
    """No UoW → RuntimeError (no DB needed)."""
    with pytest.raises(RuntimeError, match="UnitOfWork"):
        await OutboxService().save_event("test_event", {})


async def test_save_event_uses_passed_uow_over_instance_uow(db_session):
    """An explicit uow param is honoured and the event is persisted through it."""
    async with UnitOfWork() as uow:
        result = await OutboxService().save_event("yakit_added", {"x": 1}, uow=uow)
        await uow.commit()

    row = await _get_outbox(db_session, result)
    assert row is not None and row.event_type == "yakit_added"


async def test_save_event_uses_correlation_id(db_session):
    """correlation_id from the request context is stored on the real row."""
    with patch(
        "app.infrastructure.events.outbox_service.get_correlation_id",
        return_value="test-correlation-xyz",
    ):
        async with UnitOfWork() as uow:
            result = await OutboxService(uow=uow).save_event("yakit_added", {"lt": 100})
            await uow.commit()

    row = await _get_outbox(db_session, result)
    assert row.correlation_id == "test-correlation-xyz"


async def test_save_event_payload_stored(db_session):
    """The payload dict is persisted verbatim on the real row."""
    async with UnitOfWork() as uow:
        result = await OutboxService(uow=uow).save_event(
            "arac_updated", {"arac_id": 3, "plaka": "34ABC"}
        )
        await uow.commit()

    row = await _get_outbox(db_session, result)
    assert row.payload == {"arac_id": 3, "plaka": "34ABC"}


# --------------------------------------------------------------------------- #
# relay_pending_events                                                         #
# --------------------------------------------------------------------------- #


async def test_relay_pending_events_returns_zero_when_empty(db_session):
    """No pending rows → 0 (and the bus is never consulted)."""
    count = await OutboxService().relay_pending_events()
    assert count == 0


async def test_relay_pending_events_processes_events(db_session):
    """A pending row is dispatched and marked processed in the real DB."""
    oid = await _seed_outbox(db_session, "sefer_added", {"id": 1})

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()
    with patch(_BUS, return_value=mock_bus), patch(_STOPPING, return_value=False):
        count = await OutboxService().relay_pending_events()

    assert count == 1
    mock_bus.publish_async.assert_called_once()
    row = await _get_outbox(db_session, oid)
    assert row.processed is True
    assert row.processed_at is not None


async def test_relay_pending_events_increments_retry_on_failure(db_session):
    """If publish fails, the real row's retry_count/error_message are updated."""
    oid = await _seed_outbox(db_session, "sefer_added", {}, retry_count=0)

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock(side_effect=RuntimeError("bus error"))
    with patch(_BUS, return_value=mock_bus), patch(_STOPPING, return_value=False):
        count = await OutboxService().relay_pending_events()

    assert count == 0
    row = await _get_outbox(db_session, oid)
    assert row.retry_count == 1
    assert row.processed is False
    assert "bus error" in (row.error_message or "")


async def test_relay_pending_events_stops_on_shutdown(db_session):
    """is_stopping() True → break before processing; no row is touched."""
    oid = await _seed_outbox(db_session, "sefer_added", {})

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()
    with patch(_BUS, return_value=mock_bus), patch(_STOPPING, return_value=True):
        count = await OutboxService().relay_pending_events()

    assert count == 0
    mock_bus.publish_async.assert_not_called()
    row = await _get_outbox(db_session, oid)
    assert row.processed is False


async def test_relay_pending_events_commits(db_session):
    """The processed flag is persisted (relay commits the real transaction)."""
    oid = await _seed_outbox(db_session, "sefer_added", {})

    mock_bus = AsyncMock()
    mock_bus.publish_async = AsyncMock()
    with patch(_BUS, return_value=mock_bus), patch(_STOPPING, return_value=False):
        await OutboxService().relay_pending_events()

    row = await _get_outbox(db_session, oid)
    assert row.processed is True


# --------------------------------------------------------------------------- #
# get_outbox_service factory                                                   #
# --------------------------------------------------------------------------- #


def test_get_outbox_service_returns_instance():
    svc = get_outbox_service()
    assert isinstance(svc, OutboxService)
    assert svc.uow is None


def test_get_outbox_service_returns_new_each_time():
    assert get_outbox_service() is not get_outbox_service()
