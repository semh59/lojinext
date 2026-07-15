from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.database.models import Kullanici
from v2.modules.auth_rbac.application.create_ws_ticket import (
    create_ws_ticket as create_ws_ticket_usecase,
)

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
    ticket_id = await create_ws_ticket_usecase(current_user.email)

    if ticket_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bilet oluşturulamadı (Redis hatası)",
        )

    return TicketResponse(ticket=ticket_id)
