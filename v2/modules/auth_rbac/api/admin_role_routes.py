from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from v2.modules.auth_rbac.domain.permission_checker import require_yetki
from v2.modules.auth_rbac.infrastructure.repository import RolRepository
from v2.modules.auth_rbac.schemas import RolCreate, RolRead

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[RolRead])
async def get_roles(
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("rol_oku")),
):
    """Sistem rollerini listele"""
    repo = RolRepository(db)
    return await repo.get_all()


@router.get("/{role_id}", response_model=RolRead)
async def get_role(
    role_id: int,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("rol_oku")),
):
    """Spesifik bir rol getir"""
    repo = RolRepository(db)
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol bulunamadı")
    return role


@router.post("/", response_model=RolRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RolCreate,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Yeni rol oluştur"""
    # Privilege escalation guard: caller cannot grant permissions they don't hold.
    # super_admin (wildcard "*") is exempt.
    caller_yetkiler = (current_user.rol.yetkiler or {}) if current_user.rol else {}
    is_wildcard = caller_yetkiler.get("*") or (
        current_user.rol and current_user.rol.ad == "super_admin"
    )
    if not is_wildcard:
        for perm_key, enabled in payload.yetkiler.items():
            if enabled and not caller_yetkiler.get(perm_key):
                raise HTTPException(
                    status_code=403,
                    detail=f"'{perm_key}' yetkisini veremezsiniz: bu yetki size atanmamış",
                )

    repo = RolRepository(db)
    try:
        new_role = await repo.create(ad=payload.ad, yetkiler=payload.yetkiler)
        await db.commit()
        await log_audit_event(
            action="rol_olustur",
            module="admin_roles",
            entity_id=str(new_role.id),
            user_id=current_user.id,
            details={"ad": new_role.ad, "yetkiler": new_role.yetkiler},
        )
        return new_role
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Düzenlenmesi/silinmesi yasak sistem rolleri.
_PROTECTED_ROLES = {"super_admin", "admin"}


def _assert_no_privilege_escalation(
    current_user: Kullanici, yetkiler: dict[str, bool]
) -> None:
    """Çağıran, kendisinde olmayan bir yetkiyi başka role veremez (super_admin hariç)."""
    caller_yetkiler = (current_user.rol.yetkiler or {}) if current_user.rol else {}
    is_wildcard = caller_yetkiler.get("*") or (
        current_user.rol and current_user.rol.ad == "super_admin"
    )
    if is_wildcard:
        return
    for perm_key, enabled in yetkiler.items():
        if enabled and not caller_yetkiler.get(perm_key):
            raise HTTPException(
                status_code=403,
                detail=f"'{perm_key}' yetkisini veremezsiniz: bu yetki size atanmamış",
            )


@router.put("/{role_id}", response_model=RolRead)
async def update_role(
    role_id: int,
    payload: RolCreate,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Mevcut rolü güncelle (ad + yetkiler tam değişim)."""
    repo = RolRepository(db)
    existing = await repo.get_by_id(role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Rol bulunamadı")
    if existing.ad in _PROTECTED_ROLES:
        raise HTTPException(
            status_code=403, detail=f"'{existing.ad}' sistem rolü düzenlenemez"
        )

    _assert_no_privilege_escalation(current_user, payload.yetkiler)

    try:
        updated = await repo.update(role_id, ad=payload.ad, yetkiler=payload.yetkiler)
        await db.commit()
        await log_audit_event(
            action="rol_guncelle",
            module="admin_roles",
            entity_id=str(role_id),
            user_id=current_user.id,
            details={"ad": payload.ad, "yetkiler": payload.yetkiler},
        )
        return updated
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: SessionDep,
    current_user: Kullanici = Depends(require_yetki("rol_yaz")),
):
    """Rolü sil. Sistem rolleri ve atanmış kullanıcısı olan roller silinemez."""
    repo = RolRepository(db)
    existing = await repo.get_by_id(role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Rol bulunamadı")
    if existing.ad in _PROTECTED_ROLES:
        raise HTTPException(
            status_code=403, detail=f"'{existing.ad}' sistem rolü silinemez"
        )

    in_use = await repo.count_users_with_role(role_id)
    if in_use > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Bu rol {in_use} kullanıcıya atanmış; önce onları başka role taşıyın",
        )

    await repo.delete(role_id)
    await db.commit()
    await log_audit_event(
        action="rol_sil",
        module="admin_roles",
        entity_id=str(role_id),
        user_id=current_user.id,
        details={"ad": existing.ad},
    )
