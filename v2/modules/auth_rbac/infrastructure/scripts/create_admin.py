"""Manuel/dev-only CLI yardımcısı: super_admin kullanıcısı senkronize eder.

2026-07-22: `app/scripts/create_admin.py`'den bu modüle taşındı (mekanik
taşıma, davranış değişikliği yok) — Kullanici/Rol auth_rbac'ın tablo
sahipliğinde. Kök `scripts/create_admin.py` (farklı, kasıtlı bir
duplikat — rol=admin, hardcoded email, granular yetkiler dict; 2026-07-15
kararıyla ayrı kalıyor) İLE KARIŞTIRILMASIN. Gerçek prod bootstrap'ı
`alembic/versions/0002_seed_and_bootstrap.py`'de yapılır; bu script
yalnız manuel/dev CLI kullanımı içindir.

Çalıştırma: ``python -m v2.modules.auth_rbac.infrastructure.scripts.create_admin``
(repo kökünden).
"""

import asyncio
import os
import sys

from sqlalchemy import select

sys.path.append(os.getcwd())

from app.config import settings
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.auth_rbac.public import hash_password as get_password_hash
from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.platform_infra.security.pii_encryption import blind_index


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
