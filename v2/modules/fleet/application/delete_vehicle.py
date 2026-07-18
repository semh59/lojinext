"""Use-case: delete a vehicle (Smart Delete: Active->Passive, Passive->Hard Delete)."""

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.events.outbox_service import save_outbox_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.fleet.application.vehicle_event_log import log_vehicle_event

logger = get_logger(__name__)


@monitor_errors(category="arac_write", severity="error")
@publishes(EventType.ARAC_DELETED)
async def delete_vehicle(arac_id: int) -> bool:
    """Deletes a vehicle (Smart Delete: Active->Passive, Passive->Hard Delete)."""
    async with UnitOfWork() as uow:
        # include_inactive=True: bu smart-delete state machine, ikinci
        # çağrıda (aktif=False → hard-delete) zaten pasif kaydı görmesi
        # gerekiyor — kök soft-delete filtresi burada kasıtlı bypass edilir.
        current = await uow.arac_repo.get_by_id(arac_id, include_inactive=True)
        if not current:
            return False

        if current.get("aktif"):
            success = await uow.arac_repo.update(arac_id, aktif=False)
            if success:
                logger.info(f"Vehicle set to passive (Soft Deleted): ID {arac_id}")
                await log_vehicle_event(
                    arac_id,
                    "STATUS_CHANGE",
                    old_status="ACTIVE",
                    new_status="PASSIVE",
                    details="Soft deleted via delete_vehicle",
                    uow=uow,
                )
                await save_outbox_event(
                    uow.session, EventType.ARAC_DELETED, {"result": arac_id}
                )
                await uow.commit()
            return success
        else:
            try:
                success = await uow.arac_repo.hard_delete(arac_id)
                if success:
                    logger.info(
                        f"Vehicle permanently deleted (Hard Deleted): ID {arac_id}"
                    )
                    await save_outbox_event(
                        uow.session, EventType.ARAC_DELETED, {"result": arac_id}
                    )
                    await uow.commit()
                return success
            except Exception as e:
                logger.warning(f"Hard delete prevented (Dependent data): {e}")
                raise ValueError(
                    "This vehicle has active/archived trip or fuel records and cannot be permanently deleted. Keeping it passive is recommended."  # noqa: E501
                )


async def delete_all_vehicles() -> int:
    """Clears all vehicles (Admin Only)."""
    async with UnitOfWork() as uow:
        try:
            count = await uow.arac_repo.hard_delete_all()
            logger.info(f"All vehicles cleared: {count} entries")
            await uow.commit()
            return count
        except Exception as e:
            logger.error(f"Bulk delete error: {e}")
            raise ValueError("Some vehicles could not be deleted due to dependencies.")
