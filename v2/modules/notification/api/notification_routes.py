from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from v2.modules.auth_rbac.public import Kullanici, require_yetki
from v2.modules.notification.application.get_user_notifications import (
    get_user_notifications,
)
from v2.modules.notification.application.manage_notification_rules import (
    create_rule as create_rule_usecase,
)
from v2.modules.notification.application.manage_notification_rules import (
    delete_rule as delete_rule_usecase,
)
from v2.modules.notification.application.manage_notification_rules import (
    list_rules as list_rules_usecase,
)
from v2.modules.notification.application.manage_notification_rules import (
    update_rule as update_rule_usecase,
)
from v2.modules.notification.application.mark_all_notifications_read import (
    mark_all_as_read,
)
from v2.modules.notification.application.mark_notification_read import mark_as_read
from v2.modules.notification.schemas import (
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


class NotificationRuleUpdate(BaseModel):
    olay_tipi: Optional[str] = None
    kanallar: Optional[List[str]] = None
    alici_rol_id: Optional[int] = None
    aktif: Optional[bool] = None


@router.get(
    "/rules",
    response_model=List[NotificationRuleResponse],
    dependencies=[Depends(require_yetki("notification_rule_goruntule"))],
)
async def list_rules() -> List[NotificationRuleResponse]:
    """Admin: list every notification rule."""
    rules = await list_rules_usecase()
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
    rule = await create_rule_usecase(data.model_dump())
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


@router.patch(
    "/rules/{rule_id}",
    response_model=NotificationRuleResponse,
    dependencies=[Depends(require_yetki(["notification_rule_duzenle", "all", "*"]))],
)
async def update_rule(
    rule_id: int,
    data: NotificationRuleUpdate,
    current_user: Kullanici = Depends(get_current_active_user),
) -> NotificationRuleResponse:
    """Admin: partially update a notification rule (e.g. toggle aktif)."""
    changes = data.model_dump(exclude_unset=True)
    rule = await update_rule_usecase(rule_id, changes)
    if rule is None:
        raise HTTPException(status_code=404, detail="Bildirim kuralı bulunamadı.")
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="notification.rule_updated",
            module="notifications",
            entity_id=str(rule_id),
            user_id=user_id,
            new_value=changes,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)
    return NotificationRuleResponse.model_validate(rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_yetki(["notification_rule_sil", "all", "*"]))],
)
async def delete_rule(
    rule_id: int,
    current_user: Kullanici = Depends(get_current_active_user),
) -> None:
    """Admin: delete a notification rule."""
    deleted = await delete_rule_usecase(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bildirim kuralı bulunamadı.")
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="notification.rule_deleted",
            module="notifications",
            entity_id=str(rule_id),
            user_id=user_id,
            new_value=None,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)


@router.get("/my", response_model=List[NotificationItemResponse])
async def get_my_notifications(
    current_user: Kullanici = Depends(get_current_active_user),
) -> List[NotificationItemResponse]:
    """User: notifications for the logged-in user."""
    notifications = await get_user_notifications(current_user.id)
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
    count = await mark_all_as_read(current_user.id)
    return MarkAllReadResponse(success=True, count=count)


@router.patch("/{notification_id}/read", response_model=MarkSingleReadResponse)
async def mark_single_read(
    notification_id: int,
    current_user: Kullanici = Depends(get_current_active_user),
) -> MarkSingleReadResponse:
    """User: mark a single notification as read."""
    success = await mark_as_read(notification_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    return MarkSingleReadResponse(success=True)
