# Error Detector — Plan 2: Backend Probes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 6 backend probes (DB, Celery, Service, External API, Security, ML) and wire them together via `activate_all_probes()`.

**Architecture:** Each probe is a standalone module under `app/infrastructure/monitoring/`. Probes call `emit()` / `aemit()` from `app/infrastructure/monitoring/__init__.py`. All are activated once in `lifespan` via `activate_all_probes(engine, celery_app)`.

**Tech Stack:** SQLAlchemy event system, Celery signals, contextvars, httpx event_hooks, asyncio exception handler.

**Depends on:** Plan 1 (ErrorEventBus + ErrorEvent models must exist).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `app/infrastructure/monitoring/db_probe.py` | SQLAlchemy events: timing, EXPLAIN, pool, N+1, PG stats |
| Create | `app/infrastructure/monitoring/celery_probe.py` | Celery signals: failure, retry, heartbeat, queue, memory |
| Create | `app/infrastructure/monitoring/service_probe.py` | @monitor_errors, @intentional_fallback, assert_invariant, call chain |
| Create | `app/infrastructure/monitoring/external_api_probe.py` | httpx event_hooks wrapper |
| Create | `app/infrastructure/monitoring/security_probe.py` | BruteForceDetector, JWT anomaly, RBAC aggregation |
| Create | `app/infrastructure/monitoring/ml_probe.py` | Fallback rate tracker |
| Create | `app/infrastructure/monitoring/activate.py` | activate_all_probes() entry point |
| Modify | `app/main.py` | Call activate_all_probes in lifespan |
| Modify | `app/infrastructure/middleware/logging_middleware.py` | N+1 reset + security probe call |
| Create | `app/tests/unit/test_monitoring/test_service_probe.py` | Unit tests for decorators |
| Create | `app/tests/unit/test_monitoring/test_security_probe.py` | Unit tests for brute force |
| Create | `app/tests/unit/test_monitoring/test_db_probe.py` | Unit tests for SQL fingerprint, pg code mapping |

---

## Task 1: DB Probe

**Files:**
- Create: `app/infrastructure/monitoring/db_probe.py`
- Create: `app/tests/unit/test_monitoring/test_db_probe.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_db_probe.py
import pytest
from app.infrastructure.monitoring.db_probe import _sql_fingerprint, _PG_CODE_MAP, _CRITICAL_PG_CODES


def test_sql_fingerprint_normalizes_literals():
    s1 = _sql_fingerprint("SELECT * FROM users WHERE id = 42 AND name = 'alice'")
    s2 = _sql_fingerprint("SELECT * FROM users WHERE id = 99 AND name = 'bob'")
    assert s1 == s2


def test_sql_fingerprint_differs_by_table():
    s1 = _sql_fingerprint("SELECT * FROM users WHERE id = 1")
    s2 = _sql_fingerprint("SELECT * FROM orders WHERE id = 1")
    assert s1 != s2


def test_pg_code_deadlock_is_critical():
    assert "40P01" in _CRITICAL_PG_CODES
    assert _PG_CODE_MAP["40P01"] == "deadlock"


def test_pg_code_unique_violation():
    assert _PG_CODE_MAP["23505"] == "unique_violation"


def test_pg_code_unknown_returns_db_error():
    assert _PG_CODE_MAP.get("99999", "db_error") == "db_error"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_db_probe.py -x -q
```
Expected: `ImportError`

- [ ] **Step 3: Implement db_probe.py**

