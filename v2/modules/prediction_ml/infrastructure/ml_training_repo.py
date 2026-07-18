from typing import List

from sqlalchemy import select

from app.database.base_repository import BaseRepository
from app.database.models import EgitimKuyrugu


class MLTrainingRepository(BaseRepository[EgitimKuyrugu]):
    """
    Pure data access for ML Training Queue operations.
    """

    model = EgitimKuyrugu

    async def get_pending_tasks(self, limit: int = 10) -> List[EgitimKuyrugu]:
        """Fetch tasks waiting to be processed"""
        session = self.session
        stmt = (
            select(self.model)
            .where(self.model.durum == "WAITING")
            .order_by(self.model.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_tasks_for_vehicle(self, arac_id: int) -> List[EgitimKuyrugu]:
        """Fetch running/waiting tasks for a vehicle"""
        session = self.session
        stmt = select(self.model).where(
            self.model.arac_id == arac_id,
            self.model.durum.in_(["WAITING", "RUNNING"]),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
