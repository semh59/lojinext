"""Use-case: single-use WebSocket connection ticket (Redis-backed, 60s TTL)."""

import uuid

from app.infrastructure.cache.redis_pubsub import set_redis_val
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def create_ws_ticket(user_email: str) -> str | None:
    """Redis'te bilet oluşturur, ticket id döner (Redis hatasında None)."""
    ticket_id = str(uuid.uuid4())

    success = await set_redis_val(f"ws_ticket:{ticket_id}", user_email, expire=60)
    if not success:
        logger.error(f"Failed to create WS ticket for {user_email}")
        return None

    logger.info(f"WS Ticket created for {user_email}: {ticket_id}")
    return ticket_id
