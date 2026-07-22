from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from app.infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from app.infrastructure.monitoring.models import ErrorEvent

logger = get_logger(__name__)

# Numeric ordering for severity deduplication — string comparison of
# "critical"/"error"/"warning" is alphabetical (c<e<w) which is the
# inverse of intended severity order.
_SEVERITY_ORDER: dict[str, int] = {"warning": 1, "error": 2, "critical": 3}

_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_RESET_SECONDS = 60
_FLUSH_INTERVAL_SECONDS = 5
_FLUSH_BATCH_SIZE = 200

_sync_redis_client = None
_sync_redis_lock = threading.Lock()


def _get_sync_redis():
    global _sync_redis_client
    if _sync_redis_client is None:
        with _sync_redis_lock:
            if _sync_redis_client is None:
                import redis as _redis

                from app.config import settings

                _sync_redis_client = _redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    max_connections=2,
                )
    return _sync_redis_client


def _emit_sync_fallback(event: "ErrorEvent") -> None:
    """Redis-list fallback for sync contexts (Celery workers, tests)."""
    try:
        r = _get_sync_redis()
        payload = json.dumps(event.to_dict(), default=str, ensure_ascii=False)
        r.lpush("error:sync_fallback", payload)
        r.ltrim("error:sync_fallback", 0, 999)  # cap at 1000 entries
    except Exception as exc:
        logger.debug("sync_fallback failed: %s", exc)


