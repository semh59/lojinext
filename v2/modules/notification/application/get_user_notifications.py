from __future__ import annotations

from typing import List

from v2.modules.notification.infrastructure.models import BildirimGecmisi
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_user_notifications(user_id: int) -> List[BildirimGecmisi]:
    """Fetch unread or recent notifications for the logged-in user."""
    async with UnitOfWork() as uow:
        return await uow.notification_repo.get_user_notifications(user_id)
