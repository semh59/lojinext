from __future__ import annotations

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def mark_all_as_read(user_id: int) -> int:
    """Mark all notifications of a user as read."""
    async with UnitOfWork() as uow:
        count = await uow.notification_repo.mark_all_as_read(user_id)
        if count > 0:
            await uow.commit()
        return count
