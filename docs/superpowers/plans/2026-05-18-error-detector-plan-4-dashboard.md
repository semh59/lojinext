# Error Detector — Plan 4: Dashboard & API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend REST + SSE API for error data, and the SistemSaglikPage "Hata Analizi" tab with real-time updates, layer filter, trace_id drill-down, and resolve workflow.

**Architecture:** FastAPI endpoints read from `error_events` + `error_hourly_stats` (mat. view). SSE stream uses PostgreSQL `LISTEN/NOTIFY` via asyncpg directly. React frontend uses `useEventSource` hook + Recharts for the live graph.

**Tech Stack:** FastAPI, asyncpg (direct, not through SQLAlchemy pool), SSE via `StreamingResponse`, React, Recharts, TanStack Query.

**Depends on:** Plans 1 + 2 (error_events table and probes must exist).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `app/api/v1/endpoints/system.py` | GET error-events, GET error-stats, POST resolve, full batch endpoint |
| Create | `app/api/v1/endpoints/error_stream.py` | GET /error-stream SSE endpoint (asyncpg LISTEN) |
| Modify | `app/api/v1/api.py` | Register error_stream router |
| Create | `frontend/src/hooks/use-event-source.ts` | SSE React hook |
| Modify | `frontend/src/pages/admin/SistemSaglikPage.tsx` | Hata Analizi tab |
| Create | `frontend/src/services/api/error-service.ts` | API calls for error endpoints |
| Create | `app/tests/unit/test_monitoring/test_error_api.py` | Unit tests for endpoints |

---

## Task 1: Backend REST Endpoints

**Files:**
- Modify: `app/api/v1/endpoints/system.py`
- Create: `app/tests/unit/test_monitoring/test_error_api.py`

- [ ] **Step 1: Write failing tests**

```python
# app/tests/unit/test_monitoring/test_error_api.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.unit
async def test_error_events_requires_auth(async_client):
    resp = await async_client.get("/api/v1/system/error-events")
    assert resp.status_code in (401, 403)


@pytest.mark.unit
async def test_error_stats_response_shape(async_client, admin_token):
    with patch("app.api.v1.endpoints.system._get_error_stats",
               new_callable=AsyncMock) as mock:
        mock.return_value = []
        resp = await async_client.get(
            "/api/v1/system/error-stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "stats" in resp.json()
```

> Note: `async_client` and `admin_token` fixtures are defined in `app/tests/conftest.py`. If they don't exist for system endpoints yet, add minimal fixtures following the existing pattern in `app/tests/api/test_admin_health_and_roles.py`.

- [ ] **Step 2: Add GET endpoints to system.py**

