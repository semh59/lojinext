from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_sefer_service, require_permissions
from app.core.exceptions import DomainError
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from v2.modules.trip.public import SeferListResponse, SeferResponse, SeferService
from v2.modules.trip.schemas import TripTimelineResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=SeferListResponse)
async def read_seferler(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    baslangic_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis_tarih: Optional[str] = Query(None, description="YYYY-MM-DD"),
    arac_id: Optional[int] = Query(None),
    sofor_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    onay_durumu: Optional[str] = Query(
        None, description="beklemede|onaylandi|reddedildi"
    ),
):
    """Seferleri listele (Service Layer)."""
    try:
        # Service handles skip/limit/safety/validation and ISOLATION internally
        # Returns Dict with "items", "total", "skip", "limit"
        return await service.get_all_paged(
            current_user=current_user,
            skip=skip,
            limit=limit,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            durum=durum,
            search=search,
            onay_durumu=onay_durumu,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing trips via service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Liste alınırken hata oluştu")


@router.get("/today", response_model=SeferListResponse)
async def read_bugunun_seferleri(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Bugünün seferlerini listele."""
    try:
        return await service.get_all_paged(
            current_user=current_user,
            baslangic_tarih=date.today().isoformat(),
            bitis_tarih=date.today().isoformat(),
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching today's trips: {e}")
        raise HTTPException(status_code=500, detail="Bugünkü seferler alınamadı")


@router.get("/beklemede", response_model=List[SeferResponse])
async def beklemede_seferler(
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    service: SeferService = Depends(get_sefer_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Telegram botundan gelen, admin onayı bekleyen seferler."""
    try:
        return await service.get_by_onay_durumu("beklemede", skip=skip, limit=limit)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Beklemede seferler alınamadı: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Seferler alınamadı")


@router.get("/{sefer_id}", response_model=SeferResponse)
async def read_sefer(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Tekil sefer getir (Güvenli)."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    return sefer


@router.get("/{sefer_id}/timeline", response_model=TripTimelineResponse)
async def get_sefer_timeline(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Seferin kronolojik olay akışını (audit log) getirir."""
    try:
        # Sefer var mı kontrolü (isolation/safety)
        await service.get_by_id(sefer_id, current_user=current_user)

        timeline_items = await service.get_timeline(sefer_id)
        return {"items": timeline_items}
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Error fetching timeline for trip {sefer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Zaman çizelgesi alınamadı")
