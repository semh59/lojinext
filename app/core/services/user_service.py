"""User service — administrative CRUD operations on the `kullanicilar` table."""

from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, verify_password
from app.database.unit_of_work import UnitOfWork


class UserService:
    """Service for managing administrative user operations."""

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """List active users with pagination, eager-loading the role relation."""
        async with UnitOfWork() as uow:
            return await uow.kullanici_repo.get_all(
                offset=skip, limit=limit, load_relations=["rol"]
            )

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """Return one user by id; raise 404 if missing."""
        async with UnitOfWork() as uow:
            user = await uow.kullanici_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
            return user

    async def create_user(self, data: dict, created_by_id: int) -> Dict[str, Any]:
        """Create a new user with a bcrypt-hashed password."""
        async with UnitOfWork() as uow:
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

            created = await uow.kullanici_repo.get_by_id(new_id)
            if created is None:
                raise HTTPException(
                    status_code=500, detail="Oluşturulan kullanıcı tekrar okunamadı"
                )
            return created

    async def update_user(self, user_id: int, data: dict) -> Dict[str, Any]:
        """Update editable user fields; rehash password when supplied."""
        async with UnitOfWork() as uow:
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

    async def delete_user(self, user_id: int) -> bool:
        """Soft-delete a user (sets aktif=False)."""
        async with UnitOfWork() as uow:
            success = await uow.kullanici_repo.delete(user_id)
            if success:
                await uow.commit()
            return success

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
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
        async with UnitOfWork() as uow:
            user = await uow.kullanici_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
            real_id = user_id
            stored_hash: str = (
                user.sifre_hash if hasattr(user, "sifre_hash") else user["sifre_hash"]
            )

            if not verify_password(current_password, stored_hash):
                return False

            new_hash = get_password_hash(new_password)
            success = await uow.kullanici_repo.update(real_id, sifre_hash=new_hash)
            if not success:
                raise HTTPException(status_code=500, detail="Şifre güncellenemedi")

            await uow.commit()
            return True
