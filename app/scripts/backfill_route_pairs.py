import asyncio
import hashlib

from sqlalchemy import select

from app.database.db_session import get_async_session_context
from v2.modules.location.public import Lokasyon
from v2.modules.trip.public import SeferORM as Sefer


async def backfill_route_pairs():
    """
    Backfills route_pair_id in Sefer table based on the linked Lokasyon's coordinates.
    Standardizes the contract to resolve HB2.
    """
    print("[BACKFILL] Starting route_pair_id backfill...")

    async with get_async_session_context() as session:
        # 1. Get all trips that have a guzergah_id but no route_pair_id
        stmt = (
            select(Sefer, Lokasyon)
            .join(Lokasyon, Sefer.guzergah_id == Lokasyon.id)
            .where(Sefer.route_pair_id.is_(None))
        )
        result = await session.execute(stmt)
        trips_to_fix = result.all()

        updated_count = 0
        for sefer, lokasyon in trips_to_fix:
            # Generate deterministic hash based on coordinates (V2.1 Standard)
            coord_str = f"{lokasyon.cikis_lat:.5f},{lokasyon.cikis_lon:.5f}->{lokasyon.varis_lat:.5f},{lokasyon.varis_lon:.5f}"  # noqa: E501
            route_pair_id = hashlib.sha256(coord_str.encode()).hexdigest()[:16]

            sefer.route_pair_id = route_pair_id
            updated_count += 1

            if updated_count % 100 == 0:
                print(f"[BACKFILL] Processed {updated_count} records...")

        await session.commit()
        print(f"[BACKFILL] Successfully updated {updated_count} trip records.")


if __name__ == "__main__":
    asyncio.run(backfill_route_pairs())
