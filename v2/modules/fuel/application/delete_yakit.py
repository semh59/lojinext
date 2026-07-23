"""Use-case: permanently delete a fuel record (hard delete)."""

from typing import Optional

from v2.modules.platform_infra.public import (
    EventType,
    get_logger,
    monitor_errors,
    publishes,
)
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@monitor_errors(category="yakit_write", severity="error")
@publishes(EventType.YAKIT_DELETED)
async def delete_yakit(yakit_id: int, deleted_by_id: Optional[int] = None) -> bool:
    """Permanently deletes a fuel record (Hard Delete)."""
    from v2.modules.platform_infra.public import log_audit_event

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
                await save_outbox_event(
                    uow.session,
                    EventType.YAKIT_DELETED,
                    {"result": yakit_id, "arac_id": current.get("arac_id")},
                )
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