```python
# app/infrastructure/monitoring/db_probe.py
from __future__ import annotations

import re
import time
from contextvars import ContextVar
from hashlib import blake2b

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import ExceptionContext
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

# ── SQL fingerprinting ────────────────────────────────────────────────────────

_NUM_RE = re.compile(r"\b\d+\b")
_STR_RE = re.compile(r"'[^']*'")
_IN_RE  = re.compile(r"IN\s*\([^)]+\)", re.I)


def _sql_fingerprint(stmt: str) -> str:
    try:
        import sqlparse
        normalized = sqlparse.format(stmt, strip_whitespace=True, keyword_case="upper")
    except Exception:
        normalized = stmt.upper()
    normalized = _IN_RE.sub("IN (?)", normalized)
    normalized = _NUM_RE.sub("?", normalized)
    normalized = _STR_RE.sub("?", normalized)
    return blake2b(normalized.encode(), digest_size=6).hexdigest()


# ── PostgreSQL error code map ─────────────────────────────────────────────────

_PG_CODE_MAP: dict[str, str] = {
    "40001": "deadlock", "40P01": "deadlock",
    "23505": "unique_violation", "23503": "fk_violation",
    "23502": "not_null_violation", "23514": "check_violation",
    "23000": "integrity_error",
    "53300": "too_many_connections", "53200": "out_of_memory",
    "57P03": "db_unavailable", "08006": "connection_failure",
    "55P03": "lock_not_available", "57014": "query_cancelled",
    "42P01": "undefined_table", "42703": "undefined_column",
}
_CRITICAL_PG_CODES = frozenset({"53300", "57P03", "40P01", "08006"})

# ── Per-request N+1 counter ───────────────────────────────────────────────────

_request_query_count: ContextVar[int] = ContextVar("request_query_count", default=0)
_N_PLUS_ONE_THRESHOLD = 20


def reset_query_counter() -> None:
    _request_query_count.set(0)


def get_query_count() -> int:
    return _request_query_count.get(0)


# ── Probe setup ───────────────────────────────────────────────────────────────

def setup_db_probe(engine: AsyncEngine) -> None:
    """Register all SQLAlchemy event listeners. Call once at startup."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, params, context, executemany):
        context._query_start = time.monotonic()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, params, context, executemany):
        start = getattr(context, "_query_start", None)
        if start is None:
            return
        elapsed_ms = (time.monotonic() - start) * 1000

        # Increment N+1 counter
        count = _request_query_count.get(0) + 1
        _request_query_count.set(count)
        if count == _N_PLUS_ONE_THRESHOLD:
            from app.infrastructure.monitoring import emit
            emit(ErrorEvent(
                layer=ErrorLayer.DB, category="n_plus_one_suspect",
                severity=ErrorSeverity.WARNING,
                message=f"N+1 suspect: {count} queries in single request",
                metadata={"query_count": count,
                          "statement_fp": _sql_fingerprint(statement)},
            ))

        # Slow query
        if elapsed_ms < 500:
            return
        severity = ErrorSeverity.ERROR if elapsed_ms > 2000 else ErrorSeverity.WARNING
        fp = _sql_fingerprint(statement)
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.DB, category="slow_query",
            severity=severity,
            message=f"Slow query: {elapsed_ms:.0f}ms",
            metadata={"query_ms": round(elapsed_ms, 1), "statement_fp": fp},
        ))

        # Auto EXPLAIN for very slow queries (>2s) — fire-and-forget
        if elapsed_ms > 2000:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    _auto_explain(statement, params, elapsed_ms),
                    name="auto-explain",
                )
            except RuntimeError:
                pass  # No loop available

    @event.listens_for(sync_engine, "handle_error")
    def _on_error(ctx: ExceptionContext):
        orig = ctx.original_exception
        pg_code = getattr(orig, "pgcode", None)
        category = _PG_CODE_MAP.get(pg_code or "", "db_error")
        severity = ErrorSeverity.CRITICAL if pg_code in _CRITICAL_PG_CODES else ErrorSeverity.ERROR
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.DB, category=category,
            severity=severity,
            message=f"{type(orig).__name__}: {str(orig)[:300]}",
            metadata={"pg_code": pg_code, "exception_type": type(orig).__name__},
        ))

    @event.listens_for(sync_engine, "checkout")
    def _on_checkout(dbapi_conn, conn_record, conn_proxy):
        pool = sync_engine.pool
        try:
            checked_out = pool.checkedout()
            size = pool.size()
            if size > 0 and checked_out / size > 0.85:
                from app.infrastructure.monitoring import emit
                emit(ErrorEvent(
                    layer=ErrorLayer.DB, category="pool_pressure",
                    severity=ErrorSeverity.ERROR,
                    message=f"Connection pool {checked_out}/{size} ({100*checked_out//size}% used)",
                    metadata={"checked_out": checked_out, "pool_size": size,
                              "overflow": pool.overflow()},
                ))
        except Exception:
            pass

    logger.info("DB probe activated")


async def _auto_explain(statement: str, params, elapsed_ms: float) -> None:
    """Run EXPLAIN ANALYZE on slow queries to capture query plan."""
    try:
        from app.database.connection import AsyncSessionLocal
        from sqlalchemy import text

        # Only EXPLAIN SELECT statements (safe)
        clean = statement.strip().upper()
        if not clean.startswith("SELECT"):
            return

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(f"EXPLAIN (ANALYZE FALSE, FORMAT TEXT) {statement}"),
            )
            plan_lines = [row[0] for row in result.fetchall()]
            plan_text = "\n".join(plan_lines[:20])  # first 20 lines

            # Check for Sequential Scan on large table
            seq_scan = any("Seq Scan" in line for line in plan_lines)
            from app.infrastructure.monitoring import aemit
            await aemit(ErrorEvent(
                layer=ErrorLayer.DB, category="slow_query_plan",
                severity=ErrorSeverity.WARNING,
                message=f"EXPLAIN for {elapsed_ms:.0f}ms query",
                metadata={
                    "query_ms": round(elapsed_ms, 1),
                    "has_seq_scan": seq_scan,
                    "plan_excerpt": plan_text[:500],
                    "statement_fp": _sql_fingerprint(statement),
                },
            ))
    except Exception as exc:
        logger.debug("Auto EXPLAIN failed: %s", exc)
```

- [ ] **Step 4: Add pg_stat Celery tasks in error_digest.py**

Add to `app/workers/tasks/error_digest.py`:

```python
@celery_app.task(
    bind=True,
    name="monitoring.db_health_check",
    max_retries=0,
    ignore_result=True,
)
def db_health_check(self):
    """Detect long-running transactions, lock waits, and table bloat."""
    asyncio.run(_db_health_check())


async def _db_health_check() -> None:
    from app.database.connection import AsyncSessionLocal
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity
    from sqlalchemy import text

    async with AsyncSessionLocal() as session:
        # Long-running transactions (>30s)
        rows = await session.execute(text("""
            SELECT pid,
                   EXTRACT(EPOCH FROM (now() - xact_start))::int AS duration_sec,
                   LEFT(query, 200) AS query_excerpt,
                   state
            FROM pg_stat_activity
            WHERE xact_start IS NOT NULL
              AND now() - xact_start > interval '30 seconds'
              AND state != 'idle'
              AND pid != pg_backend_pid()
        """))
        for row in rows:
            sev = ErrorSeverity.CRITICAL if row.duration_sec > 120 else ErrorSeverity.ERROR
            await aemit(ErrorEvent(
                layer=ErrorLayer.DB, category="long_running_tx",
                severity=sev,
                message=f"Long TX: {row.duration_sec}s — {row.query_excerpt}",
                metadata={"pid": row.pid, "duration_sec": row.duration_sec,
                          "state": row.state},
            ))

        # Lock wait chains
        rows = await session.execute(text("""
            SELECT blocked.pid AS blocked_pid,
                   blocking.pid AS blocking_pid,
                   LEFT(blocked.query, 200) AS blocked_query,
                   EXTRACT(EPOCH FROM (now() - blocked.query_start))::int AS wait_sec
            FROM pg_stat_activity blocked
            JOIN pg_stat_activity blocking
              ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
            WHERE blocked.wait_event_type = 'Lock'
        """))
        for row in rows:
            sev = ErrorSeverity.CRITICAL if row.wait_sec > 15 else ErrorSeverity.ERROR
            await aemit(ErrorEvent(
                layer=ErrorLayer.DB, category="lock_wait",
                severity=sev,
                message=f"Lock wait {row.wait_sec}s: pid {row.blocked_pid} blocked by {row.blocking_pid}",
                metadata={"blocked_pid": row.blocked_pid,
                          "blocking_pid": row.blocking_pid,
                          "wait_sec": row.wait_sec,
                          "query": row.blocked_query},
            ))

        # Table bloat (dead tuple ratio >20%)
        rows = await session.execute(text("""
            SELECT relname,
                   n_dead_tup,
                   n_live_tup,
                   ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 1)
                       AS dead_pct
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 5000
              AND n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) > 0.20
            ORDER BY dead_pct DESC
            LIMIT 10
        """))
        for row in rows:
            await aemit(ErrorEvent(
                layer=ErrorLayer.DB, category="table_bloat",
                severity=ErrorSeverity.WARNING,
                message=f"Table '{row.relname}' bloat: {row.dead_pct}% dead tuples ({row.n_dead_tup:,})",
                metadata={"table": row.relname, "dead_pct": float(row.dead_pct),
                          "dead_tuples": row.n_dead_tup},
            ))
```