```python
# Add to app/api/v1/endpoints/system.py

from typing import Literal, Optional
from fastapi import Query as QueryParam

# ── Error event query models ────────────────────────────────────────────

class ErrorEventOut(BaseModel):
    id: int
    fingerprint: str
    layer: str
    category: str
    severity: str
    message: str
    count: int
    first_seen: str
    last_seen: str
    trace_id: Optional[str] = None
    path: Optional[str] = None
    metadata: dict = {}
    resolved_at: Optional[str] = None

class ErrorEventsResponse(BaseModel):
    items: list[ErrorEventOut]
    total: int
    page: int
    page_size: int

class ErrorStatsRow(BaseModel):
    hour: str
    layer: str
    severity: str
    event_count: int

class ErrorStatsResponse(BaseModel):
    stats: list[ErrorStatsRow]


# ── GET /error-events ────────────────────────────────────────────────────

@router.get("/error-events", response_model=ErrorEventsResponse)
async def get_error_events(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    layer: Optional[str] = QueryParam(None),
    severity: Optional[str] = QueryParam(None),
    resolved: bool = QueryParam(False),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(50, ge=1, le=200),
):
    """List error events. Admin only."""
    from app.database.connection import AsyncSessionLocal
    from sqlalchemy import text

    conditions = []
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if layer:
        conditions.append("layer = :layer::error_layer")
        params["layer"] = layer
    if severity:
        conditions.append("severity = :severity::error_severity")
        params["severity"] = severity
    if not resolved:
        conditions.append("resolved_at IS NULL")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with AsyncSessionLocal() as session:
        count_row = await session.execute(
            text(f"SELECT COUNT(*) FROM error_events {where}"), params
        )
        total = count_row.scalar_one()

        rows = await session.execute(
            text(f"""
                SELECT id, fingerprint, layer, category, severity, message,
                       count, first_seen, last_seen, trace_id, path, metadata, resolved_at
                FROM error_events {where}
                ORDER BY last_seen DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        items = [
            ErrorEventOut(
                id=r.id, fingerprint=r.fingerprint, layer=r.layer,
                category=r.category, severity=r.severity, message=r.message,
                count=r.count,
                first_seen=r.first_seen.isoformat(),
                last_seen=r.last_seen.isoformat(),
                trace_id=r.trace_id, path=r.path,
                metadata=r.metadata or {},
                resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
            )
            for r in rows
        ]

    return ErrorEventsResponse(items=items, total=total, page=page, page_size=page_size)


# ── GET /error-stats ─────────────────────────────────────────────────────

async def _get_error_stats():
    from app.database.connection import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        rows = await session.execute(text("""
            SELECT hour, layer, severity, event_count
            FROM error_hourly_stats
            ORDER BY hour DESC, layer, severity
        """))
        return [
            ErrorStatsRow(
                hour=r.hour.isoformat(), layer=r.layer,
                severity=r.severity, event_count=r.event_count,
            )
            for r in rows
        ]


@router.get("/error-stats", response_model=ErrorStatsResponse)
async def get_error_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Return hourly aggregated error stats from materialized view. Admin only."""
    stats = await _get_error_stats()
    return ErrorStatsResponse(stats=stats)


# ── POST /error-events/{id}/resolve ──────────────────────────────────────

@router.post("/error-events/{event_id}/resolve", status_code=204)
async def resolve_error_event(
    event_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Mark an error event as resolved. Admin only."""
    from app.database.connection import AsyncSessionLocal
    from sqlalchemy import text
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                UPDATE error_events
                SET resolved_at = :now, resolved_by = :user_id
                WHERE id = :event_id AND resolved_at IS NULL
            """),
            {"now": datetime.now(timezone.utc), "user_id": current_user.id,
             "event_id": event_id},
        )
        await session.commit()
        if result.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Event not found or already resolved")
```

Also upgrade the `/error-report-batch` stub from Plan 3 to emit proper ErrorEvents:

```python
# Upgrade /error-report-batch to use ErrorEventBus:
@router.post("/error-report-batch", status_code=204)
@limiter.limit("5/minute")
async def receive_frontend_error_batch(
    reports: List[FrontendErrorReport],
    request: Request,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Accept batch from navigator.sendBeacon (pagehide)."""
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

    for report in reports[:20]:
        severity_map = {"fatal": ErrorSeverity.CRITICAL, "error": ErrorSeverity.ERROR,
                        "warning": ErrorSeverity.WARNING}
        await aemit(ErrorEvent(
            layer=ErrorLayer.FRONTEND,
            category="js_error_batch",
            severity=severity_map.get(report.severity, ErrorSeverity.ERROR),
            message=report.message[:500],
            trace_id=getattr(report, "backend_trace_id", "") or "",
            path=report.url[:300],
            metadata={
                "user_id": current_user.id,
                "user_agent": report.userAgent[:200],
                "frontend_session_id": getattr(report, "frontend_session_id", ""),
            },
        ))
```

Update `FrontendErrorReport` schema to include the new fields:

```python
class FrontendErrorReport(BaseModel):
    message: str = Field(max_length=_MAX_MESSAGE_LEN)
    stack: Optional[str] = Field(default=None, max_length=_MAX_STACK_LEN)
    componentStack: Optional[str] = Field(default=None, max_length=_MAX_STACK_LEN)
    url: str = Field(max_length=500)
    userAgent: str = Field(max_length=300)
    timestamp: str = Field(max_length=50)
    severity: Literal["error", "warning", "fatal"] = "error"
    backend_trace_id: Optional[str] = Field(default=None, max_length=64)
    frontend_session_id: Optional[str] = Field(default=None, max_length=50)
    extra: Optional[dict] = None
```

