"""Transactional Outbox — ORM tablosu + servis.

``app/database/models.py`` bölünmesi (dalga 16, task #58) — bu tablo hiçbir
tek iş modülüne ait değil, TÜM modüllerin `save_outbox_event`/
`get_outbox_service` çağırdığı gerçekten paylaşılan altyapı (driver/trip/
fuel/location/fleet — grep ile doğrulandı). Bu yüzden bir iş modülüne
zorla atanmak yerine shared_kernel'e taşındı — event_bus.py/audit_logger.py
ile aynı kategori, ama o ikisinden farklı olarak bu tablonun gerçek tek
sahibi (eski ``app/infrastructure/events/outbox_service.py``, bu taşımayla
silindi) küçük ve self-contained olduğu için hemen taşınabildi.

``event_bus.py``/``request_context``/``resilience``/``logging`` importları
henüz v2'ye taşınmamış ``app/infrastructure/`` altyapısına bağımlı kalıyor
(proje kararı: geçiş sırasında v2 modülleri geçici olarak eski app/
dosyalarına bağımlı olabilir — bu, o altyapı kendisi migrate olunca
(muhtemelen platform_infra/dalga 17) çözülecek).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from v2.modules.platform_infra.context.request_context import get_correlation_id
from v2.modules.platform_infra.events.event_bus import Event, get_event_bus
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.shutdown import is_stopping
from v2.modules.shared_kernel.infrastructure.base import Base, get_utc_now

logger = get_logger(__name__)


class OutboxEvent(Base):
    """Transactional Outbox for reliable event delivery."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("idx_outbox_processed", "processed"),
        Index("idx_outbox_created", "created_at"),
        {"schema": "platform"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)


async def save_outbox_event(
    session: AsyncSession, event_type: str, payload: Dict[str, Any]
) -> int:
    """Writes an OutboxEvent row via a raw session (same transaction as caller).

    Shared by ``OutboxService.save_event`` (``uow``-based callers) and
    modules whose use-cases only receive a bare repository (``repo.session``)
    rather than a full ``UnitOfWork`` — e.g. ``v2/modules/location``'s
    caller-owns-the-session convention.
    """
    correlation_id = get_correlation_id()

    db_event = OutboxEvent(
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id,
        created_at=datetime.now(timezone.utc),
        processed=False,
    )

    session.add(db_event)
    await session.flush()  # Ensure ID is generated

    logger.debug(f"Event saved to outbox: {event_type} [ID: {db_event.id}]")
    return db_event.id


class OutboxService:
    """Manages the transactional outbox patterns."""

    def __init__(self, uow: Optional[Any] = None):
        self.uow = uow

    async def save_event(
        self, event_type: str, payload: Dict[str, Any], uow: Optional[Any] = None
    ) -> int:
        """
        Saves an event to the outbox table within the current transaction.
        """
        active_uow = uow or self.uow
        if not active_uow:
            raise RuntimeError("OutboxService requires a UnitOfWork to save events.")

        return await save_outbox_event(active_uow.session, event_type, payload)

    async def relay_pending_events(self, limit: int = 50):
        """
        Relays pending events to the EventBus.
        Called by a background worker or cron job.
        """
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            # Atomic fetch-and-lock pending events
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.processed.is_(False), OutboxEvent.retry_count < 5)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )

            result = await uow.session.execute(stmt)
            events = result.scalars().all()

            if not events:
                return 0

            bus = get_event_bus()
            processed_count = 0

            for db_event in events:
                if is_stopping():
                    logger.info(
                        "Shutdown requested, stopping outbox relay mid-batch..."
                    )
                    break

                try:
                    from v2.modules.platform_infra.events.event_types import EventType

                    event = Event(
                        type=EventType(db_event.event_type),
                        data=db_event.payload,
                        correlation_id=db_event.correlation_id,
                        event_id=str(db_event.id),
                    )

                    # publish_async catches handler exceptions internally — "processed"
                    # means "dispatched to bus", not "all handlers succeeded" (AUDIT-142).
                    await bus.publish_async(event)

                    db_event.processed = True
                    db_event.processed_at = datetime.now(timezone.utc)
                    processed_count += 1

                except Exception as e:
                    db_event.retry_count += 1
                    db_event.error_message = str(e)
                    logger.error(f"Failed to relay outbox event {db_event.id}: {e}")
                    if db_event.retry_count >= 5:
                        # Poison pill — max retries exceeded; drain from queue
                        db_event.processed = True
                        db_event.processed_at = datetime.now(timezone.utc)
                        logger.critical(
                            f"Outbox event {db_event.id} ({db_event.event_type}) "
                            f"permanently failed after {db_event.retry_count} retries "
                            f"— marked dead (DLQ replay not implemented)."
                        )

            await uow.commit()
            return processed_count


def get_outbox_service() -> OutboxService:
    return OutboxService()
