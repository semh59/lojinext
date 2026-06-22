from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from app.api.deps import SessionDep, get_current_active_user
from app.core.exceptions import DomainError
from app.database.models import Kullanici, YakitAlimi
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


router = APIRouter()


# ── Response Models ──────────────────────────────────────────────────────────


class DashboardTrends(BaseModel):
    """Aylık değişim oranları (%)."""

    sefer: float = Field(0, description="Sefer sayısı değişim %")
    km: float = Field(0, description="Toplam km değişim %")
    tuketim: float = Field(0, description="Ortalama tüketim değişim %")


class DashboardStatsResponse(BaseModel):
    """Dashboard ana istatistikleri."""

    toplam_sefer: int = 0
    toplam_km: float = 0
    toplam_yakit: float = 0
    filo_ortalama: float = 32.0
    aktif_arac: int = 0
    toplam_arac: int = 0
    aktif_sofor: int = 0
    bugun_sefer: int = 0
    trends: DashboardTrends = Field(default_factory=DashboardTrends)  # type: ignore[arg-type]


class ConsumptionTrendItem(BaseModel):
    """Aylık tüketim veri noktası."""

    month: str = Field(..., description="YYYY-MM formatında ay")
    consumption: float = Field(..., description="Toplam litre tüketim")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    Dashboard istatistiklerini getir.
    ReportService üzerinden çekilir.
    """
    from datetime import datetime, timezone

    from app.core.services.report_service import ReportService

    service = ReportService(session=db)
    today_utc = datetime.now(timezone.utc).date()

    try:
        async with UnitOfWork(session=db) as uow:
            # Tek bir DB session paylaşıldığı için sıralı await; aksi halde
            # SQLAlchemy "concurrent operations" hatası verir.
            data = await service.generate_fleet_summary(
                start_date=today_utc.replace(day=1)
            )
            aktif_arac = await uow.arac_repo.count_active()
            aktif_sofor = await uow.sofor_repo.count_active()
            bugun_sefer = await uow.sefer_repo.count_today(today_utc)
            trends = await uow.analiz_repo.get_month_over_month_trends(today_utc)
        return DashboardStatsResponse(
            toplam_sefer=data.get("total_trips", 0),
            toplam_km=data.get("total_distance", 0.0),
            toplam_yakit=data.get("total_fuel", 0.0),
            filo_ortalama=data.get("avg_consumption", 32.0),
            toplam_arac=data.get("total_vehicles", 0),
            aktif_arac=aktif_arac,
            aktif_sofor=aktif_sofor,
            bugun_sefer=bugun_sefer,
            trends=DashboardTrends(**trends),
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Dashboard verileri alınamadı. Lütfen daha sonra tekrar deneyin.",
        )


@router.get("/consumption-trend", response_model=List[ConsumptionTrendItem])
async def get_consumption_trend(
    db: SessionDep, current_user: Annotated[Kullanici, Depends(get_current_active_user)]
):
    """
    Son 6 ayın aylık toplam yakıt tüketim trendi (kronolojik sırada).
    """
    month_col = func.to_char(YakitAlimi.tarih, "YYYY-MM")

    # Subquery: son 6 ayı DESC ile seç, dış sorgu ile ASC'ye çevir
    subq = (
        select(
            month_col.label("month"),
            func.sum(YakitAlimi.litre).label("consumption"),
        )
        .group_by(month_col)
        .order_by(desc(month_col))
        .limit(6)
    ).subquery()

    stmt = select(subq.c.month, subq.c.consumption).order_by(subq.c.month)

    result = await db.execute(stmt)
    return [
        {"month": row.month, "consumption": float(row.consumption)}
        for row in result.all()
    ]
