"""
Transactional Outbox Service
Ensures atomic event persistence and reliable delivery.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OutboxEvent
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.context.request_context import get_correlation_id
from app.infrastructure.events.event_bus import Event, get_event_bus
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.shutdown import is_stopping

logger = get_logger(__name__)


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

    def __init__(self, uow: Optional[UnitOfWork] = None):
        self.uow = uow

    async def save_event(
        self, event_type: str, payload: Dict[str, Any], uow: Optional[UnitOfWork] = None
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
        from app.database.unit_of_work import UnitOfWork

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
                    from app.infrastructure.events.event_types import EventType

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
