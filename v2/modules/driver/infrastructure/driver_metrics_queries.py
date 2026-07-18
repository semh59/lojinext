"""Bulk driver metric queries (dalga 11 — analytics_executive'ten taşındı).

``get_bulk_driver_metrics`` eskiden
``app/database/repositories/analiz_repo.py``'nin (``AnalizRepository``)
parçasıydı; driver dalgası (5) bunları taşımayı atlamıştı (analytics_executive
CLAUDE.md'de "henüz taşınmadı" olarak dokümante edilmişti). Serbest fonksiyon
(B.1) — repo sınıfına eklenmedi çünkü ikisi de tek-tablo CRUD değil,
çapraz-tablo (seferler+soforler) salt-okunur agregat sorgu.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database.unit_of_work import UnitOfWork


async def get_bulk_driver_metrics(
    uow: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Tüm şoförler için puanlama metriklerini TEK BİR sorgu ile getirir."""
    from app.infrastructure.security.pii_encryption import decrypt_pii_or

    today = date.today()
    son_15_gun = today - timedelta(days=15)
    son_30_gun = today - timedelta(days=30)

    query = text("""
        SELECT
            s.sofor_id,
            sf.ad_soyad,
            COUNT(s.id) as toplam_sefer,
            COALESCE(SUM(s.mesafe_km), 0) as toplam_km,
            COALESCE(SUM(s.net_kg), 0) / 1000.0 as toplam_ton,
            COALESCE(AVG(s.tuketim), 0) as ort_tuketim,
            COALESCE(MIN(NULLIF(s.tuketim, 0)), 0) as en_iyi_tuketim,
            COALESCE(MAX(NULLIF(s.tuketim, 0)), 0) as en_kotu_tuketim,
            COALESCE(STDDEV(s.tuketim), 0) as std_sapma,
            COUNT(DISTINCT (s.cikis_yeri || ' -> ' || s.varis_yeri)) as guzergah_sayisi,
            AVG(s.tuketim) FILTER (WHERE s.tarih >= :son_15_gun AND s.tuketim > 0) as recent_avg,
            AVG(s.tuketim) FILTER (WHERE s.tarih < :son_15_gun AND s.tarih >= :son_30_gun AND s.tuketim > 0) as older_avg
        FROM seferler s
        JOIN soforler sf ON s.sofor_id = sf.id
        WHERE s.is_deleted = False
        GROUP BY s.sofor_id, sf.ad_soyad
    """)  # noqa: E501

    async def _run(session) -> List[Dict[str, Any]]:
        result = await session.execute(
            query, {"son_15_gun": son_15_gun, "son_30_gun": son_30_gun}
        )
        rows = [dict(row._mapping) for row in result.fetchall()]
        for row in rows:
            row["ad_soyad"] = decrypt_pii_or(row.get("ad_soyad"))
        return rows

    session = getattr(uow, "session", None) if uow is not None else None
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


# 2026-07-18 ölü-kod temizliği: get_driver_comparison silindi — hiçbir prod
# endpoint çağırmıyordu (get_driver_comparison_pdf farklı bir yol,
# get_driver_stats kullanır). Docstring'i zaten ölü-kod olarak işaretliydi.
