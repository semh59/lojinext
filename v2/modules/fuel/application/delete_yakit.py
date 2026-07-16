"""Use-case: permanently delete a fuel record (hard delete)."""

from typing import Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors

logger = get_logger(__name__)


@monitor_errors(category="yakit_write", severity="error")
@publishes(EventType.YAKIT_DELETED)
async def delete_yakit(yakit_id: int, deleted_by_id: Optional[int] = None) -> bool:
    """Permanently deletes a fuel record (Hard Delete)."""
    from app.infrastructure.audit.audit_logger import log_audit_event

    try:
        async with UnitOfWork() as uow:
            # include_inactive=True: hard-delete zaten pasif (aktif=False)
            # kaydı da kalıcı olarak silebilmeli — aksi halde soft-delete
            # edilmiş bir kayıt bu API üzerinden hiç hard-delete edilemez.
            current = await uow.yakit_repo.get_by_id(yakit_id, include_inactive=True)
            if not current:
                return False

            success = await uow.yakit_repo.hard_delete(yakit_id)
            if success:
                await uow.commit()
                logger.info(
                    f"Fuel record permanently deleted (Hard Delete): ID {yakit_id}"
                )
                await log_audit_event(
                    action="yakit_hard_delete",
                    module="yakit",
                    entity_id=str(yakit_id),
                    user_id=deleted_by_id,
                    details={
                        "arac_id": current.get("arac_id"),
                        "tarih": str(current.get("tarih")),
                        "litre": str(current.get("litre")),
                        "toplam_tutar": str(current.get("toplam_tutar")),
                    },
                )
            return bool(success)

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Fuel deletion error: {e}")
        raise ValueError("An error occurred while deleting fuel entry.")
