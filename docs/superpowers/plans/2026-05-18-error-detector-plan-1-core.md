# Error Detector — Plan 1: Core Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the central ErrorEventBus, PostgreSQL schema, Redis pipeline, alarm router with Z-score anomaly detection, and the Celery digest task — the foundation all probes depend on.

**Architecture:** ErrorEvent dataclass → ErrorEventBus (async queue + Redis dedup + PostgreSQL upsert) → AlarmRouter (severity matrix + Z-score) → Celery beat digest every 5 minutes. Circuit breaker protects against PostgreSQL write failures.

**Tech Stack:** SQLAlchemy 2 async, asyncpg, redis.asyncio (via existing RedisPubSubManager), Celery, Blake2b fingerprinting, statistics stdlib, FastAPI SSE (Plan 4).

**Depends on:** Nothing — this is the foundation.
**Required by:** Plans 2, 3, 4.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `app/infrastructure/monitoring/__init__.py` | Package + `emit` re-export |
| Create | `app/infrastructure/monitoring/models.py` | ErrorEvent dataclass + Enums |
| Create | `app/infrastructure/monitoring/event_bus.py` | ErrorEventBus (queue, Redis, PG, circuit breaker) |
| Create | `app/infrastructure/monitoring/alarm_router.py` | Severity routing + Z-score AnomalyDetector |
| Create | `app/workers/tasks/error_digest.py` | Celery beat: digest + beat watchdog + mat. view refresh |
| Create | `alembic/versions/xxxx_add_error_monitoring.py` | error_events + error_occurrences + mat. view |
| Modify | `app/infrastructure/background/celery_app.py` | Add beat schedules |
| Modify | `app/main.py` | Start EventBus background flusher in lifespan |
| Create | `app/tests/unit/test_monitoring/test_models.py` | Unit: fingerprint, normalization |
| Create | `app/tests/unit/test_monitoring/test_event_bus.py` | Unit: emit, circuit breaker, queue full |
| Create | `app/tests/unit/test_monitoring/test_alarm_router.py` | Unit: severity routing, Z-score |

---

## Task 1: ErrorEvent Dataclass + Fingerprint

**Files:**
- Create: `app/infrastructure/monitoring/models.py`
- Create: `app/infrastructure/monitoring/__init__.py`
- Create: `app/tests/unit/test_monitoring/__init__.py`
- Create: `app/tests/unit/test_monitoring/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_models.py
import pytest
from app.infrastructure.monitoring.models import (
    ErrorEvent, ErrorLayer, ErrorSeverity, make_fingerprint,
)

def test_fingerprint_normalizes_numbers():
    fp1 = make_fingerprint("db", "slow_query", "Query took 150ms on table users")
    fp2 = make_fingerprint("db", "slow_query", "Query took 3200ms on table users")
    assert fp1 == fp2

def test_fingerprint_normalizes_strings():
    fp1 = make_fingerprint("service", "invariant_violation", "user 'alice' not found")
    fp2 = make_fingerprint("service", "invariant_violation", "user 'bob' not found")
    assert fp1 == fp2

def test_fingerprint_differs_by_category():
    fp1 = make_fingerprint("db", "slow_query", "timeout")
    fp2 = make_fingerprint("db", "deadlock", "timeout")
    assert fp1 != fp2

def test_error_event_auto_fingerprint():
    ev = ErrorEvent(layer=ErrorLayer.DB, category="slow_query",
                    severity=ErrorSeverity.WARNING, message="took 200ms")
    assert len(ev.fingerprint) == 16
    assert ev.fingerprint == make_fingerprint("db", "slow_query", "took 200ms")

def test_error_event_to_dict():
    ev = ErrorEvent(layer=ErrorLayer.CELERY, category="task_failure",
                    severity=ErrorSeverity.ERROR, message="boom",
                    trace_id="abc123", metadata={"task": "foo"})
    d = ev.to_dict()
    assert d["layer"] == "celery"
    assert d["severity"] == "error"
    assert d["metadata"]["task"] == "foo"
    assert "fingerprint" in d
    assert "occurred_at" in d
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_models.py -x -q
```
Expected: `ModuleNotFoundError: No module named 'app.infrastructure.monitoring'`

- [ ] **Step 3: Implement models**

