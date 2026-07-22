import asyncio
import os
import sys

from sqlalchemy import select

sys.path.append(os.getcwd())

from app.config import settings
from app.infrastructure.security.pii_encryption import blind_index
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.auth_rbac.public import hash_password as get_password_hash
from v2.modules.platform_infra.database.connection import AsyncSessionLocal


async def create_user():
    admin_email = settings.SUPER_ADMIN_USERNAME
    admin_password = settings.ADMIN_PASSWORD.get_secret_value()

    async with AsyncSessionLocal() as db:
        role_result = await db.execute(select(Rol).where(Rol.ad == "super_admin"))
        role = role_result.scalars().first()
        if not role:
            role = Rol(ad="super_admin", yetkiler={"*": True})
            db.add(role)
            await db.flush()

        result = await db.execute(
            select(Kullanici).where(Kullanici.email_bidx == blind_index(admin_email))
        )
        user = result.scalars().first()

        if user:
            print(f"User {admin_email} exists. Updating password...")
            user.sifre_hash = get_password_hash(admin_password)
            user.aktif = True
            user.rol_id = role.id
        else:
            print(f"User {admin_email} not found. Creating...")
            user = Kullanici(
                email=admin_email,
                sifre_hash=get_password_hash(admin_password),
                ad_soyad="Sistem Yoneticisi",
                aktif=True,
                rol_id=role.id,
            )
            db.add(user)

        await db.commit()
        print(f"Admin user '{admin_email}' synchronized.")


if __name__ == "__main__":
    asyncio.run(create_user())
