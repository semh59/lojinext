"""Use-case: FVI için gerekli tüm aggregat'ları DB'den topla (E.1)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict


async def gather_fvi_inputs(uow, *, days_back: int = 30) -> Dict[str, Any]:
    """Endeks için gerekli tüm aggregat'ları tek round-trip'te DB'den çek.

    Nested UoW açmaz; çağıran UoW'yu paylaşır.
    """
    from sqlalchemy import text

    cutoff = date.today() - timedelta(days=days_back)
    sql = """
        WITH active_arac AS (
            SELECT id, hedef_tuketim FROM araclar
            WHERE aktif = TRUE AND is_deleted = FALSE
        ),
        fuel AS (
            SELECT AVG(
                CASE WHEN s.mesafe_km > 0
                     THEN s.tuketim * 100 / s.mesafe_km END
            ) AS avg_l_100km
            FROM seferler s
            WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
              AND s.tarih >= :cutoff
        ),
        driver_avg AS (
            SELECT AVG(score) AS avg_score FROM soforler
            WHERE aktif = TRUE AND is_deleted = FALSE
        ),
        anomaly_30d AS (
            SELECT
                COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) AS resolved,
                COUNT(*) FILTER (
                    WHERE acknowledged_at IS NOT NULL
                      AND resolved_at IS NULL
                ) AS acked,
                COUNT(*) AS total
            FROM anomalies WHERE tarih >= :cutoff
        ),
        overdue AS (
            SELECT COUNT(*) AS cnt FROM araclar a
            WHERE a.aktif = TRUE AND a.is_deleted = FALSE
              AND NOT EXISTS (
                  SELECT 1 FROM arac_bakimlari b
                  WHERE b.arac_id = a.id AND b.tamamlandi = TRUE
                    AND b.bakim_tipi = 'PERIYODIK'
                    AND b.bakim_tarihi >= CURRENT_DATE - INTERVAL '365 days'
              )
        )
        SELECT
            (SELECT AVG(hedef_tuketim) FROM active_arac) AS target,
            (SELECT COUNT(*) FROM active_arac) AS total_active,
            (SELECT avg_l_100km FROM fuel) AS fuel_avg,
            (SELECT avg_score FROM driver_avg) AS driver_avg,
            (SELECT resolved FROM anomaly_30d) AS resolved,
            (SELECT acked FROM anomaly_30d) AS acked,
            (SELECT total FROM anomaly_30d) AS total_anomalies,
            (SELECT cnt FROM overdue) AS overdue_count
    """
    row = (await uow.session.execute(text(sql), {"cutoff": cutoff})).mappings().one()
    return dict(row)
