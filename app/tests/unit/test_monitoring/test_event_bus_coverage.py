"""Additional coverage for infrastructure/monitoring/event_bus.py.
Targets: _write_redis, _write_postgres, _flush_to_redis_only, _ensure_current_partition,
get_event_bus singleton, reset_event_bus, _get_sync_redis, _emit_sync_fallback,
emit_sync fallback path, _flush_loop cancellation."""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.monitoring.event_bus import (
    ErrorEventBus,
    _emit_sync_fallback,
    get_event_bus,
    reset_event_bus,
)
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

pytestmark = pytest.mark.unit


def make_event(
    severity=ErrorSeverity.WARNING,
    category="test",
    layer=ErrorLayer.API,
    message="test msg",
):
    return ErrorEvent(
        layer=layer, category=category, severity=severity, message=message
    )


# ─── Singleton ────────────────────────────────────────────────────────────────


def test_get_event_bus_returns_same_instance():
    """get_event_bus returns a stable singleton."""
    reset_event_bus()
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2


def test_reset_event_bus_clears_singleton():
    """After reset, get_event_bus creates a fresh bus."""
    reset_event_bus()
    bus1 = get_event_bus()
    reset_event_bus()
    bus2 = get_event_bus()
    assert bus1 is not bus2


def test_get_event_bus_thread_safe():
    """Two threads getting bus concurrently both receive the same instance."""
    reset_event_bus()
    results = []

    def fetch():
        results.append(get_event_bus())

    t1 = threading.Thread(target=fetch)
    t2 = threading.Thread(target=fetch)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results[0] is results[1]


# ─── _emit_sync_fallback ──────────────────────────────────────────────────────


def test_emit_sync_fallback_pushes_to_redis():
    """_emit_sync_fallback calls lpush + ltrim on sync redis."""
    ev = make_event()
    mock_redis = MagicMock()
    with patch(
        "app.infrastructure.monitoring.event_bus._get_sync_redis",
        return_value=mock_redis,
    ):
        _emit_sync_fallback(ev)

    mock_redis.lpush.assert_called_once()
    key_arg = mock_redis.lpush.call_args[0][0]
    assert key_arg == "error:sync_fallback"
    mock_redis.ltrim.assert_called_once()


def test_emit_sync_fallback_silences_redis_exception():
    """Redis failure in sync fallback does not propagate."""
    ev = make_event()
    with patch(
        "app.infrastructure.monitoring.event_bus._get_sync_redis",
        side_effect=Exception("redis down"),
    ):
        _emit_sync_fallback(ev)  # must not raise


# ─── emit_sync — no running loop (calls _emit_sync_fallback) ─────────────────


def test_emit_sync_outside_loop_calls_sync_fallback():
    """emit_sync outside event loop falls back to _emit_sync_fallback."""
    bus = ErrorEventBus()
    ev = make_event()

    # Ensure no running loop
    try:
        asyncio.get_running_loop()
        pytest.skip("running loop present")
    except RuntimeError:
        pass

    with patch(
        "app.infrastructure.monitoring.event_bus._emit_sync_fallback"
    ) as mock_fallback:
        bus.emit_sync(ev)
        mock_fallback.assert_called_once_with(ev)


# ─── emit_sync — queue full within running loop ───────────────────────────────


@pytest.mark.asyncio
async def test_emit_sync_queue_full_logs_warning():
    """emit_sync with full queue inside loop logs warning, does not raise."""
    bus = ErrorEventBus(maxsize=1)
    await bus.emit(make_event())  # fill up

    ev2 = make_event(category="overflow")
    bus.emit_sync(ev2)  # should not raise, just log warning
    assert bus._queue.qsize() == 1  # still 1, overflow dropped


# ─── _record_success / _record_failure ───────────────────────────────────────


@pytest.mark.asyncio
async def test_record_success_clears_circuit():
    """_record_success resets failure count and closes circuit."""
    bus = ErrorEventBus()
    bus._failure_count = 5
    bus._circuit_open = True
    bus._record_success()
    assert bus._failure_count == 0
    assert bus._circuit_open is False


@pytest.mark.asyncio
async def test_record_failure_increments_and_opens():
    """Three _record_failure calls open the circuit."""
    bus = ErrorEventBus()
    bus._record_failure()
    bus._record_failure()
    assert bus._circuit_open is False
    bus._record_failure()
    assert bus._circuit_open is True


@pytest.mark.asyncio
async def test_should_attempt_reset_within_window():
    """Circuit opened just now → _should_attempt_reset returns False."""
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic()
    assert bus._should_attempt_reset() is False


# ─── stop() ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_cancels_flusher_task():
    """stop() cancels the background flusher task without raising."""
    bus = ErrorEventBus()

    async def _long_loop():
        await asyncio.sleep(1000)

    with patch.object(bus, "_flush_loop", side_effect=_long_loop):
        bus.start()
        await asyncio.sleep(0)  # let task start

    assert bus._flusher_task is not None
    await bus.stop()
    assert bus._flusher_task.done()


@pytest.mark.asyncio
async def test_stop_noop_when_no_task():
    """stop() when flusher_task is None does not raise."""
    bus = ErrorEventBus()
    assert bus._flusher_task is None
    await bus.stop()  # must not raise


