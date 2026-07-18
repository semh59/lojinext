"""
LojiNext AI - Gelişmiş Raporlama API Endpoint'leri
PDF raporlar ve maliyet analizi
"""

import asyncio
import io
from datetime import date, datetime, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.api.deps import SessionDep, get_current_active_admin
from app.api.v1.utils import parse_date_param
from app.core.exceptions import DomainError
from app.database.models import Kullanici
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.schemas.api_responses import (
    EXCEL_XLSX_RESPONSES,
    PDF_RESPONSES,
    CostTrendPoint,
    VehicleCostComparisonItem,
)
from v2.modules.analytics_executive.public import (
    calculate_period_cost,
    calculate_roi,
    calculate_savings_potential,
    get_monthly_trend,
)
from v2.modules.analytics_executive.public import (
    get_vehicle_cost_comparison as analyze_vehicle_cost_comparison,
)
from v2.modules.import_excel.public import export_data, get_export_service
from v2.modules.reports.application.generate_fleet_summary import generate_fleet_summary
from v2.modules.reports.application.generate_vehicle_report import (
    generate_vehicle_report,
)
from v2.modules.reports.infrastructure.pdf_export import get_report_generator
from v2.modules.reports.infrastructure.repo_access import resolve_repos

logger = get_logger(__name__)


router = APIRouter()


class CostBreakdownResponse(BaseModel):
    fuel_cost: float
    fuel_liters: float
    avg_price_per_liter: float
    trip_count: int
    total_distance: float
    cost_per_km: float
    period_start: str
    period_end: str


class SavingsPotentialResponse(BaseModel):
    current_consumption: float
    target_consumption: float
    current_cost: float
    target_cost: float
    potential_savings: float
    savings_percentage: float
    annual_projection: float


class ROIResponse(BaseModel):
    investment: float
    monthly_savings: float
    annual_savings: float
    payback_months: float
    annual_roi_percentage: float
    cost_improvement_pct: float


@router.get(
    "/pdf/fleet-summary",
    responses=PDF_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_fleet_summary_pdf(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Filo özet raporu PDF olarak indir

    Args:
        start_date: Başlangıç tarihi (YYYY-MM-DD)
        end_date: Bitiş tarihi (YYYY-MM-DD)
    """
    try:
        start = parse_date_param(start_date, "start_date") or (
            date.today() - timedelta(days=30)
        )
        end = parse_date_param(end_date, "end_date") or date.today()

        # Rapor verileri (async) — session-scoped repos to avoid sessionless repo crash
        async with UnitOfWork(session=db) as uow:
            data = await generate_fleet_summary(resolve_repos(uow), start, end)

        # PDF oluştur (Bloklayıcı işlemi thread'e taşı)
        generator = get_report_generator()
        pdf_bytes = await asyncio.to_thread(
            generator.generate_fleet_summary, start, end, data
        )

        # Response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=filo_ozet_{start}_{end}.pdf"
            },
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fleet summary PDF export error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Rapor oluşturulurken bir hata oluştu"
        )


@router.get(
    "/pdf/vehicle/{arac_id}",
    responses=PDF_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_vehicle_report_pdf(
    arac_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
):
    """
    Araç detay raporu PDF olarak indir

    Args:
        arac_id: Araç ID
        month: Ay (1-12)
        year: Yıl (2020-2100)
    """
    try:
        # Rapor verileri (async)
        async with UnitOfWork(session=db) as uow:
            data = await generate_vehicle_report(
                resolve_repos(uow), arac_id, month, year
            )

        if not data or "error" in data:
            raise HTTPException(status_code=404, detail="Araç bulunamadı")

        # PDF oluştur (Bloklayıcı işlemi thread'e taşı)
        generator = get_report_generator()
        pdf_bytes = await asyncio.to_thread(
            generator.generate_vehicle_report, arac_id, month, year, data
        )

        plaka = data.get("plaka", f"arac_{arac_id}")
        # Sanitize filename (Header Injection Protection)
        safe_plaka = "".join(c for c in plaka if c.isalnum() or c in ("-", "_")).strip()
        filename = f"{safe_plaka}_{month:02d}_{year}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Vehicle report PDF export error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Rapor oluşturulurken bir hata oluştu"
        )


@router.get(
    "/pdf/driver-comparison",
    responses=PDF_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_driver_comparison_pdf(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Şoför performans karşılaştırma raporu PDF"""
    try:
        from v2.modules.driver.public import get_driver_stats

        async with UnitOfWork() as uow:
            drivers = await get_driver_stats(uow=uow)

        driver_data = [
            {
                "ad_soyad": d.ad_soyad or "—",
                "trips": d.toplam_sefer or 0,
                "consumption": float(d.ort_tuketim or 0.0),
                "score": float(d.performans_puani or 0.0),
            }
            for d in drivers
        ]

        generator = get_report_generator()
        pdf_bytes = await asyncio.to_thread(
            generator.generate_driver_comparison, driver_data
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=sofor-karsilastirma.pdf"
            },
        )
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Driver comparison PDF error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="PDF oluşturulamadı.")


@router.get(
    "/pdf/vehicle-comparison",
    responses=PDF_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_vehicle_comparison_pdf(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    months: int = Query(3, ge=1, le=12),
):
    """Araç maliyet karşılaştırma raporu PDF"""
    try:
        vehicles = await analyze_vehicle_cost_comparison(months)

        generator = get_report_generator()
        pdf_bytes = await asyncio.to_thread(
            generator.generate_vehicle_comparison, vehicles
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=arac-karsilastirma.pdf"
            },
        )
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Vehicle comparison PDF error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="PDF oluşturulamadı.")


