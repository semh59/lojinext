"""Use-case: update driver details / manual score."""

from typing import Any

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.logging.logger import get_logger
from v2.modules.driver.application._locks import SOFOR_WRITE_LOCK
from v2.modules.driver.application.get_score import calculate_hybrid_score
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event

logger = get_logger(__name__)


@publishes(EventType.SOFOR_UPDATED)
async def update_sofor(sofor_id: int, **kwargs: Any) -> bool:
    """Updates driver details (UoW & Safe Name Change)."""
    async with UnitOfWork() as uow:
        current = await uow.sofor_repo.get_by_id(sofor_id)
        if current is None:
            # Driver doesn't exist, or exists but is currently passive/
            # soft-deleted. A generic update must not silently mutate a
            # deactivated driver's data (e.g. manual_score) — only an
            # explicit reactivation (aktif=True in kwargs) may proceed.
            if kwargs.get("aktif") is True:
                current = await uow.sofor_repo.get_by_id(
                    sofor_id, include_inactive=True
                )
            if current is None:
                return False

        if kwargs.get("ad_soyad"):
            ad_soyad = " ".join(
                word.capitalize() for word in kwargs["ad_soyad"].strip().split()
            )
            kwargs["ad_soyad"] = ad_soyad

            async with SOFOR_WRITE_LOCK:
                existing = await uow.sofor_repo.get_by_name(ad_soyad)
                if existing and existing["id"] != sofor_id:
                    raise ValueError("This name belongs to another driver.")

        if "manual_score" in kwargs:
            new_score = await calculate_hybrid_score(
                sofor_id, kwargs["manual_score"], uow=uow
            )
            kwargs["score"] = new_score

        success = await uow.sofor_repo.update(sofor_id, **kwargs)
        if success:
            logger.info(f"Driver updated: ID {sofor_id}")
            await save_outbox_event(
                uow.session, EventType.SOFOR_UPDATED, {"result": sofor_id}
            )
            await uow.commit()
        return bool(success)


async def update_score(sofor_id: int, score: float) -> bool:
    """Updates driver manual score and recalculates hybrid score."""
    if score < 0.1 or score > 2.0:
        raise ValueError("Score must be between 0.1 and 2.0")

    try:
        async with UnitOfWork() as uow:
            async with SOFOR_WRITE_LOCK:
                current = await uow.sofor_repo.get_by_id(sofor_id)
                if not current:
                    raise ValueError("Driver not found")

                hybrid_score = await calculate_hybrid_score(sofor_id, score, uow=uow)

                success = await uow.sofor_repo.update(
                    sofor_id, manual_score=score, score=hybrid_score
                )
                if success:
                    await uow.commit()
                    logger.info(
                        f"Driver scores updated: ID {sofor_id} | Manual: {score}, Hybrid: {hybrid_score}"
                    )
        return bool(success)
    except Exception as e:
        logger.error(f"Score update error: {e}")
        raise
