import asyncio
import os
import sys

from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from app.database.connection import AsyncSessionLocal


async def init_ml_db():
    # DEPRECATED: model_versions is managed by Alembic migrations.
    # Run `alembic upgrade head` instead of this script.
    # This script's column set may diverge from the live schema (missing `mape`).
    print("Initializing ML Database Tables...")
    async with AsyncSessionLocal() as session:
        try:
            # Check if table exists
            result = await session.execute(
                text("SELECT to_regclass('public.model_versions')")
            )
            if result.scalar():
                print("Table 'model_versions' already exists.")
                return

            print("Creating 'model_versions' table...")
            await session.execute(
                text("""
                CREATE TABLE model_versions (
                    id SERIAL PRIMARY KEY,
                    arac_id INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    model_type VARCHAR(50) NOT NULL,
                    params_json TEXT NOT NULL,
                    r2_score FLOAT,
                    mae FLOAT,
                    sample_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    notes TEXT
                );
            """)
            )
            await session.commit()
            print("Successfully created 'model_versions' table.")

            # Add indexes if needed
            await session.execute(
                text(
                    "CREATE INDEX idx_model_versions_arac_id ON model_versions(arac_id)"
                )
            )
            await session.commit()
            print("Created indexes.")

        except Exception as e:
            await session.rollback()
            print(f"Error during initialization: {e}")


if __name__ == "__main__":
    asyncio.run(init_ml_db())
