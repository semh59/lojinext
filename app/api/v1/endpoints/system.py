from datetime import datetime, timezone
from typing import Annotated, Any, List, Literal, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Query as QueryParam
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_admin, get_current_active_user
from app.api.middleware.rate_limiter import limiter
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

_MAX_MESSAGE_LEN = 2000
_MAX_STACK_LEN = 8000


# ── Frontend error report schema ─────────────────────────────────────────────


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


# ── Error event API schemas ───────────────────────────────────────────────────


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
    metadata: dict = Field(default_factory=dict)
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


# ── POST /error-report ────────────────────────────────────────────────────────


@router.post("/error-report", status_code=204)
@limiter.limit("200/hour")
async def receive_frontend_error(
    report: FrontendErrorReport,
    request: Request,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Accept client-side JS error reports from the authenticated error tracker."""
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import (
        ErrorEvent,
        ErrorLayer,
        ErrorSeverity,
    )

    severity_map = {
        "fatal": ErrorSeverity.CRITICAL,
        "error": ErrorSeverity.ERROR,
        "warning": ErrorSeverity.WARNING,
    }
    await aemit(
        ErrorEvent(
            layer=ErrorLayer.FRONTEND,
            category="js_error",
            severity=severity_map.get(report.severity, ErrorSeverity.ERROR),
            message=report.message[:500],
            # report.stack frontend'ten geliyordu ama aemit'e geçilmiyordu —
            # trace UI'da stack_trace null görünüyordu, debug zorlaşıyordu.
            stack_trace=(report.stack or "")[:4000],
            trace_id=report.backend_trace_id or "",
            path=report.url[:300],
            metadata={
                "user_id": current_user.id,
                "component_stack": (report.componentStack or "")[:500],
                "frontend_session_id": report.frontend_session_id or "",
            },
        )
    )


# ── POST /error-report-batch ─────────────────────────────────────────────────


@router.post("/error-report-batch", status_code=204)
@limiter.limit("2/minute")
async def receive_frontend_error_batch(
    reports: List[FrontendErrorReport],
    request: Request,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Accept batch of client-side JS error reports (sent via navigator.sendBeacon)."""
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import (
        ErrorEvent,
        ErrorLayer,
        ErrorSeverity,
    )

    severity_map = {
        "fatal": ErrorSeverity.CRITICAL,
        "error": ErrorSeverity.ERROR,
        "warning": ErrorSeverity.WARNING,
    }
    if len(reports) > 20:
        raise HTTPException(
            status_code=400,
            detail="Batch too large: max 20 reports per request",
        )
    for report in reports:
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.FRONTEND,
                category="js_error_batch",
                severity=severity_map.get(report.severity, ErrorSeverity.ERROR),
                message=report.message[:500],
                stack_trace=(report.stack or "")[:4000],
                trace_id=report.backend_trace_id or "",
                path=report.url[:300],
                metadata={
                    "user_id": current_user.id,
                    "user_agent": report.userAgent[:200],
                    "component_stack": (report.componentStack or "")[:500],
                    "frontend_session_id": report.frontend_session_id or "",
                },
            )
        )


# ── GET /error-events ────────────────────────────────────────────────────────


@router.get("/error-events", response_model=ErrorEventsResponse)
async def get_error_events(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    layer: Optional[str] = QueryParam(None),
    severity: Optional[str] = QueryParam(None),
    resolved: bool = QueryParam(False),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(50, ge=1, le=200),
):
    """List error events (paginated, filtered). Admin only."""
    from sqlalchemy import text

    from app.database.connection import AsyncSessionLocal
    from app.infrastructure.monitoring.models import ErrorLayer, ErrorSeverity

    valid_layers = {e.value for e in ErrorLayer}
    valid_severities = {e.value for e in ErrorSeverity}

    if layer and layer not in valid_layers:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid layer. Valid: {sorted(valid_layers)}",
        )
    if severity and severity not in valid_severities:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid severity. Valid: {sorted(valid_severities)}",
        )

    conditions: list[str] = []
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}

    if layer:
        conditions.append("layer::text = :layer")
        params["layer"] = layer
    if severity:
        conditions.append("severity::text = :severity")
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
                       count, first_seen, last_seen, trace_id, path,
                       metadata, resolved_at
                FROM error_events {where}
                ORDER BY last_seen DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        items = [
            ErrorEventOut(
                id=r.id,
                fingerprint=r.fingerprint,
                layer=r.layer,
                category=r.category,
                severity=r.severity,
                message=r.message,
                count=r._mapping["count"],
                first_seen=r.first_seen.isoformat(),
                last_seen=r.last_seen.isoformat(),
                trace_id=r.trace_id,
                path=r.path,
                metadata=r.metadata or {},
                resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
            )
            for r in rows
        ]

    return ErrorEventsResponse(items=items, total=total, page=page, page_size=page_size)