Also add to `beat_schedule` in `celery_app.py`:
```python
"monitoring-db-health-check-every-5m": {
    "task": "monitoring.db_health_check",
    "schedule": 300.0,
},
```

- [ ] **Step 5: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_db_probe.py -x -q
```
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/monitoring/db_probe.py app/tests/unit/test_monitoring/test_db_probe.py app/workers/tasks/error_digest.py app/infrastructure/background/celery_app.py
git commit -m "feat(monitoring): add DB probe — slow query, EXPLAIN, N+1, pool pressure, pg_stat health checks"
```

---

## Task 2: Celery Probe

**Files:**
- Create: `app/infrastructure/monitoring/celery_probe.py`

- [ ] **Step 1: Write failing test**

```python
# app/tests/unit/test_monitoring/test_celery_probe.py
import pytest
from unittest.mock import MagicMock, patch
from app.infrastructure.monitoring.celery_probe import _record_heartbeat_key


def test_heartbeat_key_format():
    key = _record_heartbeat_key("my.task.name")
    assert key == "beat:last_run:my.task.name"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_celery_probe.py -x -q
```

- [ ] **Step 3: Implement celery_probe.py**

```python
# app/infrastructure/monitoring/celery_probe.py
from __future__ import annotations

import resource
import time
from collections import defaultdict, deque

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

_task_start_times: dict[str, float] = {}
_SLOW_TASK_WARN_MS = 30_000   # 30s
_SLOW_TASK_ERROR_MS = 120_000 # 2min
_MEMORY_ERROR_MB = 800

# Beat watchdog: maps task name → max allowed silence in seconds
BEAT_EXPECTED_TASKS: dict[str, int] = {
    "infrastructure.relay_outbox_events": 120,
    "monitoring.error_digest": 600,
    "monitoring.db_health_check": 600,
    "prediction.drain_dlq": 180,
}


def _record_heartbeat_key(task_name: str) -> str:
    return f"beat:last_run:{task_name}"


def setup_celery_probe() -> None:
    """Connect Celery signals. Call once at startup."""
    from celery.signals import (
        task_failure, task_postrun, task_prerun, task_retry, task_revoked,
    )

    @task_prerun.connect
    def on_prerun(task_id: str, task, **_):
        _task_start_times[task_id] = time.monotonic()

    @task_postrun.connect
    def on_postrun(task_id: str, task, state: str, **_):
        start = _task_start_times.pop(task_id, None)
        if start is not None:
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms > _SLOW_TASK_WARN_MS:
                sev = ErrorSeverity.ERROR if elapsed_ms > _SLOW_TASK_ERROR_MS else ErrorSeverity.WARNING
                from app.infrastructure.monitoring import emit
                emit(ErrorEvent(
                    layer=ErrorLayer.CELERY, category="slow_task",
                    severity=sev,
                    message=f"Task {task.name} took {elapsed_ms/1000:.1f}s",
                    metadata={"task": task.name, "duration_ms": round(elapsed_ms),
                              "state": state},
                ))

        # Record heartbeat
        _write_heartbeat_sync(task.name)

        # Memory leak check
        try:
            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if mem_mb > _MEMORY_ERROR_MB:
                from app.infrastructure.monitoring import emit
                emit(ErrorEvent(
                    layer=ErrorLayer.CELERY, category="worker_memory_pressure",
                    severity=ErrorSeverity.ERROR,
                    message=f"Worker RSS {mem_mb:.0f}MB after task {task.name}",
                    metadata={"rss_mb": round(mem_mb), "task": task.name},
                ))
        except Exception:
            pass

    @task_failure.connect
    def on_failure(task_id: str, exception, traceback, sender, **_):
        _task_start_times.pop(task_id, None)
        is_final = sender.request.retries >= (sender.max_retries or 0)
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.CELERY,
            category="task_failure_final" if is_final else "task_failure",
            severity=ErrorSeverity.CRITICAL if is_final else ErrorSeverity.ERROR,
            message=f"{sender.name}: {type(exception).__name__}: {str(exception)[:200]}",
            metadata={
                "task": sender.name,
                "retries": sender.request.retries,
                "max_retries": sender.max_retries,
                "exception_type": type(exception).__name__,
                "is_final_failure": is_final,
            },
        ))

    @task_retry.connect
    def on_retry(request, reason, einfo, **_):
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.CELERY, category="task_retry",
            severity=ErrorSeverity.WARNING,
            message=f"{request.task}: retry #{request.retries} — {str(reason)[:200]}",
            metadata={"task": request.task, "retry_count": request.retries,
                      "reason": str(reason)[:200]},
        ))

    @task_revoked.connect
    def on_revoked(request, terminated, signum, expired, **_):
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.CELERY, category="task_revoked",
            severity=ErrorSeverity.WARNING,
            message=f"Task {request.task} revoked (terminated={terminated}, expired={expired})",
            metadata={"task": request.task, "terminated": terminated,
                      "signum": signum, "expired": expired},
        ))

    logger.info("Celery probe activated")


def _write_heartbeat_sync(task_name: str) -> None:
    """Write heartbeat timestamp to Redis synchronously (best-effort)."""
    try:
        import asyncio
        key = _record_heartbeat_key(task_name)
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(_write_heartbeat_async(key))
            )
        except RuntimeError:
            # Celery worker context — use asyncio.run
            asyncio.run(_write_heartbeat_async(key))
    except Exception as exc:
        logger.debug("Heartbeat write failed for %s: %s", task_name, exc)


async def _write_heartbeat_async(key: str) -> None:
    from app.infrastructure.cache.redis_pubsub import set_redis_val
    await set_redis_val(key, time.time(), expire=7200)


async def check_beat_health() -> None:
    """Check all expected beat tasks fired within their window. Called by Celery task."""
    from app.infrastructure.cache.redis_pubsub import get_redis_val
    from app.infrastructure.monitoring import aemit

    for task_name, max_silence_sec in BEAT_EXPECTED_TASKS.items():
        last_val = await get_redis_val(_record_heartbeat_key(task_name))
        last_run = float(last_val) if last_val else None
        if last_run is None or (time.time() - last_run) > max_silence_sec:
            elapsed = round(time.time() - last_run) if last_run else None
            await aemit(ErrorEvent(
                layer=ErrorLayer.CELERY, category="beat_missed",
                severity=ErrorSeverity.CRITICAL,
                message=(
                    f"Beat task '{task_name}' not seen for "
                    f"{elapsed or '?'}s (max {max_silence_sec}s)"
                ),
                metadata={"task": task_name, "max_silence_sec": max_silence_sec,
                          "last_run_ago_sec": elapsed},
            ))
```

