"""error_events / error_hourly_stats / admin_audit_log sorgu ve yönetim use-case'leri.

Dalga 15 admin_platform denetiminde bulundu: bu mantık eskiden
``app/api/v1/endpoints/system.py``'de route handler'ların İÇİNDE, doğrudan
raw SQL olarak yaşıyordu ("route layer bypasses application" bug sınıfı,
kök CLAUDE.md'de dokümante). Route'lar artık yalnızca bu fonksiyonları
çağırıp Pydantic response modeline sarıyor.

Tablo sahipliği notu: ``error_events``/``error_occurrences``/
``error_hourly_stats``'ın YAZIM yolu ``app/infrastructure/monitoring/``'de
yaşıyor (audit_logger.py/event_bus.py gibi cross-cutting altyapı — hiçbir
v2 modülüne ait değil, tüm modüllerin hata event'lerini toplar). Bu dosya
yalnızca admin-facing OKUMA/YÖNETİM katmanını sağlar (liste, istatistik,
resolve, trace-chain) — admin_platform'un sahipliği veri YAZIMI değil, bu
sorgu/yönetim yüzeyidir.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import text

from app.infrastructure.logging.logger import get_logger
from v2.modules.platform_infra.database.connection import AsyncSessionLocal

logger = get_logger(__name__)


async def list_error_events(
    *,
    layer: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Dict[str, Any]], int]:
    """Paginated/filtered error_events listesi. Returns (items, total)."""
    from app.infrastructure.monitoring.models import ErrorLayer, ErrorSeverity

    valid_layers = {e.value for e in ErrorLayer}
    valid_severities = {e.value for e in ErrorSeverity}

    if layer and layer not in valid_layers:
        raise ValueError(f"Invalid layer. Valid: {sorted(valid_layers)}")
    if severity and severity not in valid_severities:
        raise ValueError(f"Invalid severity. Valid: {sorted(valid_severities)}")

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
            {
                "id": r.id,
                "fingerprint": r.fingerprint,
                "layer": r.layer,
                "category": r.category,
                "severity": r.severity,
                "message": r.message,
                "count": r._mapping["count"],
                "first_seen": r.first_seen.isoformat(),
                "last_seen": r.last_seen.isoformat(),
                "trace_id": r.trace_id,
                "path": r.path,
                "metadata": r.metadata or {},
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in rows
        ]

    return items, total


async def get_error_stats() -> List[Dict[str, Any]]:
    """Hourly aggregated error stats (materialized view)."""
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
            {
                "hour": r.hour.isoformat(),
                "layer": r.layer,
                "severity": r.severity,
                "event_count": r.event_count,
            }
            for r in rows
        ]


async def resolve_error_event(event_id: int, user_id: Optional[int]) -> bool:
    """Error event'i resolved olarak işaretle. False → bulunamadı/zaten resolved."""
    async with AsyncSessionLocal() as session:
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


async def get_trace_chain(trace_id: str) -> Dict[str, Any]:
    """trace_id'ye ait tüm error_events + admin_audit_log zincirini döner."""
    chain: Dict[str, Any] = {"errors": [], "audit": []}

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
        chain["hint"] = (
            "Hiç kayıt bulunamadı. Container log'larında trace_id'yi arayın: "
            f"docker compose logs backend worker celery-beat | grep '{trace_id}' "
            "veya: make trace TRACE={trace_id}"
        ).format(trace_id=trace_id)
    return chain
