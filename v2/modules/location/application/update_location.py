"""Use-case: update an existing location/route record."""

from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.events.outbox_service import save_outbox_event
from app.infrastructure.logging.logger import get_logger
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonUpdate

logger = get_logger(__name__)


@publishes(EventType.LOKASYON_UPDATED)
async def update_location(
    repo: LokasyonRepository, lokasyon_id: int, data: LokasyonUpdate
) -> bool:
    """Güzergah güncelle"""
    success = await repo.update(lokasyon_id, **data.model_dump(exclude_unset=True))
    if success:
        logger.info(f"Güzergah güncellendi: ID {lokasyon_id}")
        await save_outbox_event(
            repo.session, EventType.LOKASYON_UPDATED, {"result": lokasyon_id}
        )
    return success
