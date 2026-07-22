from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Query as QueryParam
from pydantic import BaseModel, Field

from app.api.deps import get_current_active_admin, get_current_active_user
from app.api.middleware.rate_limiter import limiter
from app.infrastructure.logging.logger import get_logger
from v2.modules.admin_platform.application.error_events import (
    get_error_stats as _get_error_stats,
)
from v2.modules.admin_platform.application.error_events import (
    get_trace_chain as _get_trace_chain,
)
from v2.modules.admin_platform.application.error_events import (
    list_error_events,
)
from v2.modules.admin_platform.application.error_events import (
    resolve_error_event as _resolve_error_event,
)
from v2.modules.admin_platform.schemas import TraceChainResponse
from v2.modules.auth_rbac.public import Kullanici

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
    from v2.modules.platform_infra.monitoring import aemit
    from v2.modules.platform_infra.monitoring.models import (
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
    from v2.modules.platform_infra.monitoring import aemit
    from v2.modules.platform_infra.monitoring.models import (
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
    try:
        items, total = await list_error_events(
            layer=layer,
            severity=severity,
            resolved=resolved,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return ErrorEventsResponse(
        items=[ErrorEventOut(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /error-stats ──────────────────────────────────────────────────────────


@router.get("/error-stats", response_model=ErrorStatsResponse)
async def get_error_stats(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Return hourly aggregated error stats from materialized view. Admin only."""
    stats = await _get_error_stats()
    return ErrorStatsResponse(stats=[ErrorStatsRow(**row) for row in stats])


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
    from v2.modules.platform_infra.monitoring.silent_fallback_probe import (
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
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    resolved = await _resolve_error_event(event_id, user_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail="Event not found or already resolved",
        )


# ── GET /debug/trace/{trace_id} ───────────────────────────────────────────
# Bir trace_id'ye ait tüm error_events + audit_log zincirini tek yerde
# döner. Debugging playbook'un kalbi: pain'i "log dosyasında grep"ten
# "API çağrısına" indirir.


@router.get("/debug/trace/{trace_id}", response_model=TraceChainResponse)
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
    return await _get_trace_chain(trace_id)