class ErrorEventBus:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[ErrorEvent] = asyncio.Queue(maxsize=maxsize)
        self._circuit_open = False
        self._failure_count = 0
        self._circuit_opened_at: float = 0.0
        self._flusher_task: asyncio.Task | None = None

    async def emit(self, event: ErrorEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.error(
                "ErrorEventBus queue full — event dropped: %s/%s",
                event.layer.value,
                event.category,
            )

    def emit_sync(self, event: ErrorEvent) -> None:
        try:
            asyncio.get_running_loop()
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "ErrorEventBus queue full (sync) — event dropped: %s/%s",
                    event.layer.value,
                    event.category,
                )
        except RuntimeError:
            _emit_sync_fallback(event)

    def start(self) -> None:
        # Fix 3: guard against double-start
        if self._flusher_task is not None and not self._flusher_task.done():
            return
        self._flusher_task = asyncio.create_task(
            self._flush_loop(), name="error-bus-flusher"
        )

    async def stop(self) -> None:
        if self._flusher_task and not self._flusher_task.done():
            self._flusher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flusher_task

    def _check_circuit(self) -> None:
        if self._failure_count >= _CIRCUIT_FAILURE_THRESHOLD:
            self._circuit_open = True
            self._circuit_opened_at = time.monotonic()

    def _should_attempt_reset(self) -> bool:
        return (
            self._circuit_open
            and (time.monotonic() - self._circuit_opened_at) > _CIRCUIT_RESET_SECONDS
        )

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._check_circuit()

    async def _flush_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_FLUSH_INTERVAL_SECONDS)
                await self._flush_batch()
            except asyncio.CancelledError:
                await self._flush_batch()
                return
            except Exception as exc:
                logger.error("ErrorEventBus flusher error: %s", exc)

    async def _flush_batch(self) -> None:
        if self._circuit_open and not self._should_attempt_reset():
            await self._flush_to_redis_only()
            return

        # Force hard reset on half-open (past 60s window)
        if self._should_attempt_reset():
            self._failure_count = 0
            self._circuit_open = False

        batch: list[ErrorEvent] = []
        try:
            while len(batch) < _FLUSH_BATCH_SIZE and not self._queue.empty():
                batch.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        # Fix 1: do NOT call _record_success() on empty batch — only reset after a
        # real successful PG write to avoid phantom circuit-breaker resets.
        if not batch:
            return

        await self._write_redis(batch)

        try:
            from app.infrastructure.monitoring.alarm_router import get_alarm_router

            router = get_alarm_router()
            for ev in batch:
                await router.route(ev)
        except ImportError:
            pass  # alarm_router not yet available
        except Exception as exc:
            logger.warning("ErrorEventBus alarm routing failed: %s", exc)
            # Continue to PostgreSQL write — routing failure must not drop events

        try:
            await self._write_postgres(batch)
            self._record_success()
        except Exception as exc:
            logger.error("ErrorEventBus PostgreSQL write failed: %s", exc)
            self._record_failure()
            if self._circuit_open:
                logger.critical(
                    "ErrorEventBus circuit OPEN — switching to Redis-only mode"
                )

    async def _write_redis(self, batch: list[ErrorEvent]) -> None:
        from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        # Fix 5: use public .redis property instead of private ._redis
        if mgr.redis is None:
            return
        try:
            async with mgr.redis.pipeline(transaction=True) as pipe:
                for ev in batch:
                    key = f"error:fp:{ev.fingerprint}"
                    pipe.hincrby(key, "count", 1)
                    pipe.hset(key, "last_seen", ev.occurred_at.isoformat())
                    pipe.hset(key, "severity", ev.severity.value)
                    pipe.expire(key, 86400)
                    stream_key = f"error:stream:{ev.severity.value}"
                    payload = json.dumps(ev.to_dict(), ensure_ascii=False, default=str)
                    pipe.zadd(stream_key, {payload: ev.occurred_at.timestamp()})
                    pipe.zremrangebyrank(stream_key, 0, -1001)
                    hour_key = (
                        f"error:hourly:{ev.layer.value}:{ev.category}"
                        f":{ev.occurred_at.strftime('%Y%m%d%H')}"
                    )
                    pipe.incr(hour_key)
                    pipe.expire(hour_key, 86400 * 2)
                await pipe.execute()
        except Exception as exc:
            logger.warning("ErrorEventBus Redis write failed: %s", exc)

    async def _write_postgres(self, batch: list[ErrorEvent]) -> None:
        # Fix 2: bulk insert — single INSERT per table for the whole batch
        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        # Pre-aggregate: deduplicate by fingerprint to avoid
        # "ON CONFLICT DO UPDATE command cannot affect row a second time"
        aggregated: dict[str, ErrorEvent] = {}
        fp_counts: dict[str, int] = defaultdict(int)
        for ev in batch:
            fp_counts[ev.fingerprint] += 1
            if ev.fingerprint in aggregated:
                existing = aggregated[ev.fingerprint]
                if _SEVERITY_ORDER.get(ev.severity.value, 0) > _SEVERITY_ORDER.get(
                    existing.severity.value, 0
                ):
                    aggregated[ev.fingerprint] = ev
            else:
                aggregated[ev.fingerprint] = ev
        deduped = list(aggregated.values())

        # Build bulk INSERT for error_events
        ev_val_parts = []
        ev_params: dict = {}
        for i, ev in enumerate(deduped):
            ev_val_parts.append(
                f"(:fp{i}, :layer{i}, :category{i}, :severity{i}, :message{i},"
                f" :count{i}, :now{i}, :now{i}, :trace_id{i}, :path{i}, :stack{i},"
                f" CAST(:meta{i} AS jsonb))"
            )
            ev_params.update(
                {
                    f"fp{i}": ev.fingerprint,
                    f"layer{i}": ev.layer.value,
                    f"category{i}": ev.category,
                    f"severity{i}": ev.severity.value,
                    f"message{i}": ev.message,
                    f"count{i}": fp_counts[ev.fingerprint],
                    f"now{i}": ev.occurred_at,
                    f"trace_id{i}": ev.trace_id or None,
                    f"path{i}": ev.path or None,
                    f"stack{i}": ev.stack_trace or None,
                    f"meta{i}": json.dumps(ev.metadata, default=str),
                }
            )

        ev_values_sql = ", ".join(ev_val_parts)
        ev_insert_sql = f"""
            INSERT INTO error_events
                (fingerprint, layer, category, severity, message,
                 count, first_seen, last_seen,
                 trace_id, path, stack_trace, metadata)
            VALUES {ev_values_sql}
            ON CONFLICT (fingerprint) WHERE resolved_at IS NULL
            DO UPDATE SET
                count     = error_events.count + EXCLUDED.count,
                last_seen = EXCLUDED.last_seen,
                severity  = CASE
                    WHEN EXCLUDED.severity::text = 'critical'
                        THEN 'critical'::error_severity
                    ELSE error_events.severity
                END,
                metadata  = error_events.metadata || EXCLUDED.metadata
        """

        # Build bulk INSERT for error_occurrences
        occ_val_parts = []
        occ_params: dict = {}
        for i, ev in enumerate(batch):
            occ_val_parts.append(
                f"(:ofp{i}, :olayer{i}, :oseverity{i}, :otrace_id{i},"
                f" CAST(:ometa{i} AS jsonb), :onow{i})"
            )
            occ_params.update(
                {
                    f"ofp{i}": ev.fingerprint,
                    f"olayer{i}": ev.layer.value,
                    f"oseverity{i}": ev.severity.value,
                    f"otrace_id{i}": ev.trace_id or None,
                    f"ometa{i}": json.dumps(ev.metadata, default=str),
                    f"onow{i}": ev.occurred_at,
                }
            )

        occ_values_sql = ", ".join(occ_val_parts)
        occ_insert_sql = f"""
            INSERT INTO error_occurrences
                (fingerprint, layer, severity, trace_id, metadata, occurred_at)
            VALUES {occ_values_sql}
        """

        async with AsyncSessionLocal() as session:
            await session.execute(text(ev_insert_sql), ev_params)
            try:
                await session.execute(text(occ_insert_sql), occ_params)
                await session.commit()
            except Exception as e:
                error_str = str(e).lower()
                if "no partition" in error_str or "partition" in error_str:
                    logger.warning(
                        "Partition error on error_occurrences insert — creating partition: %s",
                        str(e)[:100],
                    )
                    await session.rollback()
                    await self._ensure_current_partition()
                    # Retry once after creating partition
                    async with AsyncSessionLocal() as retry_session:
                        await retry_session.execute(text(ev_insert_sql), ev_params)
                        await retry_session.execute(text(occ_insert_sql), occ_params)
                        await retry_session.commit()
                else:
                    raise

    async def _ensure_current_partition(self) -> None:
        """Ensure current month partition exists for error_occurrences."""
        import datetime

        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        today = datetime.date.today()
        partition_name = f"error_occurrences_{today.year}_{today.month:02d}"
        from_date = datetime.date(today.year, today.month, 1)
        if today.month == 12:
            to_date = datetime.date(today.year + 1, 1, 1)
        else:
            to_date = datetime.date(today.year, today.month + 1, 1)

        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF error_occurrences
                    FOR VALUES FROM ('{from_date}') TO ('{to_date}');
                """)
                )
                await session.commit()
                logger.info("Created partition %s", partition_name)
            except Exception as e:
                logger.warning(
                    "Failed to create partition %s: %s", partition_name, str(e)
                )

    async def _flush_to_redis_only(self) -> None:
        batch: list[ErrorEvent] = []
        while len(batch) < _FLUSH_BATCH_SIZE and not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if not batch:
            return
        await self._write_redis(batch)
        # Even with circuit open, route CRITICAL events to Telegram so they're not silently lost.
        try:
            from app.infrastructure.monitoring.alarm_router import get_alarm_router
            from app.infrastructure.monitoring.models import ErrorSeverity

            router = get_alarm_router()
            for ev in batch:
                if ev.severity == ErrorSeverity.CRITICAL:
                    await router.route(ev)
        except Exception as exc:
            logger.debug("Circuit-open alarm routing failed: %s", exc)


_bus: ErrorEventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> ErrorEventBus:
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = ErrorEventBus()
    return _bus


def reset_event_bus() -> None:
    global _bus
    with _bus_lock:
        _bus = None
