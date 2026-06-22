from datetime import timezone
from typing import Any, List, cast

from sqlalchemy import and_, select

from app.database.base_repository import BaseRepository
from app.database.models import BildirimGecmisi, BildirimKurali


class NotificationRepository(BaseRepository[BildirimGecmisi]):
    """Repository for managing notification rules and history."""

    model = BildirimGecmisi

    async def get_rules_by_event(self, event_type: str) -> List[BildirimKurali]:
        """Fetch active notification rules for a specific event type."""
        stmt = select(BildirimKurali).where(
            and_(BildirimKurali.olay_tipi == event_type, BildirimKurali.aktif.is_(True))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_notifications(
        self, kullanici_id: int, limit: int = 50
    ) -> List[BildirimGecmisi]:
        """Fetch recent notifications for a specific user."""
        stmt = (
            select(BildirimGecmisi)
            .where(BildirimGecmisi.kullanici_id == kullanici_id)
            .order_by(BildirimGecmisi.olusturma_tarihi.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_rules(self) -> List[BildirimKurali]:
        """Fetch all notification rules."""
        stmt = select(BildirimKurali)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_rule(self, rule_data: dict) -> BildirimKurali:
        """Create a new notification rule."""
        rule = BildirimKurali(**rule_data)
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def mark_as_read_for_user(self, notification_id: int, user_id: int) -> bool:
        """Mark a single notification as read only if it belongs to ``user_id``.

        Ownership-scoped to prevent IDOR: a row is updated only when both the
        id and the owner match. Returns True if a row was affected.
        """
        from datetime import datetime

        from sqlalchemy import update

        from app.database.models import BildirimDurumu

        stmt = (
            update(BildirimGecmisi)
            .where(
                and_(
                    BildirimGecmisi.id == notification_id,
                    BildirimGecmisi.kullanici_id == user_id,
                )
            )
            .values(durum=BildirimDurumu.READ, okundu_tarihi=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        return cast("Any", result).rowcount > 0

    async def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications for a user as read."""
        from datetime import datetime

        from sqlalchemy import update

        stmt = (
            update(BildirimGecmisi)
            .where(
                and_(
                    BildirimGecmisi.kullanici_id == user_id,
                    BildirimGecmisi.durum != "READ",
                )
            )
            .values(durum="READ", okundu_tarihi=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        return int(cast("Any", result).rowcount)