```python
# app/infrastructure/monitoring/__init__.py
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity
from app.infrastructure.monitoring.event_bus import get_event_bus

def emit(event: ErrorEvent) -> None:
    """Sync emit — safe to call from SQLAlchemy events, Celery signals, sync code."""
    get_event_bus().emit_sync(event)

async def aemit(event: ErrorEvent) -> None:
    """Async emit — use from async service/endpoint code."""
    await get_event_bus().emit(event)

__all__ = ["ErrorEvent", "ErrorLayer", "ErrorSeverity", "emit", "aemit"]
```

```python
# app/infrastructure/monitoring/models.py
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import blake2b
from typing import Any


class ErrorLayer(str, Enum):
    DB = "db"
    CELERY = "celery"
    API = "api"
    SERVICE = "service"
    FRONTEND = "frontend"
    EXTERNAL = "external"
    SECURITY = "security"
    ML = "ml"


class ErrorSeverity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_NUMBER_RE = re.compile(r"\b\d+\b")
_STRING_RE = re.compile(r"'[^']*'")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def make_fingerprint(layer: str, category: str, message: str) -> str:
    """Blake2b-64bit fingerprint. Normalizes numbers, strings, UUIDs → same hash."""
    normalized = _UUID_RE.sub("UUID", message)
    normalized = _NUMBER_RE.sub("N", normalized)
    normalized = _STRING_RE.sub("'S'", normalized)
    raw = f"{layer}:{category}:{normalized}".encode()
    return blake2b(raw, digest_size=8).hexdigest()


@dataclass
class ErrorEvent:
    layer: ErrorLayer
    category: str
    severity: ErrorSeverity
    message: str
    trace_id: str = ""
    path: str = ""
    stack_trace: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = field(init=False)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.layer, str):
            self.layer = ErrorLayer(self.layer)
        if isinstance(self.severity, str):
            self.severity = ErrorSeverity(self.severity)
        self.fingerprint = make_fingerprint(
            self.layer.value, self.category, self.message
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer.value,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "fingerprint": self.fingerprint,
            "trace_id": self.trace_id,
            "path": self.path,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
            "occurred_at": self.occurred_at.isoformat(),
        }
```

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_models.py -x -q
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/monitoring/ app/tests/unit/test_monitoring/
git commit -m "feat(monitoring): add ErrorEvent dataclass with Blake2b fingerprinting"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `alembic/versions/2026_05_18_add_error_monitoring.py`

- [ ] **Step 1: Generate migration skeleton**

```bash
alembic revision --autogenerate -m "add_error_monitoring"
```

Then replace the generated body with the full migration below.

- [ ] **Step 2: Write migration**

```python
# alembic/versions/2026_05_18_add_error_monitoring.py
"""add error monitoring tables

Revision ID: <generated>
Revises: <previous_head>
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "<generated>"
down_revision = "<previous_head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE error_layer AS ENUM
                ('db','celery','api','service','frontend','external','security','ml');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE error_severity AS ENUM ('critical','error','warning','info');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Aggregated table: one active row per unique fingerprint
    op.create_table(
        "error_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.CHAR(16), nullable=False),
        sa.Column("layer", postgresql.ENUM(name="error_layer", create_type=False), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("severity", postgresql.ENUM(name="error_severity", create_type=False), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("kullanici.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path", sa.String(500), nullable=True),
        sa.Column("stack_trace", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer,
                  sa.ForeignKey("kullanici.id", ondelete="SET NULL"), nullable=True),
    )

    # Partial unique index: only one active (unresolved) row per fingerprint
    op.create_index(
        "idx_error_events_fingerprint_active",
        "error_events", ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_index("idx_error_events_layer_sev",
                    "error_events", ["layer", "severity", "last_seen"])
    op.create_index("idx_error_events_trace_id", "error_events", ["trace_id"],
                    postgresql_where=sa.text("trace_id IS NOT NULL"))

    # Raw time-series log (partitioned by month)
    op.create_table(
        "error_occurrences",
        sa.Column("id", sa.BigInteger, nullable=False),
        sa.Column("fingerprint", sa.CHAR(16), nullable=False),
        sa.Column("layer", postgresql.ENUM(name="error_layer", create_type=False), nullable=False),
        sa.Column("severity", postgresql.ENUM(name="error_severity", create_type=False), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        postgresql_partition_by="RANGE (occurred_at)",
    )
    op.create_index("idx_error_occurrences_time",
                    "error_occurrences", ["occurred_at", "layer"])

    # Create initial monthly partition (current month)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_05
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
    """)

    # Materialized view for dashboard (refreshed by Celery beat every 5 min)
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS error_hourly_stats AS
        SELECT
            date_trunc('hour', occurred_at) AS hour,
            layer,
            severity,
            COUNT(*) AS event_count
        FROM error_occurrences
        WHERE occurred_at > now() - INTERVAL '24 hours'
        GROUP BY 1, 2, 3;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_error_hourly_stats "
        "ON error_hourly_stats(hour, layer, severity);"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS error_hourly_stats;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_05;")
    op.drop_table("error_occurrences")
    op.drop_table("error_events")
    op.execute("DROP TYPE IF EXISTS error_severity;")
    op.execute("DROP TYPE IF EXISTS error_layer;")
```

