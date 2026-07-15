"""Use-case: koçluk mesajlarının etki özeti (A.5).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/coaching_routes.py::get_coaching_effectiveness``
daha önce raw SQL agregasyonunu route içinde doğrudan çalıştırıyordu.
Mekanik taşıma, davranış değişikliği yok.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import text

from app.database.unit_of_work import UnitOfWork


async def get_coaching_effectiveness_stats(days: int) -> Dict[str, Any]:
    """Son N günde gönderilen koçluk mesajlarının etki özeti (ham satır)."""
    days = max(7, min(180, int(days)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            COUNT(*)                                                       AS total_sent,
            COUNT(*) FILTER (WHERE evaluated_at IS NOT NULL)                AS total_evaluated,
            COUNT(*) FILTER (WHERE score_delta_pct IS NOT NULL
                                 AND score_delta_pct > 0)                   AS improved,
            COUNT(*) FILTER (WHERE score_delta_pct IS NOT NULL
                                 AND score_delta_pct < 0)                   AS worsened,
            AVG(score_delta_pct) FILTER (WHERE evaluated_at IS NOT NULL)    AS avg_delta
        FROM coaching_deliveries
        WHERE sent_at >= :cutoff
        """
    )
    async with UnitOfWork() as uow:
        row = (await uow.session.execute(stmt, {"cutoff": cutoff})).mappings().one()

    return {
        "window_days": days,
        "total_sent": int(row["total_sent"] or 0),
        "total_evaluated": int(row["total_evaluated"] or 0),
        "improved": int(row["improved"] or 0),
        "worsened": int(row["worsened"] or 0),
        "avg_delta": row["avg_delta"],
    }
