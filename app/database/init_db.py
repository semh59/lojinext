import asyncio
import logging

from app.database.connection import engine
from v2.modules.shared_kernel.infrastructure.base import Base

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_primary_data():
    """Dev/test only: create all tables without Alembic.

    Do NOT run in production — use `alembic upgrade head` instead.
    Production safeguard: refuses to run if ENVIRONMENT=production.
    """
    from app.config import settings

    if getattr(settings, "ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError(
            "init_db must not run in production. Use `alembic upgrade head`."
        )

    logger.info("Initializing database schema (dev/test)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized successfully.")


if __name__ == "__main__":
    asyncio.run(init_primary_data())
