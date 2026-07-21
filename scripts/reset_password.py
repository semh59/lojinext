import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.auth_rbac.public import hash_password as get_password_hash

USERNAME = os.getenv("RESET_USERNAME", "")
NEW_PASSWORD = os.getenv("NEW_PASSWORD", "")

if not USERNAME or not NEW_PASSWORD:
    print(
        "Kullanım: RESET_USERNAME=<kullanici> NEW_PASSWORD=<yeni_sifre> python -m scripts.reset_password"
    )
    sys.exit(1)


async def reset_password():
    print(f"Resetting password for {USERNAME}...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Kullanici).where(Kullanici.kullanici_adi == USERNAME)
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"User found: {user.kullanici_adi}")
            hashed_pw = get_password_hash(NEW_PASSWORD)
            user.sifre_hash = hashed_pw
            await session.commit()
            print("Password updated successfully.")
        else:
            print("User NOT found!")


if __name__ == "__main__":
    asyncio.run(reset_password())
