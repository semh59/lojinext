from __future__ import annotations

from app.database.unit_of_work import UnitOfWork


async def mark_as_read(notification_id: int, user_id: int) -> bool:
    """Mark a single notification as read, scoped to its owner.

    Ownership check (IDOR guard): updates only when the notification
    belongs to ``user_id``. Returns False if it does not exist or is not
    owned by the caller.
    """
    async with UnitOfWork() as uow:
        success = await uow.notification_repo.mark_as_read_for_user(
            notification_id, user_id
        )
        if success:
            await uow.commit()
        return success