Add `check_beat_health()` call to `error_digest` task in `error_digest.py`:

```python
# At the end of _run_digest():
from app.infrastructure.monitoring.celery_probe import check_beat_health
await check_beat_health()
```

Also add queue depth check in `error_digest.py`:

```python
async def _check_queue_depth() -> None:
    """Emit warning if Celery queue backlog grows large."""
    try:
        from app.infrastructure.background.celery_app import celery_app
        from app.infrastructure.monitoring import aemit

        inspect = celery_app.control.inspect(timeout=2.0)
        import asyncio
        reserved = await asyncio.to_thread(inspect.reserved)
        if not reserved:
            return
        total = sum(len(v) for v in reserved.values())
        if total > 100:
            sev = ErrorSeverity.ERROR if total > 500 else ErrorSeverity.WARNING
            await aemit(ErrorEvent(
                layer=ErrorLayer.CELERY, category="queue_backlog",
                severity=sev,
                message=f"Celery queue depth: {total} pending tasks",
                metadata={"queued_tasks": total},
            ))
    except Exception as exc:
        logger.debug("Queue depth check failed: %s", exc)
```

Call `await _check_queue_depth()` inside `_run_digest()`.

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_celery_probe.py -x -q
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/monitoring/celery_probe.py app/tests/unit/test_monitoring/test_celery_probe.py app/workers/tasks/error_digest.py
git commit -m "feat(monitoring): add Celery probe — task failure/retry, beat watchdog, queue depth, memory"
```

---

## Task 3: Service Probe

**Files:**
- Create: `app/infrastructure/monitoring/service_probe.py`
- Create: `app/tests/unit/test_monitoring/test_service_probe.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_service_probe.py
import pytest
from unittest.mock import AsyncMock, patch
from app.infrastructure.monitoring.service_probe import (
    monitor_errors, intentional_fallback, assert_invariant,
)
from app.infrastructure.monitoring.models import ErrorSeverity


@pytest.mark.unit
async def test_monitor_errors_reraises_by_default():
    @monitor_errors(category="test_error")
    async def failing_fn():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await failing_fn()


@pytest.mark.unit
async def test_monitor_errors_emits_event_on_exception():
    events = []

    @monitor_errors(category="test_error")
    async def failing_fn():
        raise RuntimeError("test failure")

    with patch("app.infrastructure.monitoring.service_probe.aemit",
               new_callable=AsyncMock) as mock_emit:
        with pytest.raises(RuntimeError):
            await failing_fn()
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.category == "test_error"


@pytest.mark.unit
async def test_monitor_errors_skips_domain_errors():
    from app.core.exceptions import DomainError

    @monitor_errors(category="test_error")
    async def domain_fn():
        raise DomainError("domain issue")

    with patch("app.infrastructure.monitoring.service_probe.aemit",
               new_callable=AsyncMock) as mock_emit:
        with pytest.raises(DomainError):
            await domain_fn()
        mock_emit.assert_not_called()  # DomainError already handled by main.py


@pytest.mark.unit
async def test_intentional_fallback_returns_none_on_error():
    @intentional_fallback("test fallback reason")
    async def fallback_fn():
        raise ConnectionError("external down")

    result = await fallback_fn()
    assert result is None


@pytest.mark.unit
def test_assert_invariant_emits_on_violation():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        assert_invariant(False, "negative fuel detected")
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.category == "invariant_violation"


