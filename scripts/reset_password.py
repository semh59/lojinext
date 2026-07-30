import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy import select

from v2.modules.auth_rbac.public import Kullanici
from v2.modules.auth_rbac.public import hash_password as get_password_hash
from v2.modules.platform_infra.database.module_role import open_role_scoped_session
from v2.modules.platform_infra.security.pii_encryption import blind_index

# Kullanici has no "kullanici_adi" column -- login identifier is the
# (PII-encrypted-at-rest) email field, looked up via its deterministic
# blind index (email_bidx), the same pattern authenticate.py/
# kullanici_repository.py/create_admin.py already use.
RESET_EMAIL = os.getenv("RESET_EMAIL", "")
NEW_PASSWORD = os.getenv("NEW_PASSWORD", "")

if not RESET_EMAIL or not NEW_PASSWORD:
    print(
        "Kullanım: RESET_EMAIL=<email> NEW_PASSWORD=<yeni_sifre> python -m scripts.reset_password"
    )
    sys.exit(1)


async def reset_password():
    print(f"Resetting password for {RESET_EMAIL}...")
    async with open_role_scoped_session("m_ops") as session:
        result = await session.execute(
            select(Kullanici).where(Kullanici.email_bidx == blind_index(RESET_EMAIL))
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"User found: {user.ad_soyad}")
            hashed_pw = get_password_hash(NEW_PASSWORD)
            user.sifre_hash = hashed_pw
            await session.commit()
            print("Password updated successfully.")
        else:
            print("User NOT found!")


if __name__ == "__main__":
    asyncio.run(reset_password())
