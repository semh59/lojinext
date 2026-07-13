from typing import List, Optional

from sqlalchemy import select

from app.database.base_repository import BaseRepository
from app.database.models import Dorse


class DorseRepository(BaseRepository[Dorse]):
    """
    Asynchronous repository for Trailer (Dorse) management.
    Standardizes trailer specs for ML consumption (B-22).
    """

    model = Dorse
    search_columns = ["plaka", "marka", "tipi"]

    async def get_by_plate(
        self, plate: str, for_update: bool = False
    ) -> Optional[Dorse]:
        """Retrieves trailer details by plate (aktif olsun olmasın — sadece
        is_deleted hariç tutulur; duplicate/reaktivasyon kontrolü bunu bekler,
        bkz application/create_trailer.py)."""
        stmt = select(Dorse).where(Dorse.plaka == plate, ~Dorse.is_deleted)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_trailers(self) -> List[Dorse]:
        """Returns all active, non-deleted trailers."""
        stmt = select(Dorse).where(~Dorse.is_deleted, Dorse.aktif)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


import threading  # noqa: E402
from typing import Optional  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

_dorse_repo_lock = threading.Lock()
_dorse_repo: Optional["DorseRepository"] = None


def get_dorse_repo(session: Optional[AsyncSession] = None) -> "DorseRepository":
    """DorseRepo Provider — thread-safe singleton, patchable in tests."""
    global _dorse_repo
    if session:
        return DorseRepository(session=session)
    with _dorse_repo_lock:
        if _dorse_repo is None:
            _dorse_repo = DorseRepository()
    return _dorse_repo
