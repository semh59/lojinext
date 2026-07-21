import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import HTTPException

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.admin_platform.public import training_ws_manager
from v2.modules.prediction_ml.infrastructure.models import EgitimKuyrugu, ModelVersiyon

logger = get_logger(__name__)


class MLService:
    """
    Service for managing ML model training tasks and version registration.
    Includes [B-21] Async Lock to prevent concurrent sessions for the same vehicle.
    """

    _locks: Dict[int, asyncio.Lock] = {}

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def schedule_training(
        self, arac_id: int, user_id: Optional[int] = None
    ) -> EgitimKuyrugu:
        """
        Schedules a new model training task with concurrency protection.
        """
        # setdefault is GIL-atomic in CPython — safe without an extra guard lock.
        lock = MLService._locks.setdefault(arac_id, asyncio.Lock())

        async with lock:
            # NOTE: do NOT re-enter `async with self.uow:` here. `self.uow`
            # is already active — it was entered by the caller (the
            # endpoint) before constructing this service. Re-entering the
            # SAME UnitOfWork instance a second time makes
            # `UnitOfWork.__aenter__` treat it as a non-owning/nested
            # context (it only checks `self._session is not None`, not
            # actual reentrancy depth), which flips `_owns` to False even
            # for a UnitOfWork that started out owning its session. That
            # made `await self.uow.commit()` below a silent no-op — the new
            # task was `add()`-ed but never actually persisted, and
            # id/ilerleme/olusturma stayed None on the returned object
            # (confirmed via curl: POST /admin/ml/train/{id} 500'd with a
            # ResponseValidationError on those exact fields).
            active_tasks = await self.uow.ml_training_repo.get_active_tasks_for_vehicle(
                arac_id
            )
            if active_tasks:
                raise HTTPException(
                    status_code=400,
                    detail="An active training task already exists for this vehicle.",
                )

            latest_version = await self.uow.model_versiyon_repo.get_latest_version(
                arac_id
            )
            next_version = 1 if latest_version is None else latest_version.versiyon + 1

            new_task = EgitimKuyrugu(
                arac_id=arac_id,
                hedef_versiyon=next_version,
                durum="WAITING",
                tetikleyen_kullanici_id=user_id,
            )
            self.uow.session.add(new_task)
            await self.uow.commit()
            await self.uow.session.refresh(new_task)

            logger.info(
                f"Training scheduled for vehicle {arac_id} (Version {next_version})"
            )
            return new_task

    async def update_task_progress(
        self,
        task_id: int,
        ilerleme: float,
        durum: str,
        is_error: bool = False,
        error_detail: Optional[str] = None,
    ):
        """Updates the status and progress of a training task.

        NOT: ``self.uow`` çağıran tarafça (endpoint/dependency) zaten
        `async with` içinde açılmış olarak enjekte edilir — burada ikinci
        kez `async with self.uow:` yapmak aynı instance'ı yeniden açar ve
        connection-pool leak'ine yol açar (bkz. `schedule_training`
        üstündeki NOT + TASKS/bug-connection-pool-leak-under-load.md).
        """
        # Need the session-tracked ORM row (not the repo's dict projection)
        # so the attribute writes below actually persist on commit.
        task = await self.uow.session.get(EgitimKuyrugu, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Training task not found.")

        task.ilerleme = ilerleme
        task.durum = durum
        if is_error:
            task.hata_detay = error_detail

        now = datetime.now(timezone.utc)
        if durum in ["RUNNING", "COMPLETED", "FAILED"]:
            task.guncelleme = now
            if durum == "RUNNING" and not task.baslangic_zaman:
                task.baslangic_zaman = now
            if durum in ["COMPLETED", "FAILED"]:
                task.bitis_zaman = now

        await self.uow.commit()

        # Broadcast update via WebSocket
        await training_ws_manager.broadcast(
            {
                "type": "progress",
                "task_id": task_id,
                "arac_id": task.arac_id,
                "ilerleme": ilerleme,
                "durum": durum,
                "error": is_error,
                "detail": error_detail,
            }
        )

    async def get_training_queue(self, limit: int = 50) -> list:
        """Return recent training tasks ordered by newest first."""
        from sqlalchemy import select as sa_select

        stmt = sa_select(EgitimKuyrugu).order_by(EgitimKuyrugu.id.desc()).limit(limit)
        result = await self.uow.session.execute(stmt)
        return list(result.scalars().all())

    async def register_model_version(
        self,
        arac_id: int,
        versiyon: int,
        metrics: Dict,
        model_dosya_yolu: str,
        kullanilan_ozellikler: Dict,
        veri_sayisi: int,
    ) -> ModelVersiyon:
        """Register a new trained model version in the database."""
        model_ver = ModelVersiyon(
            arac_id=arac_id,
            versiyon=versiyon,
            veri_sayisi=veri_sayisi,
            r2_skoru=metrics.get("r2_skoru"),
            mae=metrics.get("mae"),
            mape=metrics.get("mape"),
            rmse=metrics.get("rmse"),
            model_dosya_yolu=model_dosya_yolu,
            kullanilan_ozellikler=kullanilan_ozellikler,
        )
        self.uow.session.add(model_ver)
        await self.uow.commit()
        logger.info(f"Model version registered: arac_id={arac_id}, version={versiyon}")
        return model_ver
