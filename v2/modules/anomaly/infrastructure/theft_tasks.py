"""Feature B.3 — Yakıt hırsızlığı offline pattern tarama.

`theft.daily_pattern_scan` task'ı her gün 03:00 UTC'de çalışır,
fuel_investigations tablosundan son 30 gün ≥3 occurrence olan
(sofor_id, arac_id) ikilisini logger'a basar. Frontend için
gerçek-zamanlı endpoint `GET /admin/investigations/patterns`
B.2'de mevcut; bu task sadece audit-trail için loglar.

theft_tasks 5-modül raw-SQL erişimi notu (FAZ1 dalga 8 taşıma görevi
TASKS/modules/anomaly.md madde 4/6): bu SQL fuel_investigations+anomalies
(bu modül) + seferler+soforler+araclar (trip/driver/fleet) tablolarına
doğrudan erişir — taşıma sonrası bu erişimler FAZ2'de trip/driver/fleet
şemalarına SELECT-only grant gerektirecek (STATUS.md'de not düşüldü).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import text

from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


# Endpoint ile aynı SQL — DRY için investigation_routes.py'dan import etmek
# circular yapacak; offline iş kritik değil, sorgu burada tekrarlanır.
_PATTERN_SCAN_SQL = """
    WITH inv_data AS (
        SELECT
            fi.suspicion_score,
            fi.created_at,
            COALESCE(sf.sofor_id, NULL) AS sofor_id,
            COALESCE(sf.arac_id, NULL) AS arac_id,
            COALESCE(s.ad_soyad, NULL) AS sofor_adi,
            COALESCE(v.plaka, NULL) AS plaka
        FROM fuel_investigations fi
        JOIN anomalies a ON fi.anomaly_id = a.id
        LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
        LEFT JOIN soforler s ON sf.sofor_id = s.id
        LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                            OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
        WHERE fi.created_at >= :cutoff
          AND fi.suspicion_score IS NOT NULL
    )
    SELECT
        sofor_id, sofor_adi, arac_id, plaka,
        COUNT(*)::int AS occurrence_count,
        AVG(suspicion_score)::float AS avg_suspicion_score,
        MAX(created_at) AS last_seen
    FROM inv_data
    WHERE sofor_id IS NOT NULL OR arac_id IS NOT NULL
    GROUP BY sofor_id, sofor_adi, arac_id, plaka
    HAVING COUNT(*) >= :min_count
    ORDER BY avg_suspicion_score DESC NULLS LAST
    LIMIT :limit
"""


async def _run_pattern_scan(
    days: int = 30, min_count: int = 3, limit: int = 100
) -> Dict[str, Any]:
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with UnitOfWork() as uow:
        rows = (
            (
                await uow.session.execute(
                    text(_PATTERN_SCAN_SQL),
                    {"cutoff": cutoff, "min_count": min_count, "limit": limit},
                )
            )
            .mappings()
            .all()
        )

    for r in rows:
        # Admin grup için logger.warning — Sentry/Loki gibi backend'ler için
        # arama yapılabilir bir tag (THEFT_PATTERN) ile basıyoruz.
        # KVKK: sadece ID'ler (PII değil); ad_soyad/plaka kapsam dışı.
        # Frontend isterse /admin/investigations endpoint'inden ID→isim çözer.
        logger.warning(
            "THEFT_PATTERN sofor_id=%s arac_id=%s count=%s avg_score=%.2f last_seen=%s",
            r.get("sofor_id"),
            r.get("arac_id"),
            r.get("occurrence_count"),
            float(r.get("avg_suspicion_score") or 0),
            r.get("last_seen"),
        )

    return {"patterns_found": len(rows), "window_days": days, "min_count": min_count}


@celery_app.task(
    bind=True,
    name="theft.daily_pattern_scan",
    max_retries=1,
    acks_late=True,
)
def daily_pattern_scan(self) -> Dict[str, Any]:  # noqa: ARG001
    """Her sabah 03:00 UTC — pattern logla."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_pattern_scan())
    except Exception as exc:
        logger.error("THEFT pattern scan failed: %s", exc, exc_info=True)
        return {"patterns_found": 0, "error": str(exc)}
    finally:
        loop.close()
