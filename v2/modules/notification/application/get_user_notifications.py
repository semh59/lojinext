from __future__ import annotations

from typing import List

from app.database.models import BildirimGecmisi
from app.database.unit_of_work import UnitOfWork


async def get_user_notifications(user_id: int) -> List[BildirimGecmisi]:
    """Fetch unread or recent notifications for the logged-in user."""
    async with UnitOfWork() as uow:
        return await uow.notification_repo.get_user_notifications(user_id)