@pytest.mark.unit
def test_assert_invariant_no_emit_when_true():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        assert_invariant(True, "should not emit")
        mock_emit.assert_not_called()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_service_probe.py -x -q
```

- [ ] **Step 3: Implement service_probe.py**

```python
# app/infrastructure/monitoring/service_probe.py
from __future__ import annotations

import asyncio
import functools
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable)

# Call chain tracking: list of qualified names built up as decorated fns call each other
_call_chain: ContextVar[list[str]] = ContextVar("service_call_chain", default=[])


def monitor_errors(
    category: str = "service_error",
    severity: str = "error",
    reraise: bool = True,
    capture_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator for service methods. Emits ErrorEvent on any non-DomainError exception.
    DomainError is intentionally skipped — main.py exception handlers cover it.

    Args:
        category: ErrorEvent category string.
        severity: ErrorSeverity value.
        reraise: Re-raise after emitting (True = not a swallow).
        capture_result: Also emit WARNING if function returns None.
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Update call chain context
            chain = _call_chain.get([]).copy()
            chain.append(fn.__qualname__)
            token = _call_chain.set(chain)
            try:
                result = await fn(*args, **kwargs)
                if capture_result and result is None:
                    from app.infrastructure.monitoring import aemit
                    await aemit(ErrorEvent(
                        layer=ErrorLayer.SERVICE,
                        category=f"{category}:null_result",
                        severity=ErrorSeverity.WARNING,
                        message=f"{fn.__qualname__} returned None unexpectedly",
                        metadata={"fn": fn.__qualname__, "call_chain": chain},
                    ))
                return result
            except Exception as exc:
                from app.core.exceptions import DomainError
                if isinstance(exc, DomainError):
                    raise  # Already handled by FastAPI exception handlers
                from app.infrastructure.monitoring import aemit
                import traceback as _tb
                await aemit(ErrorEvent(
                    layer=ErrorLayer.SERVICE,
                    category=category,
                    severity=ErrorSeverity(severity),
                    message=f"{fn.__qualname__}: {type(exc).__name__}: {str(exc)[:300]}",
                    stack_trace=_tb.format_exc()[:2000],
                    metadata={
                        "fn": fn.__qualname__,
                        "exception_type": type(exc).__name__,
                        "call_chain": chain,
                    },
                ))
                if reraise:
                    raise
                return None
            finally:
                _call_chain.reset(token)
        return wrapper  # type: ignore[return-value]
    return decorator


def intentional_fallback(reason: str) -> Callable[[F], F]:
    """
    Marks a function as having an intentional silent fallback.
    Emits WARNING (not ERROR) — distinguishes bugs from handled degradation.

    Usage:
        @intentional_fallback("ORS API down — use cached route")
        async def get_route(...): ...
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                from app.infrastructure.monitoring import aemit
                await aemit(ErrorEvent(
                    layer=ErrorLayer.SERVICE,
                    category="intentional_fallback",
                    severity=ErrorSeverity.WARNING,
                    message=f"[INTENTIONAL] {fn.__qualname__}: {reason} — {type(exc).__name__}: {str(exc)[:200]}",
                    metadata={
                        "fn": fn.__qualname__,
                        "reason": reason,
                        "exception_type": type(exc).__name__,
                    },
                ))
                return None
        return wrapper  # type: ignore[return-value]
    return decorator


def assert_invariant(
    condition: bool,
    message: str,
    severity: str = "error",
    metadata: dict | None = None,
) -> None:
    """
    Emit ErrorEvent if a business invariant is violated.
    Does NOT raise — use when wrong value is detected but processing can continue.

    Usage:
        assert_invariant(fuel_amount >= 0, f"Negative fuel: {fuel_amount=}")
        assert_invariant(distance_km < 10_000, f"Unrealistic distance: {distance_km}")
    """
    if condition:
        return
    from app.infrastructure.monitoring import emit
    emit(ErrorEvent(
        layer=ErrorLayer.SERVICE,
        category="invariant_violation",
        severity=ErrorSeverity(severity),
        message=message,
        metadata=metadata or {},
    ))


def setup_asyncio_exception_handler() -> None:
    """Capture unhandled asyncio coroutine exceptions (dangling tasks)."""
    import asyncio

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        msg = context.get("message", "")
        exc = context.get("exception")
        future = context.get("future")
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.SERVICE,
            category="async_context_leak",
            severity=ErrorSeverity.ERROR,
            message=f"Asyncio unhandled: {msg}",
            metadata={
                "exception": str(exc) if exc else None,
                "exception_type": type(exc).__name__ if exc else None,
                "source": str(future)[:200] if future else None,
            },
        ))
        # Still log it
        logger.error("Asyncio unhandled exception: %s", msg, exc_info=exc)

    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(_handler)
        logger.info("Asyncio exception handler probe activated")
    except RuntimeError:
        pass  # No event loop yet — will be set later
```

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_service_probe.py -x -q
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/monitoring/service_probe.py app/tests/unit/test_monitoring/test_service_probe.py
git commit -m "feat(monitoring): add service probe — @monitor_errors, @intentional_fallback, assert_invariant, call chain, async leak handler"
```

---

## Task 4: External API Probe

**Files:**
- Create: `app/infrastructure/monitoring/external_api_probe.py`

- [ ] **Step 1: Implement external_api_probe.py**

```python
# app/infrastructure/monitoring/external_api_probe.py
from __future__ import annotations

import time
from typing import Callable

import httpx

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

# ms thresholds per service
_THRESHOLDS: dict[str, float] = {
    "ors": 3000,
    "groq": 10000,
    "telegram": 2000,
    "mapbox": 5000,
}
_DEFAULT_THRESHOLD = 5000


def _identify_service(url: str) -> str:
    url_lower = url.lower()
    if "openrouteservice" in url_lower or "ors" in url_lower:
        return "ors"
    if "groq" in url_lower:
        return "groq"
    if "telegram" in url_lower:
        return "telegram"
    if "mapbox" in url_lower:
        return "mapbox"
    return "external"


async def _on_request(request: httpx.Request) -> None:
    request.extensions["_probe_start"] = time.monotonic()


async def _on_response(response: httpx.Response) -> None:
    start = response.request.extensions.get("_probe_start")
    elapsed_ms = (time.monotonic() - start) * 1000 if start else None
    service = _identify_service(str(response.url))
    threshold = _THRESHOLDS.get(service, _DEFAULT_THRESHOLD)

    from app.infrastructure.monitoring import aemit

    if response.status_code >= 500:
        await aemit(ErrorEvent(
            layer=ErrorLayer.EXTERNAL,
            category="api_5xx",
            severity=ErrorSeverity.ERROR,
            message=f"{service} HTTP {response.status_code}: {str(response.url)[:200]}",
            metadata={"service": service, "status": response.status_code,
                      "url": str(response.url)[:200]},
        ))
    elif response.status_code == 429:
        await aemit(ErrorEvent(
            layer=ErrorLayer.EXTERNAL,
            category="api_rate_limited",
            severity=ErrorSeverity.WARNING,
            message=f"{service} rate limited (429)",
            metadata={"service": service, "url": str(response.url)[:200]},
        ))

    if elapsed_ms is not None and elapsed_ms > threshold:
        severity = ErrorSeverity.ERROR if elapsed_ms > threshold * 2 else ErrorSeverity.WARNING
        await aemit(ErrorEvent(
            layer=ErrorLayer.EXTERNAL,
            category="api_slow",
            severity=severity,
            message=f"{service} slow: {elapsed_ms:.0f}ms (threshold {threshold}ms)",
            metadata={"service": service, "ms": round(elapsed_ms),
                      "threshold_ms": threshold, "url": str(response.url)[:200]},
        ))


async def _on_error(exc: Exception, request: httpx.Request) -> None:
    service = _identify_service(str(request.url))
    from app.infrastructure.monitoring import aemit
    await aemit(ErrorEvent(
        layer=ErrorLayer.EXTERNAL,
        category="api_unreachable",
        severity=ErrorSeverity.CRITICAL,
        message=f"{service} unreachable: {type(exc).__name__}: {str(exc)[:200]}",
        metadata={"service": service, "url": str(request.url)[:200],
                  "exception_type": type(exc).__name__},
    ))


def get_monitored_client(**kwargs) -> httpx.AsyncClient:
    """
    Return an httpx.AsyncClient with monitoring event_hooks wired.

    Usage (replace existing httpx.AsyncClient() calls):
        async with get_monitored_client(timeout=5.0) as client:
            resp = await client.get(url)
    """
    event_hooks: dict[str, list[Callable]] = kwargs.pop("event_hooks", {})
    event_hooks.setdefault("request", []).insert(0, _on_request)
    event_hooks.setdefault("response", []).insert(0, _on_response)
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
```

Replace httpx usage in `app/infrastructure/notifications/telegram_notifier.py`:

```python
# Change:
#   async with httpx.AsyncClient(timeout=2.0) as client:
# To:
from app.infrastructure.monitoring.external_api_probe import get_monitored_client
#   async with get_monitored_client(timeout=2.0) as client:
```

Do the same for `app/infrastructure/routing/openroute_client.py` (or wherever ORS/Groq httpx calls are made) — search and replace `httpx.AsyncClient(` with `get_monitored_client(`.

- [ ] **Step 2: Find and update httpx clients**

```bash
grep -rn "httpx.AsyncClient(" app/ --include="*.py" -l
```

Update each file found to use `get_monitored_client(...)`.

- [ ] **Step 3: Commit**

```bash
git add app/infrastructure/monitoring/external_api_probe.py
git commit -m "feat(monitoring): add External API probe — httpx event_hooks for ORS/Groq/Telegram"
```

---

## Task 5: Security Probe

**Files:**
- Create: `app/infrastructure/monitoring/security_probe.py`
- Create: `app/tests/unit/test_monitoring/test_security_probe.py`
- Modify: `app/infrastructure/middleware/logging_middleware.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_security_probe.py
import pytest
from unittest.mock import patch
from app.infrastructure.monitoring.security_probe import BruteForceDetector


def test_brute_force_not_triggered_below_threshold():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            detector.record("1.2.3.4", 401)
        mock_emit.assert_not_called()


def test_brute_force_triggered_at_threshold():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            detector.record("1.2.3.4", 401)
        mock_emit.assert_called_once()


def test_brute_force_ignores_non_401():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(20):
            detector.record("1.2.3.4", 200)
        mock_emit.assert_not_called()


def test_brute_force_different_ips_independent():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            detector.record("1.1.1.1", 401)
            detector.record("2.2.2.2", 401)
        mock_emit.assert_not_called()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_security_probe.py -x -q
```

- [ ] **Step 3: Implement security_probe.py**

```python
# app/infrastructure/monitoring/security_probe.py
from __future__ import annotations

import time
from collections import deque, defaultdict
from typing import DefaultDict

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

_BRUTE_FORCE_THRESHOLD = 10  # attempts
_BRUTE_FORCE_WINDOW_SEC = 60
_RBAC_AGGREGATION_WINDOW_SEC = 300  # 5 min
_RBAC_VIOLATION_THRESHOLD = 20      # 20 unique-endpoint 403s from same user


class BruteForceDetector:
    def __init__(self) -> None:
        self._windows: DefaultDict[str, deque[float]] = defaultdict(deque)
        self._alerted: dict[str, float] = {}  # ip → last_alert_time

    def record(self, ip: str, status_code: int) -> None:
        if status_code != 401:
            return
        now = time.monotonic()
        q = self._windows[ip]
        q.append(now)
        # Evict expired entries
        while q and now - q[0] > _BRUTE_FORCE_WINDOW_SEC:
            q.popleft()
        if len(q) >= _BRUTE_FORCE_THRESHOLD:
            last_alert = self._alerted.get(ip, 0.0)
            if now - last_alert > _BRUTE_FORCE_WINDOW_SEC:
                self._alerted[ip] = now
                self._emit_brute_force(ip, len(q))

    def _emit_brute_force(self, ip: str, attempts: int) -> None:
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.SECURITY,
            category="brute_force",
            severity=ErrorSeverity.CRITICAL,
            message=f"Brute force from {ip}: {attempts} attempts in {_BRUTE_FORCE_WINDOW_SEC}s",
            metadata={"ip": ip, "attempts": attempts,
                      "window_sec": _BRUTE_FORCE_WINDOW_SEC},
        ))


class RBACViolationTracker:
    def __init__(self) -> None:
        # user_id → deque of (timestamp, endpoint)
        self._windows: DefaultDict[int, deque[tuple[float, str]]] = defaultdict(deque)
        self._alerted: dict[int, float] = {}

    def record(self, user_id: int, endpoint: str) -> None:
        now = time.monotonic()
        q = self._windows[user_id]
        q.append((now, endpoint))
        while q and now - q[0][0] > _RBAC_AGGREGATION_WINDOW_SEC:
            q.popleft()
        if len(q) >= _RBAC_VIOLATION_THRESHOLD:
            last_alert = self._alerted.get(user_id, 0.0)
            if now - last_alert > _RBAC_AGGREGATION_WINDOW_SEC:
                self._alerted[user_id] = now
                endpoints = list({ep for _, ep in q})[:10]
                from app.infrastructure.monitoring import emit
                emit(ErrorEvent(
                    layer=ErrorLayer.SECURITY,
                    category="rbac_scraping",
                    severity=ErrorSeverity.ERROR,
                    message=f"User {user_id}: {len(q)} 403s in {_RBAC_AGGREGATION_WINDOW_SEC}s",
                    metadata={"user_id": user_id, "attempt_count": len(q),
                              "endpoints_sample": endpoints},
                ))


def emit_jwt_anomaly(exc_type: str, path: str, ip: str) -> None:
    """Call from JWT decode exception handlers."""
    severity_map = {
        "ExpiredSignatureError": ErrorSeverity.WARNING,   # normal expiry
        "ImmatureSignatureError": ErrorSeverity.ERROR,    # clock skew / attack
        "DecodeError": ErrorSeverity.ERROR,               # token manipulation
        "InvalidSignatureError": ErrorSeverity.ERROR,
        "InvalidAlgorithmError": ErrorSeverity.CRITICAL,
    }
    severity = severity_map.get(exc_type, ErrorSeverity.WARNING)
    from app.infrastructure.monitoring import emit
    emit(ErrorEvent(
        layer=ErrorLayer.SECURITY,
        category="jwt_anomaly",
        severity=severity,
        message=f"JWT {exc_type} from {ip} at {path}",
        metadata={"exc_type": exc_type, "ip": ip, "path": path},
    ))


# Module-level singletons
_brute_force = BruteForceDetector()
_rbac_tracker = RBACViolationTracker()


def get_brute_force_detector() -> BruteForceDetector:
    return _brute_force


def get_rbac_tracker() -> RBACViolationTracker:
    return _rbac_tracker
```

- [ ] **Step 4: Integrate into logging_middleware.py**

In `app/infrastructure/middleware/logging_middleware.py`, in the `dispatch` method after getting the response:

```python
# After: response = await call_next(request)

# Security probe
from app.infrastructure.monitoring.security_probe import (
    get_brute_force_detector, get_rbac_tracker,
)
client_ip = request.client.host if request.client else "unknown"
get_brute_force_detector().record(client_ip, response.status_code)
if response.status_code == 403:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        get_rbac_tracker().record(user_id, request.url.path)

# N+1 counter reset (for DB probe)
from app.infrastructure.monitoring.db_probe import reset_query_counter
reset_query_counter()
```

And call `reset_query_counter()` at the top of `dispatch` too (before `call_next`).

- [ ] **Step 5: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_security_probe.py -x -q
```
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/monitoring/security_probe.py app/tests/unit/test_monitoring/test_security_probe.py app/infrastructure/middleware/logging_middleware.py
git commit -m "feat(monitoring): add security probe — brute force detector, RBAC violation tracker, JWT anomaly"
```

---

## Task 6: ML Probe

**Files:**
- Create: `app/infrastructure/monitoring/ml_probe.py`

- [ ] **Step 1: Implement ml_probe.py**

```python
# app/infrastructure/monitoring/ml_probe.py
from __future__ import annotations

from collections import Counter

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

_FALLBACK_RATE_THRESHOLD = 0.80   # 80% fallback → model broken
_CHECK_EVERY_N_PREDICTIONS = 100


class MLProbe:
    """Tracks physics fallback rate per model. Emits alert if rate > 80%."""

    def __init__(self) -> None:
        self._total: Counter[str] = Counter()
        self._fallback: Counter[str] = Counter()

    def record_prediction(self, model_id: str, used_fallback: bool) -> None:
        self._total[model_id] += 1
        if used_fallback:
            self._fallback[model_id] += 1

        total = self._total[model_id]
        if total % _CHECK_EVERY_N_PREDICTIONS == 0:
            rate = self._fallback[model_id] / total
            if rate > _FALLBACK_RATE_THRESHOLD:
                from app.infrastructure.monitoring import emit
                emit(ErrorEvent(
                    layer=ErrorLayer.ML,
                    category="high_fallback_rate",
                    severity=ErrorSeverity.ERROR,
                    message=(
                        f"Model '{model_id}' fallback rate {rate:.0%} "
                        f"({self._fallback[model_id]}/{total} predictions)"
                    ),
                    metadata={
                        "model_id": model_id,
                        "fallback_rate": round(rate, 3),
                        "fallback_count": self._fallback[model_id],
                        "total_predictions": total,
                    },
                ))

    def record_model_load_failure(self, model_id: str, exc: Exception) -> None:
        from app.infrastructure.monitoring import emit
        emit(ErrorEvent(
            layer=ErrorLayer.ML,
            category="model_load_failure",
            severity=ErrorSeverity.CRITICAL,
            message=f"Model '{model_id}' failed to load: {type(exc).__name__}: {exc}",
            metadata={"model_id": model_id, "exception_type": type(exc).__name__},
        ))

    def get_stats(self, model_id: str) -> dict:
        total = self._total[model_id]
        fallback = self._fallback[model_id]
        return {
            "model_id": model_id,
            "total_predictions": total,
            "fallback_count": fallback,
            "fallback_rate": round(fallback / total, 3) if total else 0.0,
        }


_ml_probe: MLProbe | None = None


def get_ml_probe() -> MLProbe:
    global _ml_probe
    if _ml_probe is None:
        _ml_probe = MLProbe()
    return _ml_probe
```

Wire into `app/core/ml/ensemble_predictor.py` — in the predict method, after physics fallback decision:

```python
from app.infrastructure.monitoring.ml_probe import get_ml_probe
# After deciding whether fallback was used:
get_ml_probe().record_prediction(model_id=self._model_id, used_fallback=used_physics_fallback)
```

And in model load failure:

```python
except Exception as exc:
    from app.infrastructure.monitoring.ml_probe import get_ml_probe
    get_ml_probe().record_model_load_failure(model_id=self._model_id, exc=exc)
    raise
```

- [ ] **Step 2: Commit**

```bash
git add app/infrastructure/monitoring/ml_probe.py
git commit -m "feat(monitoring): add ML probe — fallback rate tracker, model load failure detection"
```

---

## Task 7: activate_all_probes + Full Integration

**Files:**
- Create: `app/infrastructure/monitoring/activate.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create activate.py**

```python
# app/infrastructure/monitoring/activate.py
"""Single entry point to activate all monitoring probes at startup."""
from __future__ import annotations

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def activate_all_probes(engine, celery_app=None) -> None:
    """
    Wire all probes to their respective systems.
    Call once from lifespan BEFORE accepting requests.

    Args:
        engine: The SQLAlchemy AsyncEngine instance.
        celery_app: The Celery application (optional — omit in test/dev without workers).
    """
    # 1. DB probe — SQLAlchemy event listeners
    from app.infrastructure.monitoring.db_probe import setup_db_probe
    setup_db_probe(engine)

    # 2. Celery probe — signals
    if celery_app is not None:
        from app.infrastructure.monitoring.celery_probe import setup_celery_probe
        setup_celery_probe()

    # 3. Service probe — asyncio exception handler
    from app.infrastructure.monitoring.service_probe import setup_asyncio_exception_handler
    setup_asyncio_exception_handler()

    logger.info(
        "All monitoring probes activated: db=%s celery=%s service=asyncio",
        True, celery_app is not None,
    )
```

- [ ] **Step 2: Update lifespan in main.py**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LojiNext (%s)", settings.ENVIRONMENT)
    from app.infrastructure.resilience.shutdown import register_shutdown_handlers
    register_shutdown_handlers()

    # Start error event bus
    from app.infrastructure.monitoring.event_bus import get_event_bus
    bus = get_event_bus()
    bus.start()

    # Activate all monitoring probes
    from app.infrastructure.monitoring.activate import activate_all_probes
    from app.infrastructure.background.celery_app import celery_app as _celery
    activate_all_probes(engine, _celery)

    try:
        yield
    finally:
        bus.stop()
        from app.core.container import get_container
        get_container().shutdown()
        await engine.dispose()
        logger.info("Shutdown complete")
```

- [ ] **Step 3: Smoke test — start server and verify no errors**

```bash
uvicorn app.main:app --reload --port 8000
```
Expected: `All monitoring probes activated: db=True celery=True service=asyncio` in logs.

- [ ] **Step 4: Run full test suite**

```bash
pytest app/tests/unit/test_monitoring/ -q
```
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/monitoring/activate.py app/main.py
git commit -m "feat(monitoring): wire all backend probes via activate_all_probes in lifespan"
```

---

## Self-Review Checklist

- [x] DB probe: slow query (>500ms warning, >2s error), EXPLAIN (>2s SELECT), N+1 (20+ queries/request), pool pressure (>85%), pg_code mapping, pg_stat tasks (long TX, lock wait, bloat) ✓
- [x] Celery probe: failure/retry/revoked signals, beat watchdog (all expected tasks), queue depth, worker memory ✓
- [x] Service probe: @monitor_errors (DomainError excluded), @intentional_fallback, assert_invariant, call chain ContextVar, asyncio exception handler ✓
- [x] External API probe: httpx event_hooks, response 5xx/429, slow response, unreachable ✓
- [x] Security probe: BruteForceDetector (10 × 401 / 60s), RBAC tracker (20 × 403 / 5min), JWT anomaly severity map ✓
- [x] ML probe: fallback rate >80% per 100 predictions, model load failure ✓
- [x] activate_all_probes wired to lifespan ✓
- [x] N+1 counter reset in middleware ✓
- [x] No TBD/TODO placeholders ✓