- [ ] **Step 3: Apply and verify**

```bash
alembic upgrade head
alembic check
```
Expected: `No new upgrade operations detected.`

- [ ] **Step 4: Commit**

```bash
git add alembic/
git commit -m "feat(monitoring): add error_events + error_occurrences schema with partitioning"
```

---

## Task 3: ErrorEventBus

**Files:**
- Create: `app/infrastructure/monitoring/event_bus.py`
- Create: `app/tests/unit/test_monitoring/test_event_bus.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_event_bus.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity
from app.infrastructure.monitoring.event_bus import ErrorEventBus


def make_event(severity=ErrorSeverity.WARNING, category="test"):
    return ErrorEvent(layer=ErrorLayer.DB, category=category,
                      severity=severity, message="test error")


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
    bus._circuit_opened_at = asyncio.get_event_loop().time() - 61
    assert bus._should_attempt_reset() is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_event_bus.py -x -q
```
Expected: `ImportError`

- [ ] **Step 3: Implement ErrorEventBus**

```python
# app/infrastructure/monitoring/event_bus.py
from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from app.infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from app.infrastructure.monitoring.models import ErrorEvent

logger = get_logger(__name__)

_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_RESET_SECONDS = 60
_FLUSH_INTERVAL_SECONDS = 5
_FLUSH_BATCH_SIZE = 200


class ErrorEventBus:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[ErrorEvent] = asyncio.Queue(maxsize=maxsize)
        self._circuit_open = False
        self._failure_count = 0
        self._circuit_opened_at: float = 0.0
        self._flusher_task: asyncio.Task | None = None

    # ── Public interface ──────────────────────────────────────────────────

    async def emit(self, event: ErrorEvent) -> None:
        """Async emit — use from async contexts (service methods, endpoints)."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.error(
                "ErrorEventBus queue full — event dropped: %s/%s",
                event.layer.value, event.category,
            )

    def emit_sync(self, event: ErrorEvent) -> None:
        """Sync emit — safe from SQLAlchemy events, Celery signals, sync callbacks."""
        try:
            loop = asyncio.get_running_loop()
            # We're inside a running event loop (called from sync code within async task)
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        except RuntimeError:
            # No running event loop (worker startup/shutdown) — drop silently
            pass

    def start(self) -> None:
        """Start background flusher. Call once from lifespan."""
        self._flusher_task = asyncio.create_task(self._flush_loop(), name="error-bus-flusher")

    def stop(self) -> None:
        if self._flusher_task and not self._flusher_task.done():
            self._flusher_task.cancel()

    # ── Circuit breaker ───────────────────────────────────────────────────

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

    # ── Flush loop ────────────────────────────────────────────────────────

    async def _flush_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_FLUSH_INTERVAL_SECONDS)
                await self._flush_batch()
            except asyncio.CancelledError:
                # Drain remaining events on shutdown
                await self._flush_batch()
                return
            except Exception as exc:
                logger.error("ErrorEventBus flusher error: %s", exc)

    async def _flush_batch(self) -> None:
        if self._circuit_open and not self._should_attempt_reset():
            await self._flush_to_redis_only()
            return

        batch: list[ErrorEvent] = []
        try:
            while len(batch) < _FLUSH_BATCH_SIZE and not self._queue.empty():
                batch.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass

        if not batch:
            return

        # Write to Redis (dedup counters) then PostgreSQL (upsert)
        await self._write_redis(batch)
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
                # Emit self-referential critical alert
                from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity
                await self.emit(ErrorEvent(
                    layer=ErrorLayer.DB, category="event_bus_circuit_open",
                    severity=ErrorSeverity.CRITICAL,
                    message=f"ErrorEventBus circuit open: {exc}",
                ))

    async def _write_redis(self, batch: list[ErrorEvent]) -> None:
        from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
        mgr = get_pubsub_manager()
        if mgr._redis is None:
            return
        try:
            pipe = mgr._redis.pipeline(transaction=True)
            for ev in batch:
                key = f"error:fp:{ev.fingerprint}"
                pipe.hincrby(key, "count", 1)
                pipe.hset(key, "last_seen", ev.occurred_at.isoformat())
                pipe.hset(key, "severity", ev.severity.value)
                pipe.expire(key, 86400)
                # Severity stream (sorted set, trimmed to last 1000)
                pipe.zadd(
                    f"error:stream:{ev.severity.value}",
                    {json.dumps(ev.to_dict(), ensure_ascii=False, default=str): ev.occurred_at.timestamp()},
                )
                pipe.zremrangebyrank(f"error:stream:{ev.severity.value}", 0, -1001)
                # Hourly counter for Z-score anomaly detection
                import datetime
                hour_key = f"error:hourly:{ev.layer.value}:{ev.category}:{ev.occurred_at.strftime('%Y%m%d%H')}"
                pipe.incr(hour_key)
                pipe.expire(hour_key, 86400 * 2)
            await pipe.execute()
        except Exception as exc:
            logger.warning("ErrorEventBus Redis write failed: %s", exc)

    async def _write_postgres(self, batch: list[ErrorEvent]) -> None:
        from app.database.connection import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            for ev in batch:
                # Upsert into error_events (aggregated)
                await session.execute(text("""
                    INSERT INTO error_events
                        (fingerprint, layer, category, severity, message,
                         count, first_seen, last_seen,
                         trace_id, path, stack_trace, metadata)
                    VALUES
                        (:fp, :layer, :category, :severity, :message,
                         1, :now, :now,
                         :trace_id, :path, :stack_trace, :metadata::jsonb)
                    ON CONFLICT (fingerprint) WHERE resolved_at IS NULL
                    DO UPDATE SET
                        count    = error_events.count + 1,
                        last_seen = EXCLUDED.last_seen,
                        severity  = CASE
                            WHEN EXCLUDED.severity::text = 'critical' THEN 'critical'::error_severity
                            ELSE error_events.severity
                        END,
                        metadata  = error_events.metadata || EXCLUDED.metadata
                """), {
                    "fp": ev.fingerprint,
                    "layer": ev.layer.value,
                    "category": ev.category,
                    "severity": ev.severity.value,
                    "message": ev.message,
                    "now": ev.occurred_at,
                    "trace_id": ev.trace_id or None,
                    "path": ev.path or None,
                    "stack_trace": ev.stack_trace or None,
                    "metadata": json.dumps(ev.metadata, default=str),
                })
                # Append to raw time-series (error_occurrences)
                await session.execute(text("""
                    INSERT INTO error_occurrences
                        (fingerprint, layer, severity, trace_id, metadata, occurred_at)
                    VALUES
                        (:fp, :layer, :severity, :trace_id, :metadata::jsonb, :now)
                """), {
                    "fp": ev.fingerprint,
                    "layer": ev.layer.value,
                    "severity": ev.severity.value,
                    "trace_id": ev.trace_id or None,
                    "metadata": json.dumps(ev.metadata, default=str),
                    "now": ev.occurred_at,
                })
            await session.commit()

    async def _flush_to_redis_only(self) -> None:
        """Circuit open — drain queue to Redis stream only."""
        batch: list[ErrorEvent] = []
        while len(batch) < _FLUSH_BATCH_SIZE and not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            await self._write_redis(batch)


# ── Singleton ─────────────────────────────────────────────────────────────────

_bus: ErrorEventBus | None = None


def get_event_bus() -> ErrorEventBus:
    global _bus
    if _bus is None:
        _bus = ErrorEventBus()
    return _bus


def reset_event_bus() -> None:
    """Test helper."""
    global _bus
    _bus = None
```

