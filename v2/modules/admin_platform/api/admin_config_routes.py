from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import SessionDep
from app.api.middleware.rate_limiter import limiter
from app.infrastructure.logging.logger import get_logger
from v2.modules.admin_platform.application.admin_audit_service import (
    log_config_change,
)
from v2.modules.admin_platform.application.konfig_service import (
    get_all_by_group,
)
from v2.modules.admin_platform.application.konfig_service import (
    get_all_configs as _get_all_configs,
)
from v2.modules.admin_platform.application.konfig_service import (
    update_config as _update_config,
)
from v2.modules.admin_platform.infrastructure.repository import get_admin_config_repo
from v2.modules.auth_rbac.public import Kullanici, require_yetki
from v2.modules.shared_kernel.exceptions import DomainError

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
    if group:
        return await get_all_by_group(db, group)
    return await _get_all_configs(db)


@router.get("/{key}", response_model=ConfigRead)
async def get_config(
    key: str,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("konfig_goruntule")),
):
    """Spesifik bir konfigürasyonu getir"""
    repo = get_admin_config_repo(db)
    config = await repo.get_config(key)
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
    repo = get_admin_config_repo(db)

    # 1. Get old value for audit
    config = await repo.get_config(key)
    if not config:
        raise HTTPException(status_code=404, detail="Konfigürasyon bulunamadı")

    old_value = config["deger"]

    try:
        # 2. Update config
        updated = await _update_config(
            db, key=key, value=data.value, user_id=current_user.id, reason=data.reason
        )

        # 3. Log the action
        await log_config_change(
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
