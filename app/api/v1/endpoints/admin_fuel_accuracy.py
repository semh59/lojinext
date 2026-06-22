"""Admin fuel-accuracy dashboard (Phase 5.3).

Pilot kalibrasyon süreci için MAPE/RMSE özet endpoint'i.

SeferFuelEstimator (Phase 4) üretime alındıktan sonra, gerçek sefer
tüketimi DB'ye girildikçe bu endpoint **tahmin vs gerçek** sapmasını
ölçer. 4 hafta veri sonra kalibrasyon kararı için baseline.

MAPE = mean(abs(actual - predicted) / actual) × 100
RMSE = sqrt(mean((actual - predicted)²))

Tam seferleri (durum=Tamamlandı + tuketim NOT NULL) filtreler.
"""

from datetime import date, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, get_current_active_admin
from app.database.models import Kullanici

router = APIRouter()


class FuelAccuracyStats(BaseModel):
    period_days: int
    sample_size: int  # Tamamlanmış + tuketim girili sefer sayısı
    mape_pct: Optional[float] = None  # %, None if sample yok
    rmse_l_100km: Optional[float] = None  # L/100km
    mean_predicted: Optional[float] = None
    mean_actual: Optional[float] = None
    bias_pct: Optional[float] = None  # tahmin - gerçek (yüzde)
    coverage_pct: float = 0.0  # tahmin yapılmış sefer / tüm sefer
    breakdown_by_arac: list = Field(default_factory=list)


@router.get(
    "/fuel-accuracy",
    response_model=FuelAccuracyStats,
    dependencies=[Depends(get_current_active_admin)],
)
async def get_fuel_accuracy(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
    days: int = Query(30, ge=1, le=365, description="Geçmiş gün sayısı"),
    arac_id: Optional[int] = Query(None, description="Tek araç filtresi"),
    sofor_id: Optional[int] = Query(None, description="Tek sürücü filtresi"),
) -> FuelAccuracyStats:
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
    params: dict = {"cutoff": cutoff}

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

    return FuelAccuracyStats(
        period_days=days,
        sample_size=sample_size,
        mape_pct=(
            round(float(row["mape_pct"]), 2)
            if row and row["mape_pct"] is not None
            else None
        ),
        rmse_l_100km=(
            round(float(row["rmse"]), 2) if row and row["rmse"] is not None else None
        ),
        mean_predicted=(
            round(float(row["mean_predicted"]), 2)
            if row and row["mean_predicted"] is not None
            else None
        ),
        mean_actual=(
            round(float(row["mean_actual"]), 2)
            if row and row["mean_actual"] is not None
            else None
        ),
        bias_pct=(
            round(float(row["bias_pct"]), 2)
            if row and row["bias_pct"] is not None
            else None
        ),
        coverage_pct=round(coverage, 1),
        breakdown_by_arac=[
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
    )