- [ ] **Step 4: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_event_bus.py -x -q
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/monitoring/event_bus.py app/tests/unit/test_monitoring/test_event_bus.py
git commit -m "feat(monitoring): add ErrorEventBus with Redis pipeline + circuit breaker"
```

---

## Task 4: Alarm Router (Severity Matrix + Z-Score)

**Files:**
- Create: `app/infrastructure/monitoring/alarm_router.py`
- Create: `app/tests/unit/test_monitoring/test_alarm_router.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_alarm_router.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity
from app.infrastructure.monitoring.alarm_router import AlarmRouter, AnomalyDetector


def make_event(sev=ErrorSeverity.CRITICAL, layer=ErrorLayer.DB, category="test"):
    return ErrorEvent(layer=layer, category=category, severity=sev, message="test")


@pytest.mark.unit
async def test_critical_routes_immediately():
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.CRITICAL)
    with patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send:
        await router.route(ev)
        mock_send.assert_called_once()


@pytest.mark.unit
async def test_warning_does_not_send_immediately():
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.WARNING)
    with patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send:
        await router.route(ev)
        mock_send.assert_not_called()


@pytest.mark.unit
def test_z_score_spike_detection():
    detector = AnomalyDetector()
    # 11 baseline counts of 2, then spike of 20
    counts = [2] * 11 + [20]
    assert detector._compute_z_score(counts) > 3.0


