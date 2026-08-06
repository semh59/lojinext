"""Minimal local session-scope helper for this service's OWN tables.

`v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork` cannot
be used here (Task 5, 2026-08-04 finding): it imports 13 business
modules' repository classes at module level (the whole point of that
class is exposing every module's repo as a lazy property) -- none of
those packages exist in this service's own Docker image. This class is
a deliberately narrower replacement: one session per `async with` block,
plus this service's OWN two repos (`model_versiyonlar`/`egitim_kuyrugu`
-- tables this service, not any other module, owns). No contextvar
session-sharing/nesting/ghost-transaction detection -- this service has
no other UoW users to nest with, unlike the main backend's 15-module
monolith.

Cross-module data (fleet/driver/trip/analytics_executive/ai_assistant)
never goes through this class -- see `cross_module_client.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.platform_infra.database.connection import AsyncSessionLocal

if TYPE_CHECKING:
    from prediction_ml_service.infrastructure.ml_training_repo import (
        MLTrainingRepository,
    )
    from prediction_ml_service.infrastructure.model_versiyon_repo import (
        ModelVersiyonRepository,
    )


class ServiceUnitOfWork:
    """Async session scope + this service's own repos. Commit is explicit."""

    def __init__(self) -> None:
        self.session: Optional[AsyncSession] = None
        self._ml_training_repo: Optional["MLTrainingRepository"] = None
        self._model_versiyon_repo: Optional["ModelVersiyonRepository"] = None

    async def __aenter__(self) -> "ServiceUnitOfWork":
        self.session = AsyncSessionLocal()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self.session is not None
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        assert self.session is not None
        await self.session.commit()

    async def rollback(self) -> None:
        assert self.session is not None
        await self.session.rollback()

    @property
    def ml_training_repo(self) -> "MLTrainingRepository":
        if self._ml_training_repo is None:
            from prediction_ml_service.infrastructure.ml_training_repo import (
                MLTrainingRepository,
            )

            self._ml_training_repo = MLTrainingRepository(self.session)
        return self._ml_training_repo

    @property
    def model_versiyon_repo(self) -> "ModelVersiyonRepository":
        if self._model_versiyon_repo is None:
            from prediction_ml_service.infrastructure.model_versiyon_repo import (
                ModelVersiyonRepository,
            )

            self._model_versiyon_repo = ModelVersiyonRepository(self.session)
        return self._model_versiyon_repo
