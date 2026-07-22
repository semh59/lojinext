"""Telegram onay akışı — sefer onaylama/reddetme."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.deps import get_sefer_service
from v2.modules.auth_rbac.public import Kullanici, require_permissions
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.metrics import trip_approval_total
from v2.modules.shared_kernel.exceptions import DomainError
from v2.modules.trip.public import SeferResponse, SeferService
from v2.modules.trip.schemas import SeferOnayRequest

logger = get_logger(__name__)

router = APIRouter()


@router.post("/{sefer_id}/onayla", response_model=SeferResponse)
async def sefer_onayla(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    body: SeferOnayRequest = Body(default_factory=SeferOnayRequest),  # type: ignore[arg-type]
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer onaylama — admin veya baş şoför yetkisi gerektirir."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    try:
        actor_id = current_user.id  # capture pre-commit (see create_sefer)
        result = await service.set_onay_durumu(
            sefer_id, "onaylandi", body.onay_notu, actor_id
        )
        trip_approval_total.labels(action="onayla").inc()
        await log_audit_event(
            module="sefer",
            action="onayla",
            entity_id=str(sefer_id),
            new_value={"onay_notu": body.onay_notu},
            user_id=actor_id,
        )
        return result
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Sefer onaylanamadı (id=%s): %s", sefer_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Onaylama işlemi başarısız")


@router.post("/{sefer_id}/reddet", response_model=SeferResponse)
async def sefer_reddet(
    sefer_id: int,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:onayla"))],
    body: SeferOnayRequest = Body(default_factory=SeferOnayRequest),  # type: ignore[arg-type]
    service: SeferService = Depends(get_sefer_service),
):
    """Sefer reddetme — admin veya baş şoför yetkisi gerektirir."""
    sefer = await service.get_by_id(sefer_id, current_user=current_user)
    if not sefer:
        raise HTTPException(status_code=404, detail="Sefer bulunamadı")
    try:
        actor_id = current_user.id  # capture pre-commit (see create_sefer)
        result = await service.set_onay_durumu(
            sefer_id, "reddedildi", body.onay_notu, actor_id
        )
        trip_approval_total.labels(action="reddet").inc()
        await log_audit_event(
            module="sefer",
            action="reddet",
            entity_id=str(sefer_id),
            new_value={"onay_notu": body.onay_notu},
            user_id=actor_id,
        )
        return result
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Sefer reddedilemedi (id=%s): %s", sefer_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Reddetme işlemi başarısız")
