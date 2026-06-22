"""Reports v2 RV2.PWA — Web Push abonelik schema'ları.

Plan §7.2 — frontend `PushSubscription.toJSON()` çıktısını karşılar.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PushSubscriptionKeys(BaseModel):
    """Browser PushSubscription.toJSON() içindeki `keys` objesi."""

    p256dh: str = Field(..., min_length=10)
    auth: str = Field(..., min_length=4)


class PushSubscriptionRequest(BaseModel):
    """POST /push/subscribe gövdesi — browser toJSON çıktısı."""

    endpoint: str = Field(..., min_length=10, max_length=2048)
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = Field(None, max_length=200)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint_https(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("Push endpoint must use HTTPS")
        if not parsed.netloc:
            raise ValueError("Push endpoint must be an absolute URL")
        return v


class PushSubscriptionResponse(BaseModel):
    """Subscription kaydı sonrası response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class VapidPublicKeyResponse(BaseModel):
    """GET /push/vapid-public-key response."""

    public_key: str = Field(..., description="Base64url-encoded VAPID public key")
    push_enabled: bool = Field(
        ..., description="True ise sunucu push gönderebilir (anahtar setli + flag açık)"
    )


class PushTestRequest(BaseModel):
    """POST /push/test gövdesi (admin debug)."""

    title: str = Field("LojiNext Test", max_length=80)
    body: str = Field("Push bildirimi çalışıyor.", max_length=200)
    url: Optional[str] = Field(None, max_length=200)


class PushSendResult(BaseModel):
    """Push gönderim özet sonucu."""

    sent: int = Field(..., description="Başarılı gönderim sayısı")
    expired: int = Field(0, description="410 Gone → silinen subscription sayısı")
    failed: int = Field(0, description="Diğer hata sayısı")