@pytest.mark.unit
def test_z_score_no_spike():
    detector = AnomalyDetector()
    counts = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6]
    assert detector._compute_z_score(counts) < 3.0


@pytest.mark.unit
def test_z_score_insufficient_data():
    detector = AnomalyDetector()
    assert detector._compute_z_score([10, 20]) is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest app/tests/unit/test_monitoring/test_alarm_router.py -x -q
```
Expected: `ImportError`

- [ ] **Step 3: Implement AlarmRouter**

```python
# app/infrastructure/monitoring/alarm_router.py
from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from app.infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from app.infrastructure.monitoring.models import ErrorEvent, ErrorSeverity

logger = get_logger(__name__)

_DEDUP_WINDOW_SECONDS = 900   # 15 min — don't resend same critical within this window
_ANOMALY_WINDOW_SIZE = 12     # 12 × 5min = 1h rolling window
_Z_SCORE_THRESHOLD = 3.0
_MIN_SAMPLES = 6              # Need at least 6 data points for Z-score


class AnomalyDetector:
    """Z-score based spike detector using 1-hour rolling window stored in Redis."""

    def _compute_z_score(self, counts: list[int]) -> float | None:
        if len(counts) < _MIN_SAMPLES:
            return None
        # Latest value is counts[-1], baseline is the rest
        baseline = counts[:-1]
        current = counts[-1]
        mean = statistics.mean(baseline)
        try:
            stdev = statistics.stdev(baseline)
        except statistics.StatisticsError:
            return None
        if stdev == 0:
            return 0.0
        return (current - mean) / stdev

    async def check(self, layer: str, category: str) -> bool:
        """Returns True if current window shows a statistical anomaly (Z > 3)."""
        from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
        import datetime

        mgr = get_pubsub_manager()
        if mgr._redis is None:
            return False
        try:
            now = datetime.datetime.utcnow()
            counts: list[int] = []
            for h in range(_ANOMALY_WINDOW_SIZE, -1, -1):
                dt = now - datetime.timedelta(hours=h // 12, minutes=(h % 12) * 5)
                key = f"error:hourly:{layer}:{category}:{dt.strftime('%Y%m%d%H')}"
                val = await mgr._redis.get(key)
                counts.append(int(val) if val else 0)
            z = self._compute_z_score(counts)
            return z is not None and z > _Z_SCORE_THRESHOLD
        except Exception as exc:
            logger.warning("AnomalyDetector check failed: %s", exc)
            return False


class AlarmRouter:
    """Routes ErrorEvents to Telegram / Sentry based on severity + anomaly detection."""

    def __init__(self) -> None:
        self._anomaly = AnomalyDetector()
        self._sent_critical: dict[str, float] = {}  # fingerprint → sent_at

    async def route(self, event: ErrorEvent) -> None:
        from app.infrastructure.monitoring.models import ErrorSeverity
        import time

        is_anomaly = await self._anomaly.check(event.layer.value, event.category)
        effective_severity = event.severity

        if is_anomaly and effective_severity != ErrorSeverity.CRITICAL:
            effective_severity = ErrorSeverity.CRITICAL
            logger.warning(
                "Anomaly detected (Z>3) for %s/%s — escalating to CRITICAL",
                event.layer.value, event.category,
            )

        if effective_severity == ErrorSeverity.CRITICAL:
            # Dedup: don't resend same fingerprint within 15 min
            last_sent = self._sent_critical.get(event.fingerprint, 0.0)
            if time.monotonic() - last_sent > _DEDUP_WINDOW_SECONDS:
                await self._send_immediate(event, is_anomaly=is_anomaly)
                self._sent_critical[event.fingerprint] = time.monotonic()
        elif effective_severity == ErrorSeverity.ERROR:
            # Aggregated in Redis — digest task will send 5-min summary
            await self._increment_digest_counter(event)
        # WARNING/INFO: logged only (probe already emitted to bus → stored in DB)

    async def _send_immediate(self, event: ErrorEvent, is_anomaly: bool = False) -> None:
        from app.infrastructure.notifications.telegram_notifier import notify_error
        prefix = "🔺 ANOMALİ " if is_anomaly else ""
        layer_emoji = {
            "db": "🗄️", "celery": "⚙️", "api": "🌐",
            "service": "🔧", "frontend": "🖥️", "external": "🔌",
            "security": "🔒", "ml": "🤖",
        }.get(event.layer.value, "❗")

        msg = (
            f"{prefix}{layer_emoji} **{event.layer.value.upper()}** critical\n"
            f"`{event.category}` — {event.message[:300]}\n"
            f"trace: `{event.trace_id or 'n/a'}`"
        )
        import asyncio
        asyncio.create_task(notify_error(
            level="critical",
            message=msg,
            path=event.path,
            trace_id=event.trace_id,
        ))

        # Also capture in Sentry
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("layer", event.layer.value)
                scope.set_tag("category", event.category)
                scope.set_context("error_event", event.to_dict())
                sentry_sdk.capture_message(event.message, level="fatal")
        except Exception:
            pass

    async def _increment_digest_counter(self, event: ErrorEvent) -> None:
        from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
        mgr = get_pubsub_manager()
        if mgr._redis is None:
            return
        try:
            key = f"error:digest:{event.layer.value}:{event.category}"
            await mgr._redis.hincrby(key, "count", 1)
            await mgr._redis.hset(key, "severity", event.severity.value)
            await mgr._redis.hset(key, "message_sample", event.message[:200])
            await mgr._redis.expire(key, 600)  # 10 min TTL — cleared after digest sends
        except Exception as exc:
            logger.warning("AlarmRouter digest counter failed: %s", exc)


_router: AlarmRouter | None = None


def get_alarm_router() -> AlarmRouter:
    global _router
    if _router is None:
        _router = AlarmRouter()
    return _router
```

- [ ] **Step 4: Wire AlarmRouter into EventBus flush**

In `app/infrastructure/monitoring/event_bus.py`, add alarm routing in `_flush_batch` after Redis write:

```python
# In _flush_batch, after await self._write_redis(batch):
from app.infrastructure.monitoring.alarm_router import get_alarm_router
router = get_alarm_router()
for ev in batch:
    await router.route(ev)
```

- [ ] **Step 5: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_alarm_router.py -x -q
```
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add app/infrastructure/monitoring/alarm_router.py app/tests/unit/test_monitoring/test_alarm_router.py app/infrastructure/monitoring/event_bus.py
git commit -m "feat(monitoring): add AlarmRouter with Z-score anomaly detection and severity matrix"
```

---

## Task 5: Celery Digest Task + Beat Schedule

**Files:**
- Create: `app/workers/tasks/error_digest.py`
- Modify: `app/infrastructure/background/celery_app.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write digest task**

```python
# app/workers/tasks/error_digest.py
"""
Error monitoring Celery tasks:
 - error_digest_every_5m   : send aggregated Telegram summary + refresh mat. view
 - db_health_check_every_5m: long-running TX, lock waits, table bloat (Plan 2 DB Probe)
"""
import asyncio

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


async def _run_digest() -> None:
    from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
    from app.infrastructure.notifications.telegram_notifier import notify_error

    mgr = get_pubsub_manager()
    if mgr._redis is None:
        return

    # Scan digest counters
    try:
        keys = await mgr._redis.keys("error:digest:*")
    except Exception as exc:
        logger.warning("Digest Redis scan failed: %s", exc)
        return

    if not keys:
        return

    lines: list[str] = []
    pipe = mgr._redis.pipeline()
    for key in keys:
        pipe.hgetall(key)
    results = await pipe.execute()

    # Delete consumed keys
    del_pipe = mgr._redis.pipeline()
    for key in keys:
        del_pipe.delete(key)
    await del_pipe.execute()

    layer_totals: dict[str, int] = {}
    for key, data in zip(keys, results):
        if not data:
            continue
        parts = key.split(":")  # error:digest:{layer}:{category}
        if len(parts) < 4:
            continue
        layer = parts[2]
        category = parts[3]
        count = int(data.get("count", 1))
        sample = data.get("message_sample", "")[:100]
        layer_totals[layer] = layer_totals.get(layer, 0) + count
        lines.append(f"  • {layer}/{category}: {count}× — {sample}")

    if not lines:
        return

    summary_parts = [f"{layer}: {cnt}" for layer, cnt in sorted(layer_totals.items())]
    header = f"📊 5dk Özet — {', '.join(summary_parts)}"
    body = "\n".join(lines[:20])  # max 20 lines
    if len(lines) > 20:
        body += f"\n  …ve {len(lines) - 20} daha"

    await notify_error(level="error", message=f"{header}\n{body}", path="digest")

    # Refresh materialized view
    try:
        from app.database.connection import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY error_hourly_stats")
            )
            await session.commit()
    except Exception as exc:
        logger.warning("error_hourly_stats refresh failed: %s", exc)


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
    from app.database.connection import AsyncSessionLocal
    from sqlalchemy import text

    today = datetime.date.today()
    # Next month
    if today.month == 12:
        year, month = today.year + 1, 1
    else:
        year, month = today.year, today.month + 1

    partition_name = f"error_occurrences_{year}_{month:02d}"
    from_date = datetime.date(year, month, 1)
    if month == 12:
        to_date = datetime.date(year + 1, 1, 1)
    else:
        to_date = datetime.date(year, month + 1, 1)

    async with AsyncSessionLocal() as session:
        await session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF error_occurrences
            FOR VALUES FROM ('{from_date}') TO ('{to_date}');
        """))
        await session.commit()
    logger.info("Created partition %s", partition_name)
```

- [ ] **Step 2: Register beat schedules in celery_app.py**

In `app/infrastructure/background/celery_app.py`, add to `beat_schedule`:

```python
"monitoring-error-digest-every-5m": {
    "task": "monitoring.error_digest",
    "schedule": 300.0,
},
"monitoring-create-monthly-partition-daily": {
    "task": "monitoring.create_monthly_partition",
    "schedule": 86400.0,
},
```

And add import at the bottom of the file:

```python
import app.workers.tasks.error_digest  # noqa: E402,F401
```

- [ ] **Step 3: Wire EventBus into lifespan in main.py**

In `app/main.py`, update the lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LojiNext (%s)", settings.ENVIRONMENT)
    from app.infrastructure.resilience.shutdown import register_shutdown_handlers
    register_shutdown_handlers()

    # Start error event bus background flusher
    from app.infrastructure.monitoring.event_bus import get_event_bus
    bus = get_event_bus()
    bus.start()

    try:
        yield
    finally:
        bus.stop()
        from app.core.container import get_container
        get_container().shutdown()
        await engine.dispose()
        logger.info("Shutdown complete")
```

- [ ] **Step 4: Run full unit test suite**

```bash
pytest app/tests/unit/test_monitoring/ -x -q
```
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks/error_digest.py app/infrastructure/background/celery_app.py app/main.py
git commit -m "feat(monitoring): add error digest Celery task, monthly partition creator, wire EventBus to lifespan"
```

---

## Self-Review Checklist

- [x] ErrorEvent dataclass with Blake2b fingerprint ✓
- [x] Alembic migration: error_events (upsert), error_occurrences (partitioned), materialized view ✓
- [x] ErrorEventBus: async queue, Redis pipeline, PostgreSQL upsert, circuit breaker ✓
- [x] AlarmRouter: critical → immediate Telegram+Sentry, error → digest counter, Z-score anomaly ✓
- [x] Celery digest: 5min Telegram summary, materialized view refresh ✓
- [x] Monthly partition creator ✓
- [x] EventBus wired to lifespan ✓
- [x] No TBD/TODO placeholders ✓
- [x] Type names consistent across all tasks ✓
