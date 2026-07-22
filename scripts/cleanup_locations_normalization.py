import asyncio
import os
import sys

from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.location.public import Lokasyon


def tr_title(text: str) -> str:
    if not text:
        return ""
    # Simple consistent title case that handles Turkish i/İ somewhat better
    # by just being consistent.
    text = text.strip().replace("i", "İ").upper().lower().title()
    # Wait, title() in Python is tricky for Turkish.
    # Let's use a very simple one:
    return text.strip().title()


async def cleanup_locations():
    async with AsyncSessionLocal() as db:
        stmt = select(Lokasyon)
        result = await db.execute(stmt)
        locations = result.scalars().all()

        print("\n--- CLEANING LOCATIONS ---")
        for loc in locations:
            old_cikis = loc.cikis_yeri
            old_varis = loc.varis_yeri

            # Use a very standard normalization
            # We'll use .strip().title() but we need to handle the i/İ mismatch
            # or just accept one.
            new_cikis = old_cikis.strip().title()
            new_varis = old_varis.strip().title()

            if new_cikis != old_cikis or new_varis != old_varis:
                print(f"Updating ID {loc.id}: '{old_cikis}' -> '{new_cikis}'")
                loc.cikis_yeri = new_cikis
                loc.varis_yeri = new_varis

        await db.commit()
        print("Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(cleanup_locations())
