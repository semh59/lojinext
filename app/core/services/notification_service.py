from datetime import datetime, timezone
from typing import List

from app.database.models import BildirimDurumu, BildirimGecmisi
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import Event, EventType, get_event_bus
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Imported lazily inside handle_event to avoid circular imports at module level,
# but exposed here for patching in tests.
try:
    from app.api.v1.endpoints.admin_ws import notification_ws_manager
except Exception:  # pragma: no cover
    notification_ws_manager = None  # type: ignore[assignment]


class NotificationService:
    """Service for processing system events and delivering notifications."""

    def __init__(self):
        self.event_bus = get_event_bus()

    def register_handlers(self):
        """Register the service to listen for all critical events."""
        self.event_bus.subscribe(EventType.SEFER_UPDATED, self.handle_event)
        self.event_bus.subscribe(EventType.SLA_DELAY, self.handle_event)
        # Add more event types as needed
        logger.info("NotificationService handlers registered.")

    async def handle_event(self, event: Event):
        """Process an incoming event and create notifications based on rules.

        Uses a single bulk query for all role IDs to avoid the N+1 pattern that
        previously issued one query per notification rule.
        """
        async with UnitOfWork() as uow:
            rules = await uow.notification_repo.get_rules_by_event(event.type)
            if not rules:
                return

            # 1. Collect unique role IDs across all rules and fetch users in one query.
            rol_ids = list({rule.alici_rol_id for rule in rules})
            users_by_rol = await uow.kullanici_repo.get_by_rol_ids(rol_ids)

            header, content = self._format_message(event)

            # 2. Build all notification records in memory.
            notifications: List[BildirimGecmisi] = []
            for rule in rules:
                users = users_by_rol.get(rule.alici_rol_id, [])
                for user in users:
                    for channel in rule.kanallar:
                        # EMAIL delivery is a log-only stub; mark FAILED so
                        # dashboards don't show false delivery success.
                        initial_durum = (
                            BildirimDurumu.SENT
                            if channel == "UI"
                            else BildirimDurumu.FAILED
                        )
                        notifications.append(
                            BildirimGecmisi(
                                kullanici_id=user.id,
                                baslik=header,
                                icerik=content,
                                olay_tipi=event.type.value,
                                kanal=channel,
                                durum=initial_durum,
                            )
                        )

            # 3. Persist all records in a single statement.
            if notifications:
                uow.session.add_all(notifications)
                await uow.session.flush()

            await uow.commit()

            # 4. Channel-specific delivery (WebSocket / email queuing).
            # Done AFTER commit so DB rows are visible when clients re-query.
            for notif in notifications:
                user_email = next(
                    (
                        u.email
                        for rule in rules
                        for u in users_by_rol.get(rule.alici_rol_id, [])
                        if u.id == notif.kullanici_id
                    ),
                    None,
                )
                if notif.kanal == "UI":
                    if notification_ws_manager is not None and user_email:
                        await notification_ws_manager.send_personal_message(
                            {
                                "type": "notification",
                                "data": {
                                    "id": notif.id,
                                    "baslik": header,
                                    "icerik": content,
                                    "olay_tipi": event.type.value,
                                    "olusturma_tarihi": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                },
                            },
                            user_email,
                        )
                        logger.info(
                            f"UI Notification pushed to user {notif.kullanici_id}"
                        )
                elif notif.kanal == "EMAIL":
                    logger.info(f"Email task queued for user {notif.kullanici_id}")

    def _format_message(self, event: Event) -> tuple:
        """Construct human-readable header and content from event data."""
        if event.type == EventType.SEFER_UPDATED:
            sefer_id = event.data.get("sefer_id")
            trigger = event.data.get("trigger")
            header = f"Sefer Güncellendi: #{sefer_id}"
            content = f"Sefer verileri '{trigger}' nedeniyle güncellendi. Yakıt ve performans değerleri yeniden hesaplandı."  # noqa: E501
            return header, content

        if event.type == EventType.SLA_DELAY:
            sefer_id = event.data.get("sefer_id")
            delay_min = event.data.get("delay_min", 0)
            header = "📦 Lojistik Gecikme (SLA İhlali)"
            content = f"#{sefer_id} nolu seferde {delay_min} dakikalık gecikme tespit edildi. Teslimat hedefi aşıldı."
            return header, content

        if event.type == EventType.ANOMALY_DETECTED:
            header = "⚠️ Anomali Tespit Ediidi"
            content = event.data.get(
                "aciklama", "Sistemde sıra dışı bir veri tespit edildi."
            )
            return header, content

        return "Sistem Mesajı", str(event.data)

    async def get_user_notifications(self, user_id: int) -> List[BildirimGecmisi]:
        """Fetch unread or recent notifications for the logged-in user."""
        async with UnitOfWork() as uow:
            return await uow.notification_repo.get_user_notifications(user_id)

    async def mark_as_read(self, notification_id: int, user_id: int) -> bool:
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

    async def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications of a user as read."""
        async with UnitOfWork() as uow:
            count = await uow.notification_repo.mark_all_as_read(user_id)
            if count > 0:
                await uow.commit()
            return count
