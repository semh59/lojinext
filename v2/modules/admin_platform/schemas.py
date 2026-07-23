"""Admin/health/observability response schemas (dalga 16 — eski app/schemas/api_responses.py'den taşındı)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

_CONN_STR_RE = re.compile(
    r"(postgresql|redis|mongodb|amqp|mysql)://[^\s\"']+", re.IGNORECASE
)

class ComponentHealth(BaseModel):
    """One subsystem's health probe outcome."""

    status: str = Field(..., description="healthy | degraded | unhealthy")
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    @field_validator("error", mode="before")
    @classmethod
    def sanitize_error(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        msg = _CONN_STR_RE.sub("[connection-redacted]", str(v))
        return msg[:300]

    model_config = ConfigDict(extra="allow")


class HealthCheckResponse(BaseModel):
    """Liveness/readiness summary returned by `/health`."""

    status: str
    uptime_seconds: int
    components: Dict[str, ComponentHealth]

    model_config = ConfigDict(extra="allow")


class AdminHealthResponse(HealthCheckResponse):
    """Admin variant adds Sentry, circuit-breaker, and backup state."""

    sentry: Optional[Dict[str, Any]] = None
    circuit_breakers: Optional[Union[Dict[str, Any], List[Any]]] = None
    backups: Optional[Dict[str, Any]] = None


class CircuitBreakerResetResponse(BaseModel):
    success: bool
    message: str


class BackupTriggerResponse(BaseModel):
    message: str
    task_id: str


# ─── Debugging / coaching snapshot ──────────────────────────────────────────


class TraceChainResponse(BaseModel):
    """Combined error_events + audit_log rows for one trace_id (debugging)."""

    errors: List[Dict[str, Any]]
    audit: List[Dict[str, Any]]
    trace_id: str
    counts: Dict[str, int]
    hint: Optional[str] = None


class SseTokenResponse(BaseModel):
    token: str
    expires_in: int


class CoachingSnapshotResponse(BaseModel):
    ad_soyad: str
    skor: float
    headline: str
    top_suggestion: Optional[str] = None
    priority: str
    insights_count: int
    source: str


# ─── Telegram bot köprüsü (2026-07-22'de `app/schemas/telegram.py`'den
# taşındı — `internal_routes.py`/`telegram_bridge.py`'nin gerçek tüketicisi
# bu modüldü, dosya taşımadan geride kalmıştı) ──────────────────────────────


class DriverBreakdownRequest(BaseModel):
    """Sürücü botu /ariza komutu gövdesi.

    Araç, sürücünün en son seferinden backend tarafında otomatik çözülür —
    sürücü plaka girmez. `acil=True` → ACIL kaydı, aksi halde ARIZA.
    """

    telegram_id: str = Field(..., min_length=1)
    detaylar: str = Field("", max_length=1000)
    acil: bool = False


class SeferBelgeResponse(BaseModel):
    id: int
    sofor_id: int
    sefer_id: Optional[int]
    belge_tipi: str
    ocr_durumu: str
    ocr_veri: Optional[dict]
    # DB kolonu artık `created_at` (MODEL-003). Dış (telegram bot) JSON
    # sözleşmesi "olusturulma" anahtarı olarak korunur; ORM'den `created_at`
    # üzerinden okunur. Optional → eski `olusturulma=None` çağrısı da geçerli.
    olusturulma: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("created_at", "olusturulma"),
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SoforTelegramInfo(BaseModel):
    sofor_id: int
    ad_soyad: str
    aktif: bool
