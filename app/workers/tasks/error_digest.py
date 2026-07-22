"""
Error monitoring Celery tasks:
 - monitoring.error_digest        : 5-min digest + materialized view refresh
 - monitoring.create_monthly_partition: create next month's error_occurrences partition
"""

import asyncio
from typing import cast

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="monitoring.error_digest",
    max_retries=0,
    ignore_result=True,
)
def error_digest(self):
    """Send 5-minute error summary to Telegram if any error-level events accumulated."""
    asyncio.run(_run_digest())


async def _drain_sync_fallback(redis) -> None:
    """Route events that were pushed to error:sync_fallback from sync contexts."""
    import json

    from v2.modules.platform_infra.monitoring.alarm_router import get_alarm_router
    from v2.modules.platform_infra.monitoring.models import ErrorEvent

    try:
        items = await redis.lrange("error:sync_fallback", 0, -1)
        if not items:
            return
        await redis.delete("error:sync_fallback")
        router = get_alarm_router()
        for raw in items:
            try:
                data = json.loads(raw)
                ev = ErrorEvent(
                    layer=data["layer"],
                    category=data["category"],
                    severity=data["severity"],
                    message=data["message"],
                    trace_id=data.get("trace_id", ""),
                    path=data.get("path", ""),
                    stack_trace=data.get("stack_trace", ""),
                    metadata=data.get("metadata", {}),
                )
                await router.route(ev)
            except Exception as exc:
                logger.warning("sync_fallback item parse/route failed: %s", exc)
    except Exception as exc:
        logger.warning("sync_fallback drain failed: %s", exc)


async def _run_digest() -> None:
    from v2.modules.notification.public import notify_error
    from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

    mgr = get_pubsub_manager()
    redis = mgr.redis
    if redis is None:
        return

    await _drain_sync_fallback(redis)

    try:
        keys = await redis.keys("error:digest:*")
    except Exception as exc:
        logger.warning("Digest Redis scan failed: %s", exc)
        return

    if not keys:
        return

    pipe = redis.pipeline()
    for key in keys:
        pipe.hgetall(key)
    results = await pipe.execute()

    layer_totals: dict[str, int] = {}
    lines: list[str] = []
    for key, data in zip(keys, results):
        if not data:
            continue
        # pubsub redis decode_responses=True → key str, data dict[str, str];
        # redis-py stub'ı decode moduna bakmadan bytes tipliyor.
        key = cast(str, key)
        data = cast("dict[str, str]", data)
        parts = key.split(":", 3)  # error:digest:{layer}:{category}
        if len(parts) < 4:
            continue
        layer = parts[2]
        category = parts[3]
        count = int(data.get("count", "1"))
        sample = data.get("message_sample", "")[:100]
        layer_totals[layer] = layer_totals.get(layer, 0) + count
        lines.append(f"  • {layer}/{category}: {count}× — {sample}")

    if not lines:
        return

    summary_parts = [f"{layer}: {cnt}" for layer, cnt in sorted(layer_totals.items())]
    header = f"📊 5dk Özet — {', '.join(summary_parts)}"
    body = "\n".join(lines[:20])
    if len(lines) > 20:
        body += f"\n  …ve {len(lines) - 20} daha"

    await notify_error(level="error", message=f"{header}\n{body}", path="digest")

    del_pipe = redis.pipeline()
    for key in keys:
        del_pipe.delete(key)
    await del_pipe.execute()

    try:
        from sqlalchemy import text

        from v2.modules.platform_infra.database.connection import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY error_hourly_stats")
            )
            await session.commit()
    except Exception as exc:
        logger.warning("error_hourly_stats refresh failed: %s", exc)

    # Check Celery beat health
    from v2.modules.platform_infra.monitoring.celery_probe import check_beat_health

    await check_beat_health()

    # Check queue depth
    await _check_queue_depth()


async def _check_queue_depth() -> None:
    """Emit warning if Celery queue backlog grows large."""
    try:
        import asyncio

        from app.infrastructure.background.celery_app import (
            celery_app as _app,
        )
        from v2.modules.platform_infra.monitoring import aemit
        from v2.modules.platform_infra.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        inspect = _app.control.inspect(timeout=2.0)
        reserved = await asyncio.to_thread(inspect.reserved)
        if not reserved:
            return
        total = sum(len(v) for v in reserved.values())
        if total > 100:
            sev = ErrorSeverity.ERROR if total > 500 else ErrorSeverity.WARNING
            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.CELERY,
                    category="queue_backlog",
                    severity=sev,
                    message=f"Celery queue depth: {total} pending tasks",
                    metadata={"queued_tasks": total},
                )
            )
    except Exception as exc:
        logger.debug("Queue depth check failed: %s", exc)


@celery_app.task(
    bind=True,
    name="monitoring.create_monthly_partition",
    max_retries=0,
    ignore_result=True,
)
def create_monthly_partition(self):
    """Create next month's error_occurrences partition on the 28th of each month."""
    asyncio.run(_create_partition())


