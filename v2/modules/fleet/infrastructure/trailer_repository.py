import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_fleet_stats(self) -> Dict[str, Any]:
        """Dorse filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
        query = """
            SELECT
                COUNT(*)                                                                              AS total,
                COUNT(*) FILTER (WHERE aktif = true)                                                  AS active,
                COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                    AND muayene_tarihi >= CURRENT_DATE
                                    AND muayene_tarihi <= CURRENT_DATE + INTERVAL '30 days')          AS inspection_expiring,
                COUNT(*) FILTER (WHERE muayene_tarihi IS NOT NULL
                                    AND muayene_tarihi < CURRENT_DATE)                                AS inspection_overdue
            FROM dorseler
        """  # noqa: E501
        rows = await self.execute_query(query)
        return dict(rows[0]) if rows else {}

    async def get_inspection_alerts(
        self, within_days: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Muayenesi yaklaşan (``expiring``) veya geçmiş (``overdue``) dorseler.

        Araç ``get_inspection_alerts`` ile aynı sözleşme (dorse'de model yok,
        tipi var). Aktif + soft-delete edilmemiş dorselerle sınırlı.
        """
        query = """
            SELECT
                id,
                plaka,
                marka,
                tipi,
                yil,
                muayene_tarihi,
                CASE
                    WHEN muayene_tarihi < CURRENT_DATE THEN 'overdue'
                    ELSE 'expiring'
                END AS bucket,
                (muayene_tarihi - CURRENT_DATE) AS days_remaining
            FROM dorseler
            WHERE aktif = TRUE
              AND is_deleted = FALSE
              AND muayene_tarihi IS NOT NULL
              AND (
                  muayene_tarihi < CURRENT_DATE
                  OR muayene_tarihi <= CURRENT_DATE + (:within_days || ' days')::interval
              )
            ORDER BY muayene_tarihi ASC
        """
        rows = await self.execute_query(query, {"within_days": str(within_days)})

        expiring: List[Dict[str, Any]] = []
        overdue: List[Dict[str, Any]] = []
        for row in rows:
            item = {
                "id": row["id"],
                "plaka": row["plaka"],
                "marka": row["marka"],
                "tipi": row["tipi"],
                "yil": row["yil"],
                "muayene_tarihi": row["muayene_tarihi"].isoformat()
                if row["muayene_tarihi"]
                else None,
                "days_remaining": int(row["days_remaining"])
                if row["days_remaining"] is not None
                else None,
            }
            (overdue if row["bucket"] == "overdue" else expiring).append(item)
        return {"expiring": expiring, "overdue": overdue}


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
