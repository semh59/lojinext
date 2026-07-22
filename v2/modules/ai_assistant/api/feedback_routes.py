"""Faz 11 — pilot kullanıcı geri bildirimi.

POST /feedback : authenticated kullanıcı mesajını Telegram OPS kanalına iletir
(best-effort; teslim hatası 202'yi bozmaz — UI engellenmez).
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from v2.modules.auth_rbac.public import Kullanici, get_current_active_user
from v2.modules.notification.public import notify_feedback
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    page: Optional[str] = Field(None, max_length=200)


@router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
    responses={202: {"description": "Kabul edildi — gövde yok (best-effort teslim)."}},
    response_model=None,
    response_class=Response,
)
async def submit_feedback(
    payload: FeedbackRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> Response:
    """Pilot geri bildirimi → Telegram OPS (best-effort)."""
    username = getattr(current_user, "kullanici_adi", "") or getattr(
        current_user, "username", ""
    )
    delivered = await notify_feedback(
        message=payload.message,
        username=str(username),
        page=payload.page or "",
    )
    if not delivered:
        logger.info("Pilot feedback alındı ama OPS teslimi başarısız (best-effort).")
    return Response(status_code=status.HTTP_202_ACCEPTED)
