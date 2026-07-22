from typing import List

from fastapi import APIRouter, Depends, status

from v2.modules.auth_rbac.application import role_service
from v2.modules.auth_rbac.domain.permission_checker import require_yetki
from v2.modules.auth_rbac.infrastructure.models import Kullanici
from v2.modules.auth_rbac.schemas import RolCreate, RolRead
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[RolRead])
async def get_roles(
    current_user: Kullanici = Depends(require_yetki("rol_oku")),
):
    """Sistem rollerini listele"""
    return await role_service.list_roles()


@router.get("/{role_id}", response_model=RolRead)
async def get_role(
    role_id: int,
    current_user: Kullanici = Depends(require_yetki("rol_oku")),
):
    """Spesifik bir rol getir"""
    return await role_service.get_role(role_id)


@router.post("/", response_model=RolRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RolCreate,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Yeni rol oluştur"""
    new_role = await role_service.create_role(
        payload.ad, payload.yetkiler, current_user
    )
    await log_audit_event(
        action="rol_olustur",
        module="admin_roles",
        entity_id=str(new_role.id),
        user_id=current_user.id,
        details={"ad": new_role.ad, "yetkiler": new_role.yetkiler},
    )
    return new_role


@router.put("/{role_id}", response_model=RolRead)
async def update_role(
    role_id: int,
    payload: RolCreate,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Mevcut rolü güncelle (ad + yetkiler tam değişim)."""
    updated = await role_service.update_role(
        role_id, payload.ad, payload.yetkiler, current_user
    )
    await log_audit_event(
        action="rol_guncelle",
        module="admin_roles",
        entity_id=str(role_id),
        user_id=current_user.id,
        details={"ad": payload.ad, "yetkiler": payload.yetkiler},
    )
    return updated


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Rolü sil. Sistem rolleri ve atanmış kullanıcısı olan roller silinemez."""
    deleted_ad = await role_service.delete_role(role_id)
    await log_audit_event(
        action="rol_sil",
        module="admin_roles",
        entity_id=str(role_id),
        user_id=current_user.id,
        details={"ad": deleted_ad},
    )
