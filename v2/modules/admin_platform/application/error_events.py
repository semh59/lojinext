"""error_events / error_hourly_stats / admin_audit_log query and management use-cases.

Found during the dalga 15 admin_platform audit: this logic used to live
directly as raw SQL INSIDE the route handlers in
``app/api/v1/endpoints/system.py`` ("route layer bypasses application" bug
class, documented in root CLAUDE.md). Routes now only call these functions
and wrap the result in a Pydantic response model.

Table ownership note: the WRITE path for ``error_events``/
``error_occurrences``/``error_hourly_stats`` lives in
``v2/modules/platform_infra/monitoring/`` (cross-cutting infra like
audit_logger.py/event_bus.py -- not owned by any v2 business module, it
collects error events from all of them). This file only provides the
admin-facing READ/management layer (list, stats, resolve, trace-chain) --
admin_platform owns this query/management surface, not the data WRITE path.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import String, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.public import ErrorEvent

logger = get_logger(__name__)


async def list_error_events(
    session: AsyncSession,
    *,
    layer: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Dict[str, Any]], int]:
    """Paginated/filtered error_events list. Returns (items, total).

    Takes the caller's own request-scoped session (UOWDep) instead of
    opening a bare ``AsyncSessionLocal()`` -- opening one directly here
    never explicitly commits/closes, which is harmless in production
    (a real per-call session closes on its own ``async with`` exit) but
    left the transaction dangling open in the test suite's shared-session
    fixture (``app/tests/conftest.py::db_session``'s ``NonClosingSession``),
    the same bug class fixed in ``reports/api/dashboard_routes.py`` (FAZ2
    Wave 2 reports pilot, 2026-07-29) -- a lingering open transaction
    carries its ``SET LOCAL ROLE`` into whatever HTTP call the shared test
    session handles next.
    """
    from v2.modules.platform_infra.public import (
        ErrorLayer,
        ErrorSeverity,
    )

    valid_layers = {e.value for e in ErrorLayer}
    valid_severities = {e.value for e in ErrorSeverity}

    if layer and layer not in valid_layers:
        raise ValueError(f"Invalid layer. Valid: {sorted(valid_layers)}")
    if severity and severity not in valid_severities:
        raise ValueError(f"Invalid severity. Valid: {sorted(valid_severities)}")

    # Cast to String rather than comparing the PG_ENUM column directly --
    # the enum's underlying Postgres type (`create_type=False`) is assumed
    # to already exist via a real migration, which the test suite's
    # Base.metadata.create_all()-only bootstrap never runs. Casting avoids
    # needing that type to exist for the bind parameter, matching the
    # `layer::text = :layer` cast the original raw-SQL version used.
    conditions = []
    if layer:
        conditions.append(ErrorEvent.layer.cast(String) == layer)
    if severity:
        conditions.append(ErrorEvent.severity.cast(String) == severity)
    if not resolved:
        conditions.append(ErrorEvent.resolved_at.is_(None))

    count_stmt = select(func.count()).select_from(ErrorEvent)
    list_stmt = select(ErrorEvent)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)
    list_stmt = (
        list_stmt.order_by(ErrorEvent.last_seen.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(list_stmt)).scalars().all()
    items = [
        {
            "id": r.id,
            "fingerprint": r.fingerprint,
            "layer": r.layer,
            "category": r.category,
            "severity": r.severity,
            "message": r.message,
            "count": r.count,
            "first_seen": r.first_seen.isoformat(),
            "last_seen": r.last_seen.isoformat(),
            "trace_id": r.trace_id,
            "path": r.path,
            "metadata": r.extra or {},
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in rows
    ]

    return items, total


async def get_error_stats(session: AsyncSession) -> List[Dict[str, Any]]:
    """Hourly aggregated error stats (materialized view)."""
    rows = await session.execute(
        text("""
        SELECT hour, layer, severity, event_count
        FROM error_hourly_stats
        ORDER BY hour DESC, layer, severity
        LIMIT 1000
    """)
    )
    return [
        {
            "hour": r.hour.isoformat(),
            "layer": r.layer,
            "severity": r.severity,
            "event_count": r.event_count,
        }
        for r in rows
    ]


async def resolve_error_event(
    session: AsyncSession, event_id: int, user_id: Optional[int]
) -> bool:
    """Mark an error event as resolved. False -> not found / already resolved."""
    result = await session.execute(
        text("""
            UPDATE error_events
            SET resolved_at = :now, resolved_by = :user_id
            WHERE id = :event_id AND resolved_at IS NULL
        """),
        {
            "now": datetime.now(timezone.utc),
            "user_id": user_id,
            "event_id": event_id,
        },
    )
    if cast("Any", result).rowcount == 0:
        return False
    await session.commit()
    return True


async def get_trace_chain(session: AsyncSession, trace_id: str) -> Dict[str, Any]:
    """Returns the full error_events + admin_audit_log chain for a trace_id."""
    chain: Dict[str, Any] = {"errors": [], "audit": []}

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

    # admin_audit_log -- Turkish column names, istek_id = trace_id
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
        chain["hint"] = (
            "Hiç kayıt bulunamadı. Container log'larında trace_id'yi arayın: "
            f"docker compose logs backend worker celery-beat | grep '{trace_id}' "
            "veya: make trace TRACE={trace_id}"
        ).format(trace_id=trace_id)
    return chain