Also update the single `/error-report` endpoint to emit through ErrorEventBus:

```python
@router.post("/error-report", status_code=204)
@limiter.limit("20/hour")
async def receive_frontend_error(
    report: FrontendErrorReport,
    request: Request,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

    severity_map = {"fatal": ErrorSeverity.CRITICAL, "error": ErrorSeverity.ERROR,
                    "warning": ErrorSeverity.WARNING}
    await aemit(ErrorEvent(
        layer=ErrorLayer.FRONTEND,
        category="js_error",
        severity=severity_map.get(report.severity, ErrorSeverity.ERROR),
        message=report.message[:500],
        trace_id=report.backend_trace_id or "",
        path=report.url[:300],
        metadata={
            "user_id": current_user.id,
            "component_stack": (report.componentStack or "")[:500],
            "frontend_session_id": report.frontend_session_id or "",
        },
    ))
```

- [ ] **Step 3: Run tests**

```bash
pytest app/tests/unit/test_monitoring/test_error_api.py -x -q
```

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/endpoints/system.py app/tests/unit/test_monitoring/test_error_api.py
git commit -m "feat(dashboard): add GET /error-events, GET /error-stats, POST /resolve — admin endpoints"
```

---

## Task 2: SSE Stream Endpoint

**Files:**
- Create: `app/api/v1/endpoints/error_stream.py`
- Modify: `app/api/v1/api.py`

PostgreSQL `LISTEN/NOTIFY`: when a new row is inserted into `error_events`, a trigger fires `NOTIFY error_events_channel`. The SSE endpoint listens on this channel and forwards events to the browser.

- [ ] **Step 1: Create the NOTIFY trigger migration**

Add a new Alembic migration:

```bash
alembic revision -m "add_error_events_notify_trigger"
```

```python
# In the new migration:

def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_error_event()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify(
                'error_events_channel',
                json_build_object(
                    'id', NEW.id,
                    'fingerprint', NEW.fingerprint,
                    'layer', NEW.layer::text,
                    'category', NEW.category,
                    'severity', NEW.severity::text,
                    'message', LEFT(NEW.message, 200),
                    'count', NEW.count,
                    'last_seen', NEW.last_seen
                )::text
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER error_events_notify
        AFTER INSERT OR UPDATE ON error_events
        FOR EACH ROW EXECUTE FUNCTION notify_error_event();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS error_events_notify ON error_events;")
    op.execute("DROP FUNCTION IF EXISTS notify_error_event();")
```

Apply:
```bash
alembic upgrade head
alembic check
```

- [ ] **Step 2: Implement SSE endpoint**

```python
# app/api/v1/endpoints/error_stream.py
"""
Server-Sent Events endpoint for real-time error monitoring.
Uses asyncpg LISTEN/NOTIFY directly (not SQLAlchemy pool) so the
connection stays open for the lifetime of the SSE stream.
"""
from __future__ import annotations

import asyncio
import json
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_active_admin
from app.config import settings
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

_KEEPALIVE_INTERVAL = 25  # seconds — browsers disconnect SSE after ~30s without data


async def _sse_generator(user_id: int) -> AsyncGenerator[str, None]:
    """
    Open a dedicated asyncpg connection, LISTEN on error_events_channel,
    and yield SSE-formatted messages. Sends keepalive comments every 25s.
    """
    import asyncpg
    from sqlalchemy.engine.url import make_url

    url = make_url(settings.DATABASE_URL)
    # Convert to asyncpg DSN (no +asyncpg prefix)
    dsn = str(url.set(drivername="postgresql"))

    conn: asyncpg.Connection | None = None
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    def _notify_callback(conn_ref, pid, channel, payload):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # Slow consumer — drop

    try:
        conn = await asyncpg.connect(dsn=dsn)
        await conn.add_listener("error_events_channel", _notify_callback)
        logger.info("SSE error stream opened for user %d", user_id)

        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_INTERVAL)
                # Parse and re-emit as SSE data
                try:
                    data = json.loads(payload)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except (json.JSONDecodeError, Exception):
                    pass
            except asyncio.TimeoutError:
                # Keepalive comment — prevents browser from closing the connection
                yield ": keepalive\n\n"

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("SSE stream error for user %d: %s", user_id, exc)
        yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
    finally:
        if conn and not conn.is_closed():
            try:
                await conn.remove_listener("error_events_channel", _notify_callback)
                await conn.close()
            except Exception:
                pass
        logger.info("SSE error stream closed for user %d", user_id)


