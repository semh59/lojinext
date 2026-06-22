import asyncio

from sqlalchemy import text

from app.database.connection import engine


async def update_db():
    async with engine.begin() as conn:
        print("Updating database schema...")
        try:
            await conn.execute(
                text(
                    "ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS sofor_id INTEGER REFERENCES soforler(id) ON DELETE SET NULL;"
                )
            )
            print("✅ 'sofor_id' column added to 'kullanicilar' table.")
        except Exception as e:
            print(f"❌ Error updating 'kullanicilar': {e}")


if __name__ == "__main__":
    asyncio.run(update_db())
