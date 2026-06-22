from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.core.services.notification_service import NotificationService
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.permission_checker import require_yetki
from app.schemas.api_responses import (
    MarkAllReadResponse,
    MarkSingleReadResponse,
    NotificationItemResponse,
    NotificationRuleResponse,
)

logger = get_logger(__name__)

router = APIRouter()


class NotificationRuleCreate(BaseModel):
    olay_tipi: str
    kanallar: List[str]
    alici_rol_id: int
    aktif: bool = True


@router.get(
    "/rules",
    response_model=List[NotificationRuleResponse],
    dependencies=[Depends(require_yetki("notification_rule_goruntule"))],
)
async def list_rules() -> List[NotificationRuleResponse]:
    """Admin: list every notification rule."""
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        rules = await uow.notification_repo.get_all_rules()
        return [NotificationRuleResponse.model_validate(rule) for rule in rules]


@router.post(
    "/rules",
    response_model=NotificationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_yetki(["notification_rule_ekle", "all", "*"]))],
)
async def create_rule(
    data: NotificationRuleCreate,
    current_user: Kullanici = Depends(get_current_active_user),
) -> NotificationRuleResponse:
    """Admin: create a new notification rule."""
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        rule = await uow.notification_repo.create_rule(data.model_dump())
        await uow.commit()
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="notification.rule_created",
            module="notifications",
            entity_id=None,
            user_id=user_id,
            new_value=data.model_dump(),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)
    return NotificationRuleResponse.model_validate(rule)


@router.get("/my", response_model=List[NotificationItemResponse])
async def get_my_notifications(
    current_user: Kullanici = Depends(get_current_active_user),
) -> List[NotificationItemResponse]:
    """User: notifications for the logged-in user."""
    service = NotificationService()
    notifications = await service.get_user_notifications(current_user.id)
    return [
        NotificationItemResponse(
            id=n.id,
            baslik=n.baslik,
            icerik=n.icerik,
            olay_tipi=n.olay_tipi,
            kanal=n.kanal,
            durum=n.durum,
            okundu=n.durum == "READ",
            olusturma_tarihi=n.olusturma_tarihi.isoformat(),
        )
        for n in notifications
    ]


@router.post("/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_read(
    current_user: Kullanici = Depends(get_current_active_user),
) -> MarkAllReadResponse:
    """User: mark every notification as read."""
    service = NotificationService()
    count = await service.mark_all_as_read(current_user.id)
    return MarkAllReadResponse(success=True, count=count)


@router.patch("/{notification_id}/read", response_model=MarkSingleReadResponse)
async def mark_single_read(
    notification_id: int,
    current_user: Kullanici = Depends(get_current_active_user),
) -> MarkSingleReadResponse:
    """User: mark a single notification as read."""
    service = NotificationService()
    success = await service.mark_as_read(notification_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    return MarkSingleReadResponse(success=True)
