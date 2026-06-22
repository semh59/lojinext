"""Repository for ML model version metadata (`model_versiyonlar` table)."""

from __future__ import annotations

from typing import Any, List, Optional, cast

from sqlalchemy import desc, select, update

from app.database.base_repository import BaseRepository
from app.database.models import ModelVersiyon


class ModelVersiyonRepository(BaseRepository[ModelVersiyon]):
    """Versioning, rollback and active-version selection for ML models."""

    model = ModelVersiyon

    async def get_latest_version(self, arac_id: int) -> Optional[ModelVersiyon]:
        stmt = (
            select(self.model)
            .where(self.model.arac_id == arac_id)
            .order_by(desc(self.model.versiyon))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_active_version(self, arac_id: int) -> Optional[ModelVersiyon]:
        stmt = (
            select(self.model)
            .where(self.model.arac_id == arac_id, self.model.aktif.is_(True))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_all_for_vehicle(
        self, arac_id: int, limit: int = 50
    ) -> List[ModelVersiyon]:
        stmt = (
            select(self.model)
            .where(self.model.arac_id == arac_id)
            .order_by(desc(self.model.versiyon))
            .limit(min(limit, self.MAX_LIMIT))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def activate(self, arac_id: int, version_id: int) -> bool:
        """Activate a single version, deactivating all others for that vehicle."""
        # Verify target exists before deactivating all — otherwise vehicle is left with no active model
        target = (
            await self.session.execute(
                select(self.model).where(
                    self.model.id == version_id, self.model.arac_id == arac_id
                )
            )
        ).scalar_one_or_none()
        if target is None:
            return False
        await self.session.execute(
            update(self.model).where(self.model.arac_id == arac_id).values(aktif=False)
        )
        result = await self.session.execute(
            update(self.model)
            .where(self.model.id == version_id, self.model.arac_id == arac_id)
            .values(aktif=True)
        )
        await self.session.flush()
        return cast("Any", result).rowcount > 0