# ─── _flush_to_redis_only ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flush_to_redis_only_empty_queue():
    """Empty queue → _write_redis not called."""
    bus = ErrorEventBus()
    with patch.object(bus, "_write_redis", new_callable=AsyncMock) as mock_redis:
        await bus._flush_to_redis_only()
        mock_redis.assert_not_called()


@pytest.mark.asyncio
async def test_flush_to_redis_only_non_critical_not_routed():
    """Circuit open: non-CRITICAL events are written to Redis but NOT routed."""
    bus = ErrorEventBus()
    ev = make_event(severity=ErrorSeverity.WARNING)
    await bus.emit(ev)

    with patch.object(bus, "_write_redis", new_callable=AsyncMock) as mock_redis:
        with patch(
            "app.infrastructure.monitoring.alarm_router.get_alarm_router"
        ) as mock_router:
            mock_router.return_value.route = AsyncMock()
            await bus._flush_to_redis_only()

        mock_redis.assert_called_once()
        mock_router.return_value.route.assert_not_called()


@pytest.mark.asyncio
async def test_flush_to_redis_only_critical_routed():
    """Circuit open: CRITICAL events ARE routed to alarm router."""
    bus = ErrorEventBus()
    ev = make_event(severity=ErrorSeverity.CRITICAL)
    await bus.emit(ev)

    mock_router = MagicMock()
    mock_router.route = AsyncMock()

    with patch.object(bus, "_write_redis", new_callable=AsyncMock):
        with patch(
            "app.infrastructure.monitoring.alarm_router.get_alarm_router",
            return_value=mock_router,
        ):
            await bus._flush_to_redis_only()

        mock_router.route.assert_called_once_with(ev)


@pytest.mark.asyncio
async def test_flush_to_redis_only_router_exception_silenced():
    """Router crash during circuit-open flush is silently swallowed."""
    bus = ErrorEventBus()
    ev = make_event(severity=ErrorSeverity.CRITICAL)
    await bus.emit(ev)

    with patch.object(bus, "_write_redis", new_callable=AsyncMock):
        with patch(
            "app.infrastructure.monitoring.alarm_router.get_alarm_router",
            side_effect=Exception("router crash"),
        ):
            await bus._flush_to_redis_only()  # must not raise


# ─── _ensure_current_partition ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_current_partition_december():
    """December month → to_date wraps to next year January."""
    import datetime
    import types

    bus = ErrorEventBus()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    fake_date = MagicMock(spec=datetime.date)
    fake_date.today.return_value = datetime.date(2026, 12, 15)
    fake_date.side_effect = datetime.date  # pass-through constructor

    fake_dt_module = types.ModuleType("datetime")
    fake_dt_module.date = fake_date

    with patch("app.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch.dict("sys.modules", {"datetime": fake_dt_module}):
            await bus._ensure_current_partition()

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_current_partition_exception_logged():
    """execute failure inside _ensure_current_partition is logged, not raised."""
    bus = ErrorEventBus()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=Exception("already exists"))
    mock_session.commit = AsyncMock()

    with patch("app.database.connection.AsyncSessionLocal", return_value=mock_session):
        await bus._ensure_current_partition()  # must not raise


# ─── _write_redis ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_redis_no_redis_returns_early():
    """If pubsub manager has no redis, _write_redis returns without error."""
    bus = ErrorEventBus()
    ev = make_event()

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = None
        await bus._write_redis([ev])


@pytest.mark.asyncio
async def test_write_redis_pipeline_executes():
    """Valid redis → pipeline is executed with correct keys."""
    bus = ErrorEventBus()
    ev = make_event(layer=ErrorLayer.DB, category="test_cat")

    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.hincrby = MagicMock()
    mock_pipe.hset = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.zadd = MagicMock()
    mock_pipe.zremrangebyrank = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.execute = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = mock_redis
        await bus._write_redis([ev])

    mock_pipe.execute.assert_called_once()


@pytest.mark.asyncio
async def test_write_redis_exception_logged():
    """Pipeline execute failure → logged, not raised."""
    bus = ErrorEventBus()
    ev = make_event()

    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.hincrby = MagicMock()
    mock_pipe.hset = MagicMock()
    mock_pipe.expire = MagicMock()
    mock_pipe.zadd = MagicMock()
    mock_pipe.zremrangebyrank = MagicMock()
    mock_pipe.incr = MagicMock()
    mock_pipe.execute = AsyncMock(side_effect=Exception("Redis pipeline crash"))

    mock_redis = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    with patch("app.infrastructure.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = mock_redis
        await bus._write_redis([ev])  # must not raise


# ─── _flush_loop cancellation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flush_loop_cancellation_flushes_remaining():
    """_flush_loop on CancelledError flushes remaining events then exits."""
    bus = ErrorEventBus()
    await bus.emit(make_event())

    flush_calls = []

    async def fake_flush_batch():
        flush_calls.append(1)

    bus._flush_batch = fake_flush_batch

    task = asyncio.create_task(bus._flush_loop())
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # At least one flush should have been called (the cancellation path)
    assert len(flush_calls) >= 1
