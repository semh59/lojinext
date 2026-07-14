import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.database.models import Kullanici
from app.infrastructure.cache.redis_pubsub import set_redis_val
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class TicketResponse(BaseModel):
    ticket: str
    expires_in: int = 60


@router.post("/ticket", response_model=TicketResponse)
async def create_ws_ticket(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    WebSocket bağlantısı için tek kullanımlık bilet oluşturur.
    Bilet 60 saniye geçerlidir.
    """
    ticket_id = str(uuid.uuid4())

    # Bileti Redis'te sakla (Key: ws_ticket:ID, Value: Kullanıcı Adı)
    success = await set_redis_val(
        f"ws_ticket:{ticket_id}", current_user.email, expire=60
    )

    if not success:
        logger.error(f"Failed to create WS ticket for {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bilet oluşturulamadı (Redis hatası)",
        )

    logger.info(f"WS Ticket created for {current_user.email}: {ticket_id}")
    return TicketResponse(ticket=ticket_id)
