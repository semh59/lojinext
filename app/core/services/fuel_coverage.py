"""Yakıt-tahmin coverage hesaplama yardımcısı (fuel-coverage ops alarmı, 2026-07-07).

``GET /admin/fuel-accuracy`` (``app/api/v1/endpoints/admin_fuel_accuracy.py``)
ve ``monitoring.fuel_coverage_check`` beat task'ı
(``app/workers/tasks/fuel_coverage_check.py``) aynı "tamamlanmış sefer
başına tahmin var mı" SQL çekirdeğini paylaşır: ``durum = 'Completed'``
+ ``is_deleted = FALSE`` + ``tuketim NOT NULL``/``> 0`` filtresiyle toplam
tamamlanmış sefer sayısı ile ``tahmini_tuketim`` (ve ``mesafe_km``) dolu
olan sefer sayısı.

Endpoint'in MAPE/RMSE/breakdown hesaplarına DOKUNULMADI — davranışı aynen
korumak için bu modül endpoint'i çağırmaz/değiştirmez, sadece coverage
sayaçlarını (aynı filtre semantiğiyle) izole bir yardımcıya çıkarır.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CoverageResult(NamedTuple):
    sample_size: int  # tahmini_tuketim dolu (+ mesafe_km > 0) sefer sayısı
    total_completed: int  # toplam tamamlanmış (tuketim dolu) sefer sayısı
    coverage_pct: float  # sample_size / total_completed * 100 (yüzde 1 ondalık)


async def compute_coverage(db: AsyncSession, days: int) -> CoverageResult:
    """Son ``days`` gündeki tamamlanmış seferler için tahmin coverage'ı.

    Filtre semantiği ``admin_fuel_accuracy.py``'deki ``base_where`` +
    "paired" CTE'siyle birebir aynıdır (durum='Completed', is_deleted=FALSE,
    tuketim NOT NULL/>0; sample ek olarak tahmini_tuketim NOT NULL/>0 VE
    mesafe_km > 0 ister).
    """
    cutoff = date.today() - timedelta(days=days)
    sql = text(
        """
        WITH completed AS (
            SELECT tahmini_tuketim, mesafe_km
            FROM seferler
            WHERE durum = 'Completed'
              AND is_deleted = FALSE
              AND tarih >= :cutoff
              AND tuketim IS NOT NULL
              AND tuketim > 0
        )
        SELECT
            COUNT(*) FILTER (
                WHERE tahmini_tuketim IS NOT NULL
                  AND tahmini_tuketim > 0
                  AND mesafe_km > 0
            ) AS sample_size,
            COUNT(*) AS total_completed
        FROM completed
        """
    )
    row = (await db.execute(sql, {"cutoff": cutoff})).mappings().one()
    sample_size = int(row["sample_size"] or 0)
    total_completed = int(row["total_completed"] or 0)
    coverage_pct = (
        round(sample_size / total_completed * 100.0, 1) if total_completed else 0.0
    )
    return CoverageResult(
        sample_size=sample_size,
        total_completed=total_completed,
        coverage_pct=coverage_pct,
    )
