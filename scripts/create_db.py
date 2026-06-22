"""PostgreSQL veritabanı oluşturma scripti"""

import asyncio
import os
import sys

import asyncpg

_DB_PASSWORD = os.getenv("DB_PASSWORD", "")
if not _DB_PASSWORD:
    print("Kullanım: DB_PASSWORD=<sifre> python -m scripts.create_db")
    sys.exit(1)


async def create_database():
    # postgres veritabanına bağlan (default)
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password=_DB_PASSWORD,
        database="postgres",
    )

    # tir_yakit veritabanı var mı kontrol et
    exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = 'tir_yakit'"
    )

    if not exists:
        await conn.execute("CREATE DATABASE tir_yakit")
        print("✅ tir_yakit veritabanı oluşturuldu!")
    else:
        print("ℹ️ tir_yakit veritabanı zaten mevcut")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(create_database())
