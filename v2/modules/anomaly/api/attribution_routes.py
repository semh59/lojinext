from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.exceptions import DomainError
from app.database.models import Kullanici
from app.database.unit_of_work import UnitOfWork
from v2.modules.anomaly.application.attribute_loss import (
    override_attribution,
)
from v2.modules.anomaly.schemas import (
    AttributionOverrideRequest,
    AttributionOverrideResponse,
)
from v2.modules.auth_rbac.domain.permission_checker import require_yetki

router = APIRouter()


@router.post(
    "/override",
    response_model=AttributionOverrideResponse,
    dependencies=[Depends(require_yetki(["attribution_duzenle", "all", "*"]))],
)
async def override_trip_attribution(
    request: AttributionOverrideRequest,
    current_user: Kullanici = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Manually override the vehicle or driver for a specific trip.
    """
    try:
        # NOT: UnitOfWork(db) burada ÖNCEDEN `async with` ile açılmıyor —
        # override_attribution()'ın kendi `async with uow:` bloğu tek
        # giriş noktası olmalı. Önceden burada da açılıyordu, bu da aynı
        # instance'ı iki kez `__aenter__` etmek anlamına geliyordu — connection-
        # pool leak'ine yol açan kök neden (bkz.
        # TASKS/bug-connection-pool-leak-under-load.md, AuthService/MLService'te
        # aynı desen bulunup düzeltildi).
        success = await override_attribution(
            sefer_id=request.sefer_id,
            arac_id=request.new_arac_id,
            sofor_id=request.new_sofor_id,
            reason=request.reason,
            uow=UnitOfWork(db),
        )

        return AttributionOverrideResponse(
            sefer_id=request.sefer_id,
            success=success,
            message="Atanmış araç/şoför başarıyla güncellendi."
            if success
            else "Güncelleme yapılamadı.",
        )
    except HTTPException:
        raise
    except DomainError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atama güncellenemedi: {str(e)}",
        )


@router.post(
    "/bulk-override",
    response_model=List[AttributionOverrideResponse],
    dependencies=[Depends(require_yetki(["attribution_duzenle", "all", "*"]))],
)
async def bulk_override_trip_attribution(
    requests: List[AttributionOverrideRequest],
    current_user: Kullanici = Depends(deps.get_current_active_user),
):
    """
    Bulk override trip attributions.
    """
    results = []

    for req in requests:
        try:
            # Fresh UoW per item so each gets its own commit cycle.
            # Sharing a single UoW caused a _committed=True latch that
            # silently skipped commits for all items after the first.
            success = await override_attribution(
                sefer_id=req.sefer_id,
                arac_id=req.new_arac_id,
                sofor_id=req.new_sofor_id,
                reason=req.reason,
                uow=UnitOfWork(),
            )
            results.append(
                AttributionOverrideResponse(
                    sefer_id=req.sefer_id,
                    success=success,
                    message="Başarılı" if success else "Hata",
                )
            )
        except DomainError:
            raise
        except HTTPException:
            raise
        except Exception as e:
            results.append(
                AttributionOverrideResponse(
                    sefer_id=req.sefer_id, success=False, message=str(e)
                )
            )

    return results
