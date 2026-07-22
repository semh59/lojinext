"""Sefer istatistik/maliyet analitiği route'ları.

Dalga 14 — ``app/api/v1/endpoints/trips.py``'den taşındı (task dosyası
madde 2'nin kararı). Veri mantığı ``seferler`` tablosunu sahiplenen
trip'te kalır — bu route'lar yalnız ``v2.modules.trip.public``'i çağıran
ince wrapper'lar (bkz. ``trip.public.get_trip_stats``/
``get_fuel_performance_analytics``/``reconcile_costs``). ``api.py``'de
hâlâ ``prefix="/trips"`` ile mount edilir — URL'ler DEĞİŞMEDİ.
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_sefer_service
from v2.modules.analytics_executive.schemas import FuelPerformanceAnalyticsResponse
from v2.modules.auth_rbac.public import (
    Kullanici,
    get_current_active_user,
    require_permissions,
)
from v2.modules.platform_infra.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
)
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.public import get_job_manager
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.trip.public import SeferService, SeferStatsResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("/stats", response_model=SeferStatsResponse)
async def get_trip_stats(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    durum: Optional[str] = Query(None, description="Filtrelemek istenen sefer durumu"),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    Sefer istatistiklerini sunar.
    Tarih filtresi varsa dinamik sorgu kosturur, yoksa materialized view kullanir.
    """
    try:
        start_date = date.fromisoformat(baslangic_tarih) if baslangic_tarih else None
        end_date = date.fromisoformat(bitis_tarih) if bitis_tarih else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Tarih formati gecersiz.")

    try:
        stats = await service.get_trip_stats(
            durum=durum,
            baslangic_tarih=start_date,
            bitis_tarih=end_date,
        )
        return SeferStatsResponse(**stats)
    except ValueError:
        raise HTTPException(status_code=422, detail="Gecersiz durum degeri.")
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sefer listesi alınırken hata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Liste alınırken hata oluştu",
        )


@router.get(
    "/analytics/fuel-performance", response_model=FuelPerformanceAnalyticsResponse
)
async def get_fuel_performance_analytics(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    durum: Optional[str] = Query(None),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    """
    Sefer bazli yakit performans metriklerini kullanici odakli payload ile doner.
    """
    try:
        start_date = date.fromisoformat(baslangic_tarih) if baslangic_tarih else None
        end_date = date.fromisoformat(bitis_tarih) if bitis_tarih else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Tarih formati gecersiz.")

    try:
        return await service.get_fuel_performance_analytics(
            durum=durum,
            baslangic_tarih=start_date,
            bitis_tarih=end_date,
            arac_id=arac_id,
            sofor_id=sofor_id,
            search=search,
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="Gecersiz durum degeri.")
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Fuel performance analytics error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Yakit performansi alinamadi")


@router.get("/{sefer_id}/cost-analysis", response_model=dict, status_code=202)
async def analyze_trip_costs(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    service: SeferService = Depends(get_sefer_service),
    job_manager: BackgroundJobManager = Depends(get_job_manager),
):
    """
    Sefer maliyet analizi ve Smart Reconciliation tetikleme (Asenkron).
    """
    try:
        # Check permission (get_by_id handles ownership)
        sefer = await service.get_by_id(sefer_id, current_user=current_user)
        if not sefer:
            raise HTTPException(status_code=404, detail="Sefer bulunamadı")

        # Submit to background job manager instead of raw BackgroundTasks
        job_id = await job_manager.submit(service.reconcile_costs, sefer_id)

        return {
            "status": AsyncJobStatus.PROCESSING.value,
            "task_id": job_id,
            "message": "Maliyet analizi arka plana alındı. Lütfen durum sorgulama endpoint'ini kullanın.",
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cost analysis initialization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Maliyet analizi başlatılamadı")
