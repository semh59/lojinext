import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database.connection import engine
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.auth_rbac.public import hash_password as get_password_hash


async def create_admin():
    # Get admin password from environment or settings
    admin_password = os.environ.get("ADMIN_PASSWORD") or getattr(
        settings, "ADMIN_PASSWORD", None
    )
    if not admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable not set")
        sys.exit(1)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # 1. Check/Create admin role
        stmt = select(Rol).where(Rol.ad == "admin")
        result = await session.execute(stmt)
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            print("Creating admin role...")
            admin_role = Rol(
                ad="admin",
                yetkiler={
                    # Legacy keys (backward compat)
                    "kullanici_yonetimi": True,
                    "arac_yonetimi": True,
                    "sofor_yonetimi": True,
                    "raporlama": True,
                    "ayarlar": True,
                    "admin_panel": True,
                    # Granular endpoint keys (require_yetki checks)
                    "attribution_duzenle": True,
                    "backup_al": True,
                    "bakim_duzenle": True,
                    "bakim_ekle": True,
                    "bakim_oku": True,
                    "circuit_breaker_reset": True,
                    "kalibrasyon_duzenle": True,
                    "kalibrasyon_goruntule": True,
                    "konfig_duzenle": True,
                    "konfig_goruntule": True,
                    "kullanici_duzenle": True,
                    "kullanici_ekle": True,
                    "kullanici_goruntule": True,
                    "kullanici_sil": True,
                    "model_egit": True,
                    "model_goruntule": True,
                    "notification_rule_ekle": True,
                    "notification_rule_goruntule": True,
                    "rol_oku": True,
                    "rol_yaz": True,
                    "sistem_saglik_goruntule": True,
                    "yonetim_rapor": True,
                    # 2026-07-15 dedektif denetiminde bulundu — bu 5 anahtar
                    # hiçbir OR-alternatifi/fallback'i olmayan veya "all"/"*"
                    # fallback'ine dict'te karşılık gelmeyen endpoint'ler
                    # yüzünden admin rolüne hiç erişemiyordu:
                    "import_goruntule": True,  # admin_imports.py — tek yetki, fallback yok
                    "import_rollback": True,  # admin_imports.py — OR: all/* (ikisi de yoktu)
                    "notification_rule_duzenle": True,  # notification_routes.py — OR: all/*
                    "notification_rule_sil": True,  # notification_routes.py — OR: all/*
                    "admin": True,  # 3 endpoint literal "admin" anahtarı arıyor (rol adı değil)
                },
            )
            session.add(admin_role)
            await session.commit()
            await session.refresh(admin_role)

        # 2. Check/Create admin user
        stmt = select(Kullanici).where(Kullanici.email == "admin@lojinext.com")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        hashed_pw = get_password_hash(admin_password)

        if user:
            print("Updating existing admin user...")
            user.sifre_hash = hashed_pw
            user.aktif = True
            user.rol_id = admin_role.id
        else:
            print("Creating new admin user...")
            user = Kullanici(
                email="admin@lojinext.com",
                sifre_hash=hashed_pw,
                ad_soyad="Sistem Yöneticisi",
                rol_id=admin_role.id,
                aktif=True,
            )
            session.add(user)

        await session.commit()
        print("SUCCESS: Admin user created/updated.")
        print("  Email:    admin@lojinext.com")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(create_admin())
