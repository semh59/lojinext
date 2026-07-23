import asyncio

from sqlalchemy import delete

from v2.modules.auth_rbac.public import Kullanici
from v2.modules.platform_infra.database.connection import engine


async def clear():
    async with engine.begin() as conn:
        await conn.execute(
            delete(Kullanici).where(Kullanici.email == "test_sofor_ahmet@lojinext.com")
        )
        print("Test user deleted.")


if __name__ == "__main__":
    asyncio.run(clear())
