"""Sefer silme (soft delete) use-case'i."""


from app.infrastructure.audit import audit_log
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.platform_infra.events.event_bus import EventType, publishes
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.stats_refresh import refresh_stats

logger = get_logger(__name__)


@monitor_errors(category="sefer_write", severity="error")
@audit_log("DELETE", "sefer")
@publishes(EventType.SEFER_DELETED)
async def delete_sefer(sefer_id: int) -> bool:
    """Sefer sil (Soft Delete - Atomik)."""
    async with UnitOfWork() as uow:
        success = await delete_sefer_uow(uow, sefer_id)
        if success:
            await uow.commit()
            await refresh_stats(uow)
        return success


async def delete_sefer_uow(uow: UnitOfWork, sefer_id: int) -> bool:
    """Sefer silme mantığı (Paylaşımlı UoW destekli)."""
    try:
        # Soft delete by default, as per audit result
        success = await uow.sefer_repo.delete(sefer_id)
        if success:
            logger.info(f"Sefer silindi (Soft Deleted): ID {sefer_id}")
        return bool(success)
    except Exception as e:
        logger.error(f"Sefer silme hatasi (UoW): {e}")
        raise
