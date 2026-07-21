from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base_repository import BaseRepository
from v2.modules.import_excel.infrastructure.models import IceriAktarimGecmisi


class ImportHistoryRepository(BaseRepository[IceriAktarimGecmisi]):
    """Repository for managing IceriAktarimGecmisi records."""

    model = IceriAktarimGecmisi

    def __init__(self, session: AsyncSession):
        super().__init__(session=session)

    async def create_import_job(self, data: Dict[str, Any]) -> IceriAktarimGecmisi:
        """Create a new import job tracking record.

        Returns the ORM instance (not just the id) so callers can read
        ``job.id`` after the surrounding ``flush()``.
        """
        physical_columns = {c.name for c in self.model.__table__.columns}
        obj = self.model(**{k: v for k, v in data.items() if k in physical_columns})
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_id(self, history_id: int) -> Optional[IceriAktarimGecmisi]:  # type: ignore[override]
        return await self.session.get(self.model, history_id)

    async def get_recent_jobs(self, limit: int = 50) -> List[IceriAktarimGecmisi]:
        """Fetch recent import jobs for administrative audit."""
        stmt = (
            select(IceriAktarimGecmisi)
            .order_by(IceriAktarimGecmisi.baslama_zamani.desc())
            .limit(limit)
        )
        async with self._get_session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_job_status(
        self, history_id: int, durum: str, **kwargs: Any
    ) -> bool:
        """Update job statistics and status safely."""
        return await self.update(history_id, durum=durum, **kwargs)


def get_import_history_repo(session: AsyncSession) -> ImportHistoryRepository:
    return ImportHistoryRepository(session)