@router.get("/cost/period", response_model=CostBreakdownResponse)
async def get_period_cost(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    start_date: str = Query(...),
    end_date: str = Query(...),
    arac_id: Optional[int] = Query(None),
):
    """
    Dönemsel maliyet analizi
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın."
        )

    breakdown = await calculate_period_cost(start, end, arac_id)

    return CostBreakdownResponse(
        fuel_cost=float(breakdown.fuel_cost),
        fuel_liters=breakdown.fuel_liters,
        avg_price_per_liter=float(breakdown.avg_price_per_liter),
        trip_count=breakdown.trip_count,
        total_distance=breakdown.total_distance,
        cost_per_km=float(breakdown.cost_per_km),
        period_start=breakdown.period_start.isoformat(),
        period_end=breakdown.period_end.isoformat(),
    )


@router.get("/cost/trend", response_model=List[CostTrendPoint])
async def get_cost_trend(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    months: int = Query(12, ge=1, le=24),
):
    """
    Aylık maliyet trendi
    """
    return await get_monthly_trend(months)


@router.get("/cost/vehicle-comparison", response_model=List[VehicleCostComparisonItem])
async def get_vehicle_cost_comparison(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    months: int = Query(3, ge=1, le=12),
):
    """
    Araç bazlı maliyet karşılaştırması
    """
    return await analyze_vehicle_cost_comparison(months)


@router.get("/cost/savings-potential", response_model=SavingsPotentialResponse)
async def get_savings_potential(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    target_consumption: float = Query(30.0, ge=20, le=45),
):
    """
    Tasarruf potansiyeli hesaplama
    """
    result = await calculate_savings_potential(target_consumption)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    return SavingsPotentialResponse(**result)


@router.get("/cost/roi", response_model=ROIResponse)
async def get_roi_analysis(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    investment: float = Query(50000, ge=0),
    months: int = Query(12, ge=3, le=24),
    target_consumption: float = Query(30.0, ge=20, le=45),
):
    """
    Sistem ROI analizi
    """
    result = await calculate_roi(investment, months, target_consumption)

    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    return ROIResponse(**result)


@router.get(
    "/excel/template/{entity_type}",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def get_excel_template(
    entity_type: str,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """
    Excel yükleme şablonu indir

    Args:
        entity_type: yakit, sefer, arac, sofor
    """
    export_service = get_export_service()
    filepath = await export_service.generate_template(entity_type)

    if not filepath:
        raise HTTPException(status_code=404, detail="Şablon oluşturulamadı")

    import os

    filename = os.path.basename(filepath)

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get(
    "/excel/export",
    responses=EXCEL_XLSX_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def export_analytical_report_excel(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    report_type: str = Query(
        ...,
        description="fleet_summary, driver_comparison, cost_trend, vehicle_comparison",
    ),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
):
    """
    Analitik raporları Excel formatında dışa aktarır.
    """
    try:
        data = []
        filename = f"rapor_{report_type}_{date.today()}.xlsx"

        if report_type == "fleet_summary":
            start = parse_date_param(start_date, "start_date") or (
                date.today() - timedelta(days=30)
            )
            end = parse_date_param(end_date, "end_date") or date.today()

            async with UnitOfWork(session=db) as uow:
                raw_data = await generate_fleet_summary(resolve_repos(uow), start, end)
            # Flatten or format raw_data for Excel
            data = [raw_data] if isinstance(raw_data, dict) else raw_data

        elif report_type == "driver_comparison":
            from v2.modules.driver.public import get_driver_stats

            # get_driver_stats()'in uow'suz singleton fallback'i raw-SQL
            # metotlarında session-less crash veriyordu (aynı dosyadaki
            # get_driver_comparison_pdf zaten uow ile doğru çağırıyordu —
            # 2026-07-16 dedektif denetiminde bulunan pre-existing bug,
            # taşımadan önce de vardı).
            async with UnitOfWork() as uow:
                drivers = await get_driver_stats(uow=uow)
            data = [
                {
                    "Şoför": d.ad_soyad,
                    "Toplam Sefer": d.toplam_sefer,
                    "Ort. Tüketim": d.ort_tuketim,
                    "Performans Puanı": d.performans_puani,
                }
                for d in drivers
            ]

        elif report_type == "cost_trend":
            trend = await get_monthly_trend(months)
            data = trend if isinstance(trend, list) else [trend]

        elif report_type == "vehicle_comparison":
            vehicles = await analyze_vehicle_cost_comparison(months)
            data = [
                {
                    "Plaka": v.get("plaka"),
                    "Toplam Mesafe (km)": v.get("total_distance"),
                    "Yakıt Maliyeti (TL)": v.get("fuel_cost"),
                    "km Başı Maliyet (TL)": v.get("cost_per_km"),
                    "Ort. Tüketim (L/100km)": v.get("avg_consumption"),
                }
                for v in vehicles
            ]

        else:
            raise HTTPException(status_code=400, detail="Geçersiz rapor tipi")

        if not data:
            raise HTTPException(status_code=404, detail="Rapor verisi bulunamadı")

        # Excel oluştur
        content = await export_data(data, type=f"{report_type}_analiz")

        import urllib.parse

        encoded_filename = urllib.parse.quote(filename)

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Analytical Excel export error: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Rapor dışa aktarılırken bir hata oluştu"
        )