# ── GET /error-stats ──────────────────────────────────────────────────────────


async def _get_error_stats() -> list[ErrorStatsRow]:
    from sqlalchemy import text

    from app.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            text("""
            SELECT hour, layer, severity, event_count
            FROM error_hourly_stats
            ORDER BY hour DESC, layer, severity
            LIMIT 1000
        """)
        )
        return [
            ErrorStatsRow(
                hour=r.hour.isoformat(),
                layer=r.layer,
                severity=r.severity,
                event_count=r.event_count,
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


# ── GET /silent-fallbacks ────────────────────────────────────────────────────


@router.get("/silent-fallbacks")
async def get_silent_fallbacks(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
) -> dict:
    """Aggregated silent-degradation counters by reason. Admin only.

    Surfaces fallback paths that succeed with reduced fidelity (NULL fuel
    prediction on estimator timeout, physics-only estimate when Open-Meteo
    elevation fails, ...). Alarm on a rising ``total`` / per-reason count.
    """
    from app.infrastructure.monitoring.silent_fallback_probe import (
        get_silent_fallback_probe,
    )

    return get_silent_fallback_probe().get_stats()


# ── POST /error-events/{event_id}/resolve ────────────────────────────────────


@router.post("/error-events/{event_id}/resolve", status_code=204)
async def resolve_error_event(
    event_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Mark an error event as resolved. Admin only."""
    from sqlalchemy import text

    from app.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                UPDATE error_events
                SET resolved_at = :now, resolved_by = :user_id
                WHERE id = :event_id AND resolved_at IS NULL
            """),
            {
                "now": datetime.now(timezone.utc),
                "user_id": current_user.id,
                "event_id": event_id,
            },
        )
        if cast("Any", result).rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Event not found or already resolved",
            )
        await session.commit()


# ── GET /debug/trace/{trace_id} ───────────────────────────────────────────
# Bir trace_id'ye ait tüm error_events + audit_log zincirini tek yerde
# döner. Debugging playbook'un kalbi: pain'i "log dosyasında grep"ten
# "API çağrısına" indirir.


@router.get("/debug/trace/{trace_id}")
async def get_trace_chain(
    trace_id: str,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """trace_id'ye ait tüm event zincirini döner (debugging için).

    Birleşik döküm:
      - error_events: layer/category/severity/message/stack_trace
      - audit_log:    action/entity/duration/status
      - request log:  path/status_code (logging_middleware'den)

    Frontend bunu admin paneline koyunca, yakalanan trace_id'yi tek
    tıkla detay gösterir → hata kovalama dakikalardan saniyelere iner.
    """
    from sqlalchemy import text

    from app.database.connection import AsyncSessionLocal

    chain: dict[str, Any] = {"errors": [], "audit": []}

    async with AsyncSessionLocal() as session:
        # error_events
        err_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT id, layer, category, severity, message,
                           stack_trace, path, count,
                           first_seen, last_seen, resolved_at
                    FROM error_events
                    WHERE trace_id = :trace_id
                    ORDER BY first_seen ASC
                    """
                    ),
                    {"trace_id": trace_id},
                )
            )
            .mappings()
            .all()
        )
        chain["errors"] = [dict(r) for r in err_rows]

        # admin_audit_log — Türkçe kolon isimleri, istek_id = trace_id
        try:
            audit_rows = (
                (
                    await session.execute(
                        text(
                            """
                        SELECT id,
                               aksiyon_tipi    AS action,
                               hedef_tablo     AS entity,
                               hedef_id        AS entity_id,
                               kullanici_id    AS user_id,
                               yeni_deger      AS new_value,
                               CASE WHEN basarili THEN 'success'
                                    ELSE 'failure' END AS status,
                               sure_ms         AS duration_ms,
                               zaman           AS created_at
                        FROM admin_audit_log
                        WHERE istek_id = :trace_id
                        ORDER BY zaman ASC
                        LIMIT 100
                        """
                        ),
                        {"trace_id": trace_id},
                    )
                )
                .mappings()
                .all()
            )
            chain["audit"] = [dict(r) for r in audit_rows]
        except Exception as exc:  # pragma: no cover
            logger.debug("Audit chain skipped for trace %s: %s", trace_id, exc)

    chain["trace_id"] = trace_id
    chain["counts"] = {
        "errors": len(chain["errors"]),
        "audit": len(chain["audit"]),
    }
    if not chain["errors"] and not chain["audit"]:
        # Aramayı kolaylaştırmak için make trace komutunu öner
        chain["hint"] = (
            "Hiç kayıt bulunamadı. Container log'larında trace_id'yi arayın: "
            f"docker compose logs backend worker celery-beat | grep '{trace_id}' "
            "veya: make trace TRACE={trace_id}"
        ).format(trace_id=trace_id)
    return chain
