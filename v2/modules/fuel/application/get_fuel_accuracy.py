"""Use-case: MAPE/RMSE tahmin doğruluğu ölçümü (admin ops).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/fuel_routes.py::get_fuel_accuracy`` `application/`
katmanını atlayıp doğrudan ``db.execute(text(...))`` çalıştırıyordu. Mekanik
taşıma, davranış değişikliği yok.
"""

from datetime import date, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_fuel_accuracy_stats(
    db: AsyncSession,
    days: int,
    arac_id: Optional[int] = None,
    sofor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """MAPE/RMSE — tahmin doğruluğu ölçümü.

    Tamamlanmış sefer'ler için tahmin (tahmini_tuketim) ile gerçek
    (tuketim) karşılaştırması. Sefer durum=Tamamlandı + tuketim NOT NULL.
    """
    cutoff = date.today() - timedelta(days=days)

    base_where = """
        WHERE durum = 'Completed'
          AND is_deleted = FALSE
          AND tarih >= :cutoff
          AND tuketim IS NOT NULL
          AND tuketim > 0
    """
    params: Dict[str, Any] = {"cutoff": cutoff}

    if arac_id is not None:
        base_where += " AND arac_id = :arac_id"
        params["arac_id"] = arac_id
    if sofor_id is not None:
        base_where += " AND sofor_id = :sofor_id"
        params["sofor_id"] = sofor_id

    # Aggregate metrics
    agg_sql = text(f"""
        WITH paired AS (
            SELECT
                tahmini_tuketim AS predicted,
                tuketim AS actual,
                mesafe_km
            FROM seferler
            {base_where}
              AND tahmini_tuketim IS NOT NULL
              AND tahmini_tuketim > 0
              AND mesafe_km > 0
        ),
        all_completed AS (
            SELECT COUNT(*) AS total
            FROM seferler
            {base_where}
        )
        SELECT
            (SELECT COUNT(*) FROM paired) AS sample_size,
            (SELECT total FROM all_completed) AS total_completed,
            AVG(ABS(actual - predicted) / actual * 100.0) AS mape_pct,
            SQRT(AVG(POWER(actual - predicted, 2))) AS rmse,
            AVG(predicted) AS mean_predicted,
            AVG(actual) AS mean_actual,
            AVG((predicted - actual) / actual * 100.0) AS bias_pct
        FROM paired
    """)
    row = (await db.execute(agg_sql, params)).mappings().one_or_none()

    sample_size = int(row["sample_size"] or 0) if row else 0
    total_completed = int(row["total_completed"] or 0) if row else 0
    coverage = (sample_size / total_completed * 100.0) if total_completed else 0.0

    # Per-arac breakdown (top 10 by sample size)
    arac_sql = text(f"""
        WITH paired AS (
            SELECT
                arac_id,
                tahmini_tuketim AS predicted,
                tuketim AS actual
            FROM seferler
            {base_where}
              AND tahmini_tuketim IS NOT NULL
              AND tahmini_tuketim > 0
        )
        SELECT
            arac_id,
            COUNT(*) AS samples,
            AVG(ABS(actual - predicted) / actual * 100.0) AS mape_pct,
            AVG((predicted - actual) / actual * 100.0) AS bias_pct
        FROM paired
        GROUP BY arac_id
        ORDER BY samples DESC
        LIMIT 10
    """)
    arac_rows = (await db.execute(arac_sql, params)).mappings().all()

    return {
        "period_days": days,
        "sample_size": sample_size,
        "mape_pct": (
            round(float(row["mape_pct"]), 2)
            if row and row["mape_pct"] is not None
            else None
        ),
        "rmse_l_100km": (
            round(float(row["rmse"]), 2) if row and row["rmse"] is not None else None
        ),
        "mean_predicted": (
            round(float(row["mean_predicted"]), 2)
            if row and row["mean_predicted"] is not None
            else None
        ),
        "mean_actual": (
            round(float(row["mean_actual"]), 2)
            if row and row["mean_actual"] is not None
            else None
        ),
        "bias_pct": (
            round(float(row["bias_pct"]), 2)
            if row and row["bias_pct"] is not None
            else None
        ),
        "coverage_pct": round(coverage, 1),
        "breakdown_by_arac": [
            {
                "arac_id": int(r["arac_id"]),
                "samples": int(r["samples"]),
                "mape_pct": round(float(r["mape_pct"]), 2)
                if r["mape_pct"] is not None
                else None,
                "bias_pct": round(float(r["bias_pct"]), 2)
                if r["bias_pct"] is not None
                else None,
            }
            for r in arac_rows
        ],
    }
