"""Reports v2 RV2.PWA — Web Push abonelik schema'ları.

Plan §7.2 — frontend `PushSubscription.toJSON()` çıktısını karşılar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
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


# ─── Admin bildirim response şemaları (dalga 16 — eski app/schemas/api_responses.py'den taşındı) ───────


class NotificationRuleResponse(BaseModel):
    id: int
    olay_tipi: str
    kanallar: List[str]
    alici_rol_id: int
    aktif: bool

    model_config = ConfigDict(extra="allow", from_attributes=True)


class NotificationItemResponse(BaseModel):
    id: int
    baslik: str
    icerik: str
    olay_tipi: Optional[str] = None
    kanal: str
    durum: str
    okundu: bool
    olusturma_tarihi: str

    @field_validator("baslik", "icerik", "kanal", "durum", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("olay_tipi", mode="before")
    @classmethod
    def heal_optional_string(cls, v: Any) -> Optional[str]:
        """Boş optional string alanlarını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("olusturma_tarihi", mode="before")
    @classmethod
    def heal_datetime_string(cls, v: Any) -> str:
        """Bozuk datetime string değerlerini fallback'ler."""
        if v is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v).strip()


class MarkAllReadResponse(BaseModel):
    success: bool
    count: int


class MarkSingleReadResponse(BaseModel):
    success: bool