@router.get("/error-stream")
async def error_stream(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """
    Server-Sent Events stream of live error_events.
    Admin only. Connect once; each new/updated error_event is pushed.

    Event format: data: {"id": 1, "layer": "db", "severity": "critical", ...}
    """
    return StreamingResponse(
        _sse_generator(current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

- [ ] **Step 3: Register router in api.py**

In `app/api/v1/api.py`, add:

```python
from app.api.v1.endpoints.error_stream import router as error_stream_router
api_router.include_router(error_stream_router, prefix="/system", tags=["monitoring"])
```

- [ ] **Step 4: Smoke test SSE**

```bash
uvicorn app.main:app --reload &
# Get a valid admin token first, then:
curl -N -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/system/error-stream
```
Expected: `: keepalive` comment every 25s, live events when errors occur.

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/endpoints/error_stream.py app/api/v1/api.py alembic/
git commit -m "feat(dashboard): add SSE /error-stream endpoint with PostgreSQL LISTEN/NOTIFY"
```

---

## Task 3: Frontend API Service

**Files:**
- Create: `frontend/src/services/api/error-service.ts`
- Create: `frontend/src/hooks/use-event-source.ts`

- [ ] **Step 1: Create error-service.ts**

```typescript
// frontend/src/services/api/error-service.ts
import axiosInstance from './axios-instance';

export interface ErrorEventItem {
  id: number;
  fingerprint: string;
  layer: string;
  category: string;
  severity: 'critical' | 'error' | 'warning' | 'info';
  message: string;
  count: number;
  first_seen: string;
  last_seen: string;
  trace_id?: string;
  path?: string;
  metadata: Record<string, unknown>;
  resolved_at?: string;
}

export interface ErrorEventsResponse {
  items: ErrorEventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ErrorStatsRow {
  hour: string;
  layer: string;
  severity: string;
  event_count: number;
}

export interface ErrorFilters {
  layer?: string;
  severity?: string;
  resolved?: boolean;
  page?: number;
  pageSize?: number;
}

export const errorService = {
  async getEvents(filters: ErrorFilters = {}): Promise<ErrorEventsResponse> {
    const params = new URLSearchParams();
    if (filters.layer) params.set('layer', filters.layer);
    if (filters.severity) params.set('severity', filters.severity);
    if (filters.resolved !== undefined) params.set('resolved', String(filters.resolved));
    if (filters.page) params.set('page', String(filters.page));
    if (filters.pageSize) params.set('page_size', String(filters.pageSize));

    const { data } = await axiosInstance.get<ErrorEventsResponse>(
      `/system/error-events?${params}`
    );
    return data;
  },

  async getStats(): Promise<ErrorStatsRow[]> {
    const { data } = await axiosInstance.get<{ stats: ErrorStatsRow[] }>(
      '/system/error-stats'
    );
    return data.stats;
  },

  async resolve(eventId: number): Promise<void> {
    await axiosInstance.post(`/system/error-events/${eventId}/resolve`);
  },
};
```

- [ ] **Step 2: Create useEventSource hook**

```typescript
// frontend/src/hooks/use-event-source.ts
import { useEffect, useRef, useState, useCallback } from 'react';

export interface SSEState<T> {
  lastEvent: T | null;
  connected: boolean;
  error: string | null;
}

/**
 * React hook for Server-Sent Events.
 * Automatically reconnects on disconnect (exponential backoff, max 30s).
 * Requires a valid JWT token in localStorage (passed as query param or cookie).
 */
export function useEventSource<T = unknown>(
  url: string,
  enabled: boolean = true
): SSEState<T> {
  const [state, setState] = useState<SSEState<T>>({
    lastEvent: null, connected: false, error: null,
  });
  const esRef = useRef<EventSource | null>(null);
  const retryDelay = useRef(1000);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (!enabled) return;

    // Get token for authentication (EventSource doesn't support custom headers)
    // Backend must support token as query param, or use a short-lived ticket
    const token = localStorage.getItem('auth_token') ?? '';
    const fullUrl = `${url}?token=${encodeURIComponent(token)}`;

    const es = new EventSource(fullUrl);
    esRef.current = es;

    es.onopen = () => {
      setState((s) => ({ ...s, connected: true, error: null }));
      retryDelay.current = 1000; // Reset backoff on success
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as T;
        setState((s) => ({ ...s, lastEvent: data }));
      } catch {
        // Ignore malformed messages
      }
    };

    es.onerror = () => {
      es.close();
      setState((s) => ({ ...s, connected: false }));
      // Exponential backoff: 1s, 2s, 4s, ..., 30s
      const delay = Math.min(retryDelay.current, 30_000);
      retryDelay.current = Math.min(delay * 2, 30_000);
      retryTimer.current = setTimeout(connect, delay);
    };
  }, [url, enabled]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      if (retryTimer.current) clearTimeout(retryTimer.current);
    };
  }, [connect]);

  return state;
}
```

> **Note on auth:** EventSource doesn't support `Authorization` headers. Options:
> 1. Accept token as query param in the SSE endpoint and validate it.
> 2. Use a short-lived SSE ticket: call `POST /system/sse-ticket` → get one-time token valid 30s → pass as query param.
>
> For simplicity, implement option 1: add query param token support to the `error_stream` endpoint by reading `token` from `request.query_params` and validating it with the existing `decode_access_token` function.

- [ ] **Step 3: Add query-param token support to error_stream.py**

```python
# In error_stream.py, replace the Depends(get_current_active_admin) approach:

