"""Use-case: update a fuel record (atomic)."""

from v2.modules.fuel.schemas import YakitUpdate
from v2.modules.platform_infra.public import (
    EventType,
    audit_log,
    get_logger,
    monitor_errors,
    publishes,
)
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@monitor_errors(category="yakit_write", severity="error")
@audit_log("UPDATE", "yakit")
@publishes(EventType.YAKIT_UPDATED)
async def update_yakit(yakit_id: int, data: YakitUpdate) -> bool:
    """Updates a fuel record (Atomic)."""
    try:
        async with UnitOfWork() as uow:
            current = await uow.yakit_repo.get_by_id(yakit_id, for_update=True)
            if not current:
                return False

            update_data = data.model_dump(exclude_unset=True)
            if not update_data:
                return True

            success = await uow.yakit_repo.update_yakit(yakit_id, **update_data)
            if success:
                await save_outbox_event(
                    uow.session,
                    EventType.YAKIT_UPDATED,
                    {"result": yakit_id, "arac_id": current.get("arac_id")},
                )
                await uow.commit()
                logger.info(f"Fuel record updated: ID {yakit_id}")
            return bool(success)
    except Exception as e:
        logger.error(f"Fuel update error: {e}")
        raise
