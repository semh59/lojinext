"""Reports v2 RV2.PWA — Web Push endpoint'leri.

Plan §7.2:
- GET /push/vapid-public-key — frontend subscribe için public key
- POST /push/subscribe — subscription kaydı (upsert by endpoint)
- DELETE /push/subscribe?endpoint=... — subscription sil
- POST /push/test — admin test push gönderir
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_active_admin, get_current_active_user
from app.config import settings
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.notification.application.manage_push_subscription import (
    subscribe_push,
    unsubscribe_push,
)
from v2.modules.notification.application.send_push_to_user import send_push_to_user
from v2.modules.notification.schemas import (
    PushSendResult,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    PushTestRequest,
    VapidPublicKeyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
async def get_vapid_public_key(
    _current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> VapidPublicKeyResponse:
    """Frontend subscribe için VAPID public key.

    push_enabled False ise frontend abone olmamalı.
    """
    push_enabled = bool(
        settings.VAPID_PUBLIC_KEY
        and settings.VAPID_PRIVATE_KEY
        and settings.PUSH_NOTIFICATION_ENABLED
    )
    return VapidPublicKeyResponse(
        public_key=settings.VAPID_PUBLIC_KEY,
        push_enabled=push_enabled,
    )


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=201,
)
async def subscribe(
    payload: PushSubscriptionRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> PushSubscriptionResponse:
    """Yeni subscription kaydı (endpoint unique → upsert)."""
    if not settings.PUSH_NOTIFICATION_ENABLED:
        raise HTTPException(status_code=503, detail="Push bildirimleri devre dışı")

    # Sentetik (break-glass) süper admin — id<=0 — kullanicilar tablosunda
    # gerçek bir satıra karşılık gelmiyor (bkz app/api/deps.py). user_id FK'si
    # NOT NULL + kullanicilar(id) referanslı olduğu için bu id ile insert
    # denemek yakalanmamış bir FK ihlaline ve opak 500'e düşüyordu (bulundu
    # 0-mock epiği sırasında). preferences.py'deki aynı desenle erken ve
    # açık bir 403 döndür.
    if not current_user.id or current_user.id <= 0:
        raise HTTPException(
            status_code=403, detail="Sistem kullanıcısı push aboneliği oluşturamaz"
        )

    sub = await subscribe_push(
        current_user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=payload.user_agent,
    )
    return PushSubscriptionResponse.model_validate(sub)


@router.delete("/subscribe", status_code=204)
async def unsubscribe(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    endpoint: str = Query(..., min_length=10),
) -> None:
    """Bir endpoint için subscription sil — yalnız kendi kayıtları."""
    await unsubscribe_push(current_user.id, endpoint)


@router.post("/test", response_model=PushSendResult)
async def send_test_push(
    payload: PushTestRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
) -> PushSendResult:
    """Admin debugging — current_user'a test push gönderir."""
    if not settings.PUSH_NOTIFICATION_ENABLED:
        raise HTTPException(status_code=503, detail="Push bildirimleri devre dışı")

    return await send_push_to_user(
        current_user.id,
        title=payload.title,
        body=payload.body,
        url=payload.url,
    )