from fastapi import Request
from app.core.security import decode_access_token

@router.get("/error-stream")
async def error_stream(request: Request):
    """
    SSE stream. Auth via ?token=<JWT> query param
    (EventSource API doesn't support Authorization header).
    """
    token = request.query_params.get("token", "")
    if not token:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"error": {"code": "UNAUTHORIZED"}})

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", 0))
        is_admin = payload.get("is_admin", False)
        if not is_admin:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"error": {"code": "FORBIDDEN"}})
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"error": {"code": "INVALID_TOKEN"}})

    return StreamingResponse(
        _sse_generator(user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api/error-service.ts frontend/src/hooks/use-event-source.ts app/api/v1/endpoints/error_stream.py
git commit -m "feat(dashboard): add error-service.ts, useEventSource hook, SSE query-param auth"
```

---

## Task 4: SistemSaglikPage — Hata Analizi Tab

**Files:**
- Modify: `frontend/src/pages/admin/SistemSaglikPage.tsx`

- [ ] **Step 1: Read current SistemSaglikPage.tsx**

```bash
head -80 frontend/src/pages/admin/SistemSaglikPage.tsx
```

- [ ] **Step 2: Add Hata Analizi tab**

Add the tab alongside existing tabs in `SistemSaglikPage.tsx`. Below is the complete tab implementation to insert:

```typescript
// Add these imports at the top of SistemSaglikPage.tsx:
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { errorService, ErrorEventItem, ErrorStatsRow, ErrorFilters } from '../../services/api/error-service';
import { useEventSource } from '../../hooks/use-event-source';
import { AlertTriangle, CheckCircle, RefreshCw, ExternalLink } from 'lucide-react';

// ── Layer + severity constants ────────────────────────────────────────────

const LAYERS = ['db', 'celery', 'api', 'service', 'frontend', 'external', 'security', 'ml'] as const;
const SEVERITIES = ['critical', 'error', 'warning', 'info'] as const;
const SEVERITY_COLORS = {
  critical: '#ef4444',
  error:    '#f97316',
  warning:  '#eab308',
  info:     '#3b82f6',
} as const;
const LAYER_EMOJI: Record<string, string> = {
  db: '🗄️', celery: '⚙️', api: '🌐', service: '🔧',
  frontend: '🖥️', external: '🔌', security: '🔒', ml: '🤖',
};

// ── HataAnaliziTab component ──────────────────────────────────────────────

function HataAnaliziTab() {
  const qc = useQueryClient();
  const [filters, setFilters] = React.useState<ErrorFilters>({ page: 1, pageSize: 50 });

  // REST queries
  const eventsQuery = useQuery({
    queryKey: ['error-events', filters],
    queryFn: () => errorService.getEvents(filters),
    refetchInterval: 30_000,
  });
  const statsQuery = useQuery({
    queryKey: ['error-stats'],
    queryFn: () => errorService.getStats(),
    refetchInterval: 300_000, // materialized view refreshes every 5min
  });

  // SSE live updates — when a new event arrives, refetch events list
  const { lastEvent, connected } = useEventSource<ErrorEventItem>(
    '/api/v1/system/error-stream'
  );
  React.useEffect(() => {
    if (lastEvent) {
      qc.invalidateQueries({ queryKey: ['error-events'] });
    }
  }, [lastEvent, qc]);

  // Resolve mutation
  const resolveMutation = useMutation({
    mutationFn: (id: number) => errorService.resolve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['error-events'] }),
  });

  // Prepare chart data from stats
  const chartData = React.useMemo(() => {
    if (!statsQuery.data) return [];
    const byHour: Record<string, Record<string, number>> = {};
    statsQuery.data.forEach((row) => {
      if (!byHour[row.hour]) byHour[row.hour] = { hour: row.hour };
      byHour[row.hour][row.severity] = (byHour[row.hour][row.severity] ?? 0) + row.event_count;
    });
    return Object.values(byHour)
      .sort((a, b) => String(a.hour).localeCompare(String(b.hour)))
      .slice(-24); // last 24 hours
  }, [statsQuery.data]);

  // Summary counts
  const totalUnresolved = eventsQuery.data?.total ?? 0;
  const criticalCount = eventsQuery.data?.items.filter(
    (e) => e.severity === 'critical' && !e.resolved_at
  ).length ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
          <span className="text-sm text-secondary">{connected ? 'Canlı' : 'Bağlanıyor...'}</span>
          <span className="text-sm text-secondary">·</span>
          <span className="text-sm text-secondary">Son 24 Saat: <strong>{totalUnresolved}</strong> aktif hata</span>
          {criticalCount > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-500/10 text-red-500 text-xs font-bold">
              {criticalCount} kritik
            </span>
          )}
        </div>
        <button
          onClick={() => qc.invalidateQueries({ queryKey: ['error-events', 'error-stats'] })}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border text-secondary hover:text-primary text-sm transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Yenile
        </button>
      </div>

      {/* Layer filter pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilters((f) => ({ ...f, layer: undefined, page: 1 }))}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            !filters.layer ? 'bg-accent text-white' : 'bg-surface border border-border text-secondary hover:text-primary'
          }`}
        >
          Tümü
        </button>
        {LAYERS.map((layer) => (
          <button
            key={layer}
            onClick={() => setFilters((f) => ({ ...f, layer, page: 1 }))}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filters.layer === layer
                ? 'bg-accent text-white'
                : 'bg-surface border border-border text-secondary hover:text-primary'
            }`}
          >
            {LAYER_EMOJI[layer]} {layer}
          </button>
        ))}
      </div>

      {/* Hourly chart */}
      {chartData.length > 0 && (
        <div className="bg-surface border border-border rounded-2xl p-4">
          <p className="text-sm font-medium text-secondary mb-3">Saatlik Hata Dağılımı</p>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis dataKey="hour" tick={{ fontSize: 10 }}
                tickFormatter={(v) => new Date(v).getHours() + ':00'} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                formatter={(value, name) => [value, name]}
                labelFormatter={(l) => new Date(l).toLocaleTimeString('tr-TR')}
              />
              <Legend />
              {SEVERITIES.map((sev) => (
                <Area key={sev} type="monotone" dataKey={sev}
                  stroke={SEVERITY_COLORS[sev]}
                  fill={SEVERITY_COLORS[sev] + '22'}
                  stackId="1" strokeWidth={1.5} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Events table */}
      <div className="bg-surface border border-border rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Fingerprint</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Katman</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Kategori</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Severity</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Adet</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Son Görülme</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium">Trace ID</th>
              <th className="px-4 py-3 text-left text-xs text-secondary font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {eventsQuery.isLoading && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-secondary">Yükleniyor...</td></tr>
            )}
            {eventsQuery.data?.items.map((ev) => (
              <tr key={ev.id}
                  className="border-b border-border/50 hover:bg-elevated/50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-secondary">{ev.fingerprint.slice(0, 8)}</td>
                <td className="px-4 py-3">
                  <span className="text-sm">{LAYER_EMOJI[ev.layer]} {ev.layer}</span>
                </td>
                <td className="px-4 py-3 text-xs text-secondary max-w-[200px] truncate" title={ev.message}>
                  {ev.category}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-bold"
                    style={{
                      backgroundColor: SEVERITY_COLORS[ev.severity as keyof typeof SEVERITY_COLORS] + '22',
                      color: SEVERITY_COLORS[ev.severity as keyof typeof SEVERITY_COLORS],
                    }}
                  >
                    {ev.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm font-medium">{ev.count.toLocaleString('tr-TR')}</td>
                <td className="px-4 py-3 text-xs text-secondary">
                  {new Date(ev.last_seen).toLocaleString('tr-TR')}
                </td>
                <td className="px-4 py-3">
                  {ev.trace_id ? (
                    <span className="font-mono text-xs text-accent">{ev.trace_id.slice(0, 8)}</span>
                  ) : (
                    <span className="text-xs text-secondary/40">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {!ev.resolved_at && (
                    <button
                      onClick={() => resolveMutation.mutate(ev.id)}
                      disabled={resolveMutation.isPending}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <CheckCircle className="w-3 h-3" />
                      Çözüldü
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        {(eventsQuery.data?.total ?? 0) > (filters.pageSize ?? 50) && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-secondary">
              Toplam {eventsQuery.data?.total} kayıt
            </span>
            <div className="flex gap-2">
              <button
                disabled={(filters.page ?? 1) <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                className="px-3 py-1 rounded-lg border border-border text-xs disabled:opacity-40 hover:bg-elevated transition-colors"
              >
                ← Önceki
              </button>
              <button
                disabled={
                  ((filters.page ?? 1) * (filters.pageSize ?? 50)) >= (eventsQuery.data?.total ?? 0)
                }
                onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                className="px-3 py-1 rounded-lg border border-border text-xs disabled:opacity-40 hover:bg-elevated transition-colors"
              >
                Sonraki →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

Add `HataAnaliziTab` to the existing tab list in `SistemSaglikPage`. Find the tab definitions and add:

```typescript
{ id: 'hata-analizi', label: '🔍 Hata Analizi', component: <HataAnaliziTab /> },
```

Also add `import React from 'react';` if not present, and `recharts` if not installed:

```bash
cd frontend && npm install recharts
```

- [ ] **Step 3: Run type check + lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Run vitest**

```bash
cd frontend && npx vitest --run
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/SistemSaglikPage.tsx frontend/src/services/api/error-service.ts frontend/src/hooks/use-event-source.ts
git commit -m "feat(dashboard): add Hata Analizi tab to SistemSaglikPage with SSE live updates, charts, resolve workflow"
```

---

## Self-Review Checklist

- [x] GET /error-events: paginated, filtered by layer/severity/resolved ✓
- [x] GET /error-stats: hourly aggregates from materialized view ✓
- [x] POST /error-events/{id}/resolve: admin only, marks resolved_at + resolved_by ✓
- [x] POST /error-report-batch: upgraded to emit through ErrorEventBus ✓
- [x] POST /error-report: upgraded to emit through ErrorEventBus ✓
- [x] FrontendErrorReport schema: added backend_trace_id, frontend_session_id, extra ✓
- [x] SSE endpoint: asyncpg LISTEN/NOTIFY, keepalive, exponential reconnect ✓
- [x] PostgreSQL NOTIFY trigger migration ✓
- [x] SSE auth via query-param token (EventSource limitation) ✓
- [x] error-service.ts: getEvents, getStats, resolve ✓
- [x] useEventSource: auto-reconnect with exponential backoff ✓
- [x] SistemSaglikPage: live indicator, layer filter pills, hourly chart, event table, resolve button, pagination ✓
- [x] recharts for visualization ✓
- [x] No TBD/TODO placeholders ✓
- [x] Type names consistent across all tasks ✓
