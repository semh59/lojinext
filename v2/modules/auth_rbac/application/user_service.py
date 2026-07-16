"""Administrative CRUD operations on the `kullanicilar` table.

Eski ``UserService`` sınıfı kaldırıldı (B.1) — her use-case bağımsız bir
fonksiyon, opsiyonel ``uow: UnitOfWork | None = None`` alır.
"""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.database.unit_of_work import UnitOfWork
from v2.modules.auth_rbac.domain.security import get_password_hash, verify_password


async def list_users(
    skip: int = 0, limit: int = 100, uow: Optional[UnitOfWork] = None
) -> List[Dict[str, Any]]:
    """List active users with pagination, eager-loading the role relation."""
    if uow is not None:
        return await uow.kullanici_repo.get_all(
            offset=skip, limit=limit, load_relations=["rol"]
        )
    async with UnitOfWork() as owned_uow:
        return await owned_uow.kullanici_repo.get_all(
            offset=skip, limit=limit, load_relations=["rol"]
        )


async def get_user(user_id: int, uow: Optional[UnitOfWork] = None) -> Dict[str, Any]:
    """Return one user by id; raise 404 if missing."""
    if uow is not None:
        return await _get_user(uow, user_id)
    async with UnitOfWork() as owned_uow:
        return await _get_user(owned_uow, user_id)


async def _get_user(uow: UnitOfWork, user_id: int) -> Dict[str, Any]:
    user = await uow.kullanici_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return user


async def create_user(
    data: dict, created_by_id: int, uow: Optional[UnitOfWork] = None
) -> Dict[str, Any]:
    """Create a new user with a bcrypt-hashed password."""
    if uow is not None:
        return await _create_user(uow, data, created_by_id)
    async with UnitOfWork() as owned_uow:
        return await _create_user(owned_uow, data, created_by_id)


async def _create_user(
    uow: UnitOfWork, data: dict, created_by_id: int
) -> Dict[str, Any]:
    existing = await uow.kullanici_repo.get_by_email(data["email"])
    if existing is not None:
        raise HTTPException(
            status_code=400, detail="Bu e-posta adresi zaten kullanımda"
        )

    try:
        new_id = await uow.kullanici_repo.create(
            email=data["email"],
            ad_soyad=data["ad_soyad"],
            rol_id=data["rol_id"],
            aktif=data.get("aktif", True),
            sofor_id=data.get("sofor_id"),
            sifre_hash=get_password_hash(data["sifre"]),
            olusturan_id=created_by_id if created_by_id != 0 else None,
        )
        await uow.commit()
    except IntegrityError as e:
        await uow.rollback()
        if "rol_id" in str(e.orig) or "kullanicilar_rol_id_fkey" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="Geçersiz rol_id: belirtilen rol mevcut değil",
            )
        raise HTTPException(
            status_code=400,
            detail="Kullanıcı oluşturulamadı: veri bütünlüğü hatası",
        )

    # include_inactive=True: az önce oluşturulan kaydı aynı
    # transaction içinde geri okuyoruz — caller `aktif=False` ile
    # oluşturmuş olabilir (data.get("aktif", True)), bu durumda da
    # okunabilmeli.
    created = await uow.kullanici_repo.get_by_id(new_id, include_inactive=True)
    if created is None:
        raise HTTPException(
            status_code=500, detail="Oluşturulan kullanıcı tekrar okunamadı"
        )
    return created


async def update_user(
    user_id: int, data: dict, uow: Optional[UnitOfWork] = None
) -> Dict[str, Any]:
    """Update editable user fields; rehash password when supplied."""
    if uow is not None:
        return await _update_user(uow, user_id, data)
    async with UnitOfWork() as owned_uow:
        return await _update_user(owned_uow, user_id, data)


async def _update_user(uow: UnitOfWork, user_id: int, data: dict) -> Dict[str, Any]:
    existing = await uow.kullanici_repo.get_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    update_data = dict(
        data
    )  # callers use exclude_unset=True; allow None to clear nullable fields
    if update_data.get("sifre"):
        update_data["sifre_hash"] = get_password_hash(update_data.pop("sifre"))
    else:
        update_data.pop("sifre", None)

    if not update_data:
        return existing

    try:
        success = await uow.kullanici_repo.update(user_id, **update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Güncelleme başarısız")
        await uow.commit()
    except IntegrityError as e:
        await uow.rollback()
        if "email" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="Bu e-posta adresi zaten kullanımda",
            )
        raise HTTPException(
            status_code=400,
            detail="Kullanıcı güncellenemedi: veri bütünlüğü hatası",
        )
    return await uow.kullanici_repo.get_by_id(user_id)


async def delete_user(user_id: int, uow: Optional[UnitOfWork] = None) -> bool:
    """Soft-delete a user (sets aktif=False)."""
    if uow is not None:
        success = await uow.kullanici_repo.delete(user_id)
        if success:
            await uow.commit()
        return success
    async with UnitOfWork() as owned_uow:
        success = await owned_uow.kullanici_repo.delete(user_id)
        if success:
            await owned_uow.commit()
        return success


async def change_password(
    user_id: int,
    current_password: str,
    new_password: str,
    uow: Optional[UnitOfWork] = None,
) -> bool:
    """Verify current password and update with new bcrypt hash.

    Returns True on success, False if current_password does not match.
    """
    # Defense-in-depth: blocks the virtual superadmin fallback (id=0). The
    # primary guard is now at the endpoint via current_user.is_env_superadmin
    # (ARCH-001), since the resolved break-glass superadmin has a real id.
    if user_id == 0:
        raise HTTPException(
            status_code=403,
            detail="Sistem yöneticisi şifresi ortam değişkeni üzerinden yönetilir.",
        )
    if uow is not None:
        return await _change_password(uow, user_id, current_password, new_password)
    async with UnitOfWork() as owned_uow:
        return await _change_password(
            owned_uow, user_id, current_password, new_password
        )


async def _change_password(
    uow: UnitOfWork, user_id: int, current_password: str, new_password: str
) -> bool:
    user = await uow.kullanici_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    # get_by_id() always returns a dict (BaseRepository.get_by_id's return
    # type), never an ORM object — the hasattr/attribute-access branch this
    # used to have was dead code (2026-07-16 dedektif denetimi bulgusu).
    stored_hash: str = user["sifre_hash"]

    if not verify_password(current_password, stored_hash):
        return False

    new_hash = get_password_hash(new_password)
    success = await uow.kullanici_repo.update(user_id, sifre_hash=new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Şifre güncellenemedi")

    await uow.commit()
    return True
