"""Administrative CRUD operations on the `roller` table.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/admin_role_routes.py`` daha önce
``RolRepository``'yi doğrudan örnekliyor VE privilege-escalation guard'ını
(``create_role``/``update_role`` içinde) iki kez neredeyse birebir
tekrarlıyordu — diğer 5 auth_rbac route dosyası her zaman ``application/``
katmanına delege ederken bu dosya delege etmiyordu. Mekanik taşıma,
davranış değişikliği yok (yalnız guard'ın iki kopyası tek fonksiyona
indirgendi — saf DRY, karar mantığı birebir aynı).
"""

from typing import Dict, List

from fastapi import HTTPException

from app.database.models import Kullanici, Rol
from app.database.unit_of_work import UnitOfWork

_PROTECTED_ROLES = {"super_admin", "admin"}


def assert_no_privilege_escalation(
    current_user: Kullanici, yetkiler: Dict[str, bool]
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


async def list_roles() -> List[Rol]:
    async with UnitOfWork() as uow:
        return await uow.rol_repo.get_all()


async def get_role(role_id: int) -> Rol:
    async with UnitOfWork() as uow:
        role = await uow.rol_repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Rol bulunamadı")
        return role


async def create_role(
    ad: str, yetkiler: Dict[str, bool], current_user: Kullanici
) -> Rol:
    # Privilege escalation guard: caller cannot grant permissions they don't hold.
    assert_no_privilege_escalation(current_user, yetkiler)

    async with UnitOfWork() as uow:
        try:
            new_role = await uow.rol_repo.create(ad=ad, yetkiler=yetkiler)
            await uow.commit()
            return new_role
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


async def update_role(
    role_id: int, ad: str, yetkiler: Dict[str, bool], current_user: Kullanici
) -> Rol:
    async with UnitOfWork() as uow:
        existing = await uow.rol_repo.get_by_id(role_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Rol bulunamadı")
        if existing.ad in _PROTECTED_ROLES:
            raise HTTPException(
                status_code=403, detail=f"'{existing.ad}' sistem rolü düzenlenemez"
            )

        assert_no_privilege_escalation(current_user, yetkiler)

        try:
            updated = await uow.rol_repo.update(role_id, ad=ad, yetkiler=yetkiler)
            await uow.commit()
            return updated
        except ValueError as exc:
            await uow.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc


async def delete_role(role_id: int) -> str:
    """Rolü siler, audit-log için silinen rolün adını döner."""
    async with UnitOfWork() as uow:
        existing = await uow.rol_repo.get_by_id(role_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Rol bulunamadı")
        if existing.ad in _PROTECTED_ROLES:
            raise HTTPException(
                status_code=403, detail=f"'{existing.ad}' sistem rolü silinemez"
            )

        in_use = await uow.rol_repo.count_users_with_role(role_id)
        if in_use > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Bu rol {in_use} kullanıcıya atanmış; önce onları başka role taşıyın",
            )

        deleted_ad = existing.ad
        await uow.rol_repo.delete(role_id)
        await uow.commit()
        return deleted_ad
