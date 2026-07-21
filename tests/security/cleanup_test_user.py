import asyncio

from sqlalchemy import delete

from app.database.connection import engine
from v2.modules.auth_rbac.public import Kullanici


async def clear():
    async with engine.begin() as conn:
        await conn.execute(
            delete(Kullanici).where(Kullanici.email == "test_sofor_ahmet@lojinext.com")
        )
        print("Test user deleted.")


if __name__ == "__main__":
    asyncio.run(clear())
