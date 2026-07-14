from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import SessionDep
from app.api.middleware.rate_limiter import limiter
from app.core.exceptions import DomainError
from app.core.services.admin_audit_service import AdminAuditService
from app.core.services.konfig_service import KonfigService
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from v2.modules.auth_rbac.domain.permission_checker import require_yetki

router = APIRouter()
logger = get_logger(__name__)


class ConfigUpdate(BaseModel):
    value: Any
    reason: Optional[str] = None


class ConfigRead(BaseModel):
    anahtar: str
    deger: Any
    tip: str
    birim: Optional[str]
    min_deger: Optional[float]
    max_deger: Optional[float]
    grup: str
    aciklama: Optional[str]
    yeniden_baslat: bool
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[ConfigRead])
async def get_all_configs(
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("konfig_goruntule")),
    group: Optional[str] = None,
):
    """Sistem konfigürasyonlarını listele"""
    service = KonfigService(db)
    if group:
        return await service.get_all_by_group(group)
    return await service.get_all()


@router.get("/{key}", response_model=ConfigRead)
async def get_config(
    key: str,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("konfig_goruntule")),
):
    """Spesifik bir konfigürasyonu getir"""
    service = KonfigService(db)
    config = await service.repo.get_config(key)
    if not config:
        raise HTTPException(status_code=404, detail="Konfigürasyon bulunamadı")
    return config


@router.put("/{key}", response_model=ConfigRead)
@limiter.limit("30/hour")
async def update_config(
    key: str,
    data: ConfigUpdate,
    request: Request,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("konfig_duzenle")),
):
    """Konfigürasyonu güncelle ve logla"""
    service = KonfigService(db)
    audit_service = AdminAuditService()

    # 1. Get old value for audit
    config = await service.repo.get_config(key)
    if not config:
        raise HTTPException(status_code=404, detail="Konfigürasyon bulunamadı")

    old_value = config["deger"]

    try:
        # 2. Update config
        updated = await service.update_config(
            key=key, value=data.value, user_id=current_user.id, reason=data.reason
        )

        # 3. Log the action
        await audit_service.log_config_change(
            user=current_user,
            key=key,
            old_val=old_value,
            new_val=data.value,
            request=request,
        )

        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config update error: {e}")
        raise HTTPException(
            status_code=500, detail="Güncelleme sırasında bir hata oluştu"
        )
