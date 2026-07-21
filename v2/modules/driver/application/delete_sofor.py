"""Use-case: soft-delete a driver (single + bulk)."""

from typing import Any, Dict, List

from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@publishes(EventType.SOFOR_DELETED)
async def delete_sofor(sofor_id: int) -> bool:
    """Deletes a driver (Soft Delete Standard)."""
    async with UnitOfWork() as uow:
        success = await _delete_sofor_uow(uow, sofor_id)
        if success:
            await save_outbox_event(
                uow.session, EventType.SOFOR_DELETED, {"result": sofor_id}
            )
            await uow.commit()
        return success


async def _delete_sofor_uow(uow: UnitOfWork, sofor_id: int) -> bool:
    """Transactional soft delete logic (Shared UoW)."""
    # include_inactive=True: bu idempotent silme guard'ı, zaten
    # pasif/silinmiş bir kaydı görüp çift-silmeyi engellemesi gerekiyor.
    current = await uow.sofor_repo.get_by_id(
        sofor_id, for_update=True, include_inactive=True
    )
    if not current or current.get("is_deleted"):
        return False

    success = await uow.sofor_repo.update(sofor_id, is_deleted=True, aktif=False)
    if success:
        logger.info(f"Driver soft-deleted: ID {sofor_id}")
    return bool(success)


async def bulk_delete(ids: List[int]) -> Dict[str, Any]:
    """Bulk delete drivers (Transaction isolated)."""
    if not ids:
        return {"deleted": 0, "errors": []}

    async with UnitOfWork() as uow:
        count = await uow.sofor_repo.bulk_soft_delete(ids)
        await uow.commit()

        logger.info(f"Bulk drivers deleted: {count} entries")
        return {"deleted": count, "total": len(ids), "status": "success"}
