"""Event-subscriber use-case: SEFER_UPDATED / SLA_DELAY -> bildirim_gecmisi.

Was previously bundled into ``NotificationService`` (a stateful class whose
only state was ``self.event_bus``). Split out per B.1 (one file = one
use-case, see TASKS/modules/notification.md madde 3) — the register/handle
pair stays together in one file because they're two halves of a single
event-subscription use-case, not independent use-cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from v2.modules.notification.events import SeferUpdatedPayload, SlaDelayPayload
from v2.modules.notification.infrastructure.models import (
    BildirimDurumu,
    BildirimGecmisi,
)
from v2.modules.notification.infrastructure.ws_broadcaster import (
    notification_ws_manager,
)
from v2.modules.platform_infra.public import (
    Event,
    EventType,
    get_event_bus,
    get_logger,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


def register_handlers() -> None:
    """Register handle_event to listen for all critical events."""
    event_bus = get_event_bus()
    # EventBus.subscribe's Callable[[Event], None] annotation doesn't model
    # async handlers (repo-wide pattern — same gap in physics_handler.py,
    # cache_invalidation.py, rag_sync_service.py; those don't surface it
    # because mypy infers their bound-method/local-function callbacks more
    # loosely than this fully-typed top-level async function).
    event_bus.subscribe(EventType.SEFER_UPDATED, handle_event)  # type: ignore[arg-type]
    event_bus.subscribe(EventType.SLA_DELAY, handle_event)  # type: ignore[arg-type]
    # Add more event types as needed
    logger.info("notification handlers registered.")


async def handle_event(event: Event) -> None:
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

        header, content = _format_message(event)

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
                if user_email:
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
                    logger.info(f"UI Notification pushed to user {notif.kullanici_id}")
            elif notif.kanal == "EMAIL":
                logger.info(f"Email task queued for user {notif.kullanici_id}")


def _format_message(event: Event) -> tuple:
    """Construct human-readable header and content from event data."""
    if event.type == EventType.SEFER_UPDATED:
        sefer_payload = SeferUpdatedPayload.model_validate(event.data)
        header = f"Sefer Güncellendi: #{sefer_payload.sefer_id}"
        content = f"Sefer verileri '{sefer_payload.trigger}' nedeniyle güncellendi. Yakıt ve performans değerleri yeniden hesaplandı."  # noqa: E501
        return header, content

    if event.type == EventType.SLA_DELAY:
        delay_payload = SlaDelayPayload.model_validate(event.data)
        header = "📦 Lojistik Gecikme (SLA İhlali)"
        content = f"#{delay_payload.sefer_id} nolu seferde {delay_payload.delay_min} dakikalık gecikme tespit edildi. Teslimat hedefi aşıldı."  # noqa: E501
        return header, content

    if event.type == EventType.ANOMALY_DETECTED:
        header = "⚠️ Anomali Tespit Ediidi"
        content = event.data.get(
            "aciklama", "Sistemde sıra dışı bir veri tespit edildi."
        )
        return header, content

    return "Sistem Mesajı", str(event.data)
