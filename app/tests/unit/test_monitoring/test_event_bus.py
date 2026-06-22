import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.monitoring.event_bus import ErrorEventBus
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


def make_event(severity=ErrorSeverity.WARNING, category="test"):
    return ErrorEvent(
        layer=ErrorLayer.DB, category=category, severity=severity, message="test error"
    )


@pytest.mark.unit
async def test_emit_adds_to_queue():
    bus = ErrorEventBus()
    ev = make_event()
    await bus.emit(ev)
    assert bus._queue.qsize() == 1


@pytest.mark.unit
async def test_emit_sync_adds_to_queue():
    bus = ErrorEventBus()
    ev = make_event()
    bus.emit_sync(ev)
    assert bus._queue.qsize() == 1


@pytest.mark.unit
async def test_queue_full_drops_event():
    bus = ErrorEventBus(maxsize=2)
    for _ in range(3):
        await bus.emit(make_event())
    # Queue holds 2; 3rd was dropped
    assert bus._queue.qsize() == 2


@pytest.mark.unit
async def test_circuit_breaker_opens_after_3_failures():
    bus = ErrorEventBus()
    bus._failure_count = 3
    bus._check_circuit()
    assert bus._circuit_open is True


@pytest.mark.unit
async def test_circuit_resets_after_half_open():
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic() - 61
    assert bus._should_attempt_reset() is True


@pytest.mark.unit
def test_emit_sync_no_loop_drops_silently():
    """emit_sync must not raise when called outside an event loop."""
    # Verify there is no running loop in this sync context
    try:
        asyncio.get_running_loop()
        pytest.skip("running loop present — cannot test no-loop path")
    except RuntimeError:
        pass
    bus = ErrorEventBus()
    bus.emit_sync(make_event())  # must not raise
    # Queue is empty because no loop was running
    assert bus._queue.qsize() == 0


# ─── Circuit Breaker: _flush_batch integration ─────────────────────────────────


@pytest.mark.unit
async def test_flush_batch_circuit_open_skips_postgres():
    """Circuit open (within 60s) → _flush_to_redis_only, _write_postgres not called."""
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic()  # just opened, <60s
    await bus.emit(make_event())

    with (
        patch.object(
            bus, "_flush_to_redis_only", new_callable=AsyncMock
        ) as mock_redis_only,
        patch.object(bus, "_write_postgres", new_callable=AsyncMock) as mock_pg,
    ):
        await bus._flush_batch()
        mock_redis_only.assert_called_once()
        mock_pg.assert_not_called()


@pytest.mark.unit
async def test_flush_batch_half_open_resets_circuit_on_success():
    """Circuit open + 60s elapsed → circuit reset → PG write → success."""
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic() - 61
    bus._failure_count = 3
    await bus.emit(make_event())

    # Patch get_alarm_router at the alarm_router module level (it's imported inside _flush_batch)
    with (
        patch.object(bus, "_write_redis", new_callable=AsyncMock),
        patch.object(bus, "_write_postgres", new_callable=AsyncMock),
        patch(
            "app.infrastructure.monitoring.alarm_router.get_alarm_router",
            side_effect=ImportError,
        ),
    ):
        await bus._flush_batch()

    assert bus._circuit_open is False
    assert bus._failure_count == 0


@pytest.mark.unit
async def test_flush_batch_pg_failure_opens_circuit():
    """_write_postgres raises → failure count increments → after threshold circuit opens."""
    bus = ErrorEventBus()

    async def _one_flush():
        mock_router = MagicMock()
        mock_router.route = AsyncMock()
        with (
            patch.object(bus, "_write_redis", new_callable=AsyncMock),
            patch.object(bus, "_write_postgres", side_effect=Exception("DB down")),
            patch(
                "app.infrastructure.monitoring.alarm_router.AlarmRouter",
                return_value=mock_router,
            ),
        ):
            await bus._flush_batch()

    # Need to emit one event per flush (queue is drained each call)
    for _ in range(3):
        await bus.emit(make_event())
        await _one_flush()

    assert bus._circuit_open is True


@pytest.mark.unit
async def test_flush_batch_empty_does_not_call_writes():
    """Empty queue → no Redis/PG write, failure_count unchanged."""
    bus = ErrorEventBus()
    bus._failure_count = 2

    with (
        patch.object(bus, "_write_redis", new_callable=AsyncMock) as mock_redis,
        patch.object(bus, "_write_postgres", new_callable=AsyncMock) as mock_pg,
    ):
        await bus._flush_batch()
        mock_redis.assert_not_called()
        mock_pg.assert_not_called()

    assert bus._failure_count == 2


@pytest.mark.unit
async def test_flush_batch_routing_exception_does_not_skip_postgres():
    """AlarmRouter crash → PG write still called."""
    bus = ErrorEventBus()
    await bus.emit(make_event())

    mock_router = MagicMock()
    mock_router.route = AsyncMock(side_effect=Exception("router crash"))

    with (
        patch.object(bus, "_write_redis", new_callable=AsyncMock),
        patch.object(bus, "_write_postgres", new_callable=AsyncMock) as mock_pg,
        patch(
            "app.infrastructure.monitoring.alarm_router.get_alarm_router",
            return_value=mock_router,
        ),
    ):
        await bus._flush_batch()
        mock_pg.assert_called_once()


@pytest.mark.unit
async def test_double_start_reuses_existing_task():
    """start() twice → flusher_task is the same object (no double task)."""
    bus = ErrorEventBus()

    # Patch _flush_loop as a coroutine function that sleeps briefly
    async def _dummy_loop(*args, **kwargs):
        await asyncio.sleep(10)

    with patch.object(bus, "_flush_loop", side_effect=_dummy_loop):
        bus.start()
        task_first = bus._flusher_task
        bus.start()
        task_second = bus._flusher_task

    assert task_first is task_second

    # cleanup
    if task_first and not task_first.done():
        task_first.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task_first