async def _create_partition() -> None:
    import datetime

    from sqlalchemy import text

    from v2.modules.platform_infra.database.connection import AsyncSessionLocal

    today = datetime.date.today()

    # Create current month + next month partitions
    months_to_create = []

    # Current month
    months_to_create.append((today.year, today.month))

    # Next month
    if today.month == 12:
        months_to_create.append((today.year + 1, 1))
    else:
        months_to_create.append((today.year, today.month + 1))

    async with AsyncSessionLocal() as session:
        for year, month in months_to_create:
            partition_name = f"error_occurrences_{year}_{month:02d}"
            from_date = datetime.date(year, month, 1)
            if month == 12:
                to_date = datetime.date(year + 1, 1, 1)
            else:
                to_date = datetime.date(year, month + 1, 1)

            try:
                await session.execute(
                    text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF error_occurrences
                    FOR VALUES FROM ('{from_date}') TO ('{to_date}');
                """)
                )
                logger.info("Created partition %s", partition_name)
            except Exception as e:
                logger.warning(
                    "Failed to create partition %s: %s", partition_name, str(e)
                )

        await session.commit()


@celery_app.task(
    bind=True,
    name="monitoring.db_health_check",
    max_retries=0,
    ignore_result=True,
)
def db_health_check(self):
    """Detect long-running transactions, lock waits, and table bloat."""
    from v2.modules.platform_infra.database.connection import engine

    try:
        asyncio.run(_db_health_check())
    except RuntimeError as e:
        if (
            "greenlet" in str(e)
            or "different loop" in str(e)
            or "Event loop is closed" in str(e)
        ):
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "AsyncIO event loop conflict in Celery worker: %s. Skipping DB health check.",
                e,
            )
        else:
            raise
    finally:
        # Dispose pool connections bound to the now-closed event loop so the
        # next asyncio.run() call starts with a clean pool on its own loop.
        try:
            engine.sync_engine.pool.dispose(close=False)
        except Exception:
            pass


async def _db_health_check() -> None:
    from sqlalchemy import text

    from v2.modules.platform_infra.database.connection import AsyncSessionLocal
    from v2.modules.platform_infra.monitoring import aemit
    from v2.modules.platform_infra.monitoring.models import (
        ErrorEvent,
        ErrorLayer,
        ErrorSeverity,
    )

    async with AsyncSessionLocal() as session:
        # Long-running transactions (>30s)
        rows = await session.execute(
            text("""
            SELECT pid,
                   EXTRACT(EPOCH FROM (now() - xact_start))::int AS duration_sec,
                   LEFT(query, 200) AS query_excerpt,
                   state
            FROM pg_stat_activity
            WHERE xact_start IS NOT NULL
              AND now() - xact_start > interval '30 seconds'
              AND state != 'idle'
              AND pid != pg_backend_pid()
        """)
        )
        for row in rows:
            sev = (
                ErrorSeverity.CRITICAL
                if row.duration_sec > 120
                else ErrorSeverity.ERROR
            )
            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category="long_running_tx",
                    severity=sev,
                    message=f"Long TX: {row.duration_sec}s — {row.query_excerpt}",
                    metadata={
                        "pid": row.pid,
                        "duration_sec": row.duration_sec,
                        "state": row.state,
                    },
                )
            )

        # Lock wait chains
        rows = await session.execute(
            text("""
            SELECT blocked.pid AS blocked_pid,
                   blocking.pid AS blocking_pid,
                   LEFT(blocked.query, 200) AS blocked_query,
                   EXTRACT(EPOCH FROM (now() - blocked.query_start))::int AS wait_sec
            FROM pg_stat_activity blocked
            JOIN pg_stat_activity blocking
              ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
            WHERE blocked.wait_event_type = 'Lock'
        """)
        )
        for row in rows:
            sev = ErrorSeverity.CRITICAL if row.wait_sec > 15 else ErrorSeverity.ERROR
            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category="lock_wait",
                    severity=sev,
                    message=(
                        f"Lock wait {row.wait_sec}s: "
                        f"pid {row.blocked_pid} blocked by {row.blocking_pid}"
                    ),
                    metadata={
                        "blocked_pid": row.blocked_pid,
                        "blocking_pid": row.blocking_pid,
                        "wait_sec": row.wait_sec,
                        "query": row.blocked_query,
                    },
                )
            )

        # Table bloat (dead tuple ratio >20%)
        rows = await session.execute(
            text("""
            SELECT relname,
                   n_dead_tup,
                   n_live_tup,
                   ROUND(
                       n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100,
                       1
                   ) AS dead_pct
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 5000
              AND n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) > 0.20
            ORDER BY dead_pct DESC
            LIMIT 10
        """)
        )
        for row in rows:
            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category="table_bloat",
                    severity=ErrorSeverity.WARNING,
                    message=(
                        f"Table '{row.relname}' bloat: "
                        f"{row.dead_pct}% dead tuples ({row.n_dead_tup:,})"
                    ),
                    metadata={
                        "table": row.relname,
                        "dead_pct": float(row.dead_pct),
                        "dead_tuples": row.n_dead_tup,
                    },
                )
            )
