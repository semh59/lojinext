"""Response schemas for endpoints whose shape does not fit a domain entity.

Used by:
  - health/admin_health        — system health snapshots
  - admin_imports              — import job history
  - admin_notifications        — notification rules + user inbox
  - admin_maintenance          — maintenance records, alerts, completion
  - fuel/stats                 — fuel statistics summary
  - weather/dashboard-summary  — dashboard risk roll-up
  - locations/route-info       — coordinate→route lookup
  - routes/analyze             — route analysis with difficulty
"""

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CONN_STR_RE = re.compile(
    r"(postgresql|redis|mongodb|amqp|mysql)://[^\s\"']+", re.IGNORECASE
)

# ─── Health / Admin Health ───────────────────────────────────────────────────


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


# ─── Admin Imports ───────────────────────────────────────────────────────────


class ImportHistoryItem(BaseModel):
    """One row from the import-job history table."""

    id: int
    dosya_adi: str
    aktarim_tipi: str
    durum: str
    toplam: int
    basarili: int
    hatali: int
    baslama_zamani: Optional[datetime] = None
    yukleyen_id: Optional[int] = None

    @field_validator("dosya_adi", "aktarim_tipi", "durum", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("toplam", "basarili", "hatali", mode="before")
    @classmethod
    def heal_ints(cls, v: Any) -> int:
        """Bozuk int değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("baslama_zamani", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> Optional[datetime]:
        """Bozuk datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None


# ─── Admin Notifications ─────────────────────────────────────────────────────


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


# ─── Admin Maintenance ───────────────────────────────────────────────────────


class MaintenanceRecordResponse(BaseModel):
    """`AracBakim` row, exposed via SQLAlchemy `from_attributes`."""

    id: int
    arac_id: Optional[int] = None
    dorse_id: Optional[int] = None
    bakim_tipi: str
    km_bilgisi: int
    bakim_tarihi: datetime
    maliyet: Decimal = Field(default=Decimal("0"))
    detaylar: Optional[str] = None
    tamamlandi: bool = False
    guncelleme_tarihi: Optional[datetime] = None

    @field_validator("bakim_tipi", mode="before")
    @classmethod
    def heal_bakim_tipi(cls, v: Any) -> str:
        """Boş bakim_tipi alanını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("km_bilgisi", mode="before")
    @classmethod
    def heal_km(cls, v: Any) -> int:
        """Bozuk km değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("maliyet", mode="before")
    @classmethod
    def heal_maliyet(cls, v: Any) -> Decimal:
        """Bozuk maliyet değerlerini 0 yapar."""
        if v is None:
            return Decimal("0")
        try:
            val = Decimal(str(v))
            return val if val >= 0 else Decimal("0")
        except (ValueError, TypeError, Exception):
            return Decimal("0")

    @field_validator("detaylar", mode="before")
    @classmethod
    def heal_detaylar(cls, v: Any) -> Optional[str]:
        """Boş detaylar alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("bakim_tarihi", mode="before")
    @classmethod
    def heal_bakim_tarihi(cls, v: Any) -> datetime:
        """Bozuk datetime değerlerini şu andan yapılır."""
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return datetime.now(timezone.utc)

    @field_validator("guncelleme_tarihi", mode="before")
    @classmethod
    def heal_update_time(cls, v: Any) -> Optional[datetime]:
        """Bozuk optional datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceAlertItem(BaseModel):
    """Single maintenance alert as enriched by the service layer."""

    id: int
    arac_id: Optional[int] = None
    plaka: str
    bakim_tipi: str
    tarih: datetime
    vade_durumu: str = Field(..., description="UPCOMING | OVERDUE")

    @field_validator("plaka", "bakim_tipi", "vade_durumu", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("tarih", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> datetime:
        """Bozuk datetime değerlerini şu andan yapılır."""
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return datetime.now(timezone.utc)


class MaintenanceCompleteResponse(BaseModel):
    success: bool


# ─── Fuel statistics ─────────────────────────────────────────────────────────


class FuelStatsResponse(BaseModel):
    """Fuel aggregation summary. Service-driven, so extra keys are tolerated
    (e.g. per-vehicle breakdown, percentile metrics) — but the headline numbers
    are documented for the client contract."""

    toplam_litre: Optional[float] = None
    toplam_maliyet: Optional[float] = None
    ortalama_birim_fiyat: Optional[float] = None
    kayit_sayisi: Optional[int] = None

    @field_validator(
        "toplam_litre", "toplam_maliyet", "ortalama_birim_fiyat", mode="before"
    )
    @classmethod
    def heal_floats(cls, v: Any) -> Optional[float]:
        """Bozuk float değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("kayit_sayisi", mode="before")
    @classmethod
    def heal_count(cls, v: Any) -> Optional[int]:
        """Bozuk count değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = int(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    model_config = ConfigDict(extra="allow")


# ─── Weather dashboard ──────────────────────────────────────────────────────


class WeatherTripDetail(BaseModel):
    trip_id: int
    plaka: str
    risk: str = Field(..., description="High | Unavailable")
    impact: Optional[float] = None
    error_code: Optional[str] = None


class WeatherDashboardResponse(BaseModel):
    total_active: int
    high_risk: int
    medium_risk: int
    normal: int
    unavailable: int
    details: List[WeatherTripDetail]


# ─── Routes / locations ─────────────────────────────────────────────────────


class RouteInfoResponse(BaseModel):
    """Result of a coordinate→route lookup. Provider returns extra fields
    (geometry, segments, elevation profile) — kept under `extra=allow` so
    callers can read them, but the documented core is mandatory."""

    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    otoban_mesafe_km: Optional[float] = None
    sehir_ici_mesafe_km: Optional[float] = None
    source: Optional[str] = None

    @field_validator(
        "distance_km",
        "duration_min",
        "ascent_m",
        "descent_m",
        "otoban_mesafe_km",
        "sehir_ici_mesafe_km",
        mode="before",
    )
    @classmethod
    def heal_floats(cls, v: Any) -> Optional[float]:
        """Bozuk float değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("source", mode="before")
    @classmethod
    def heal_source(cls, v: Any) -> Optional[str]:
        """Boş source alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    model_config = ConfigDict(extra="allow")


class RouteAnalysisResponse(RouteInfoResponse):
    difficulty: Optional[str] = Field(
        None, description="Düz | Hafif Eğimli | Dik/Dağlık (computed by service)"
    )

    @field_validator("difficulty", mode="before")
    @classmethod
    def heal_difficulty(cls, v: Any) -> Optional[str]:
        """Boş difficulty alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()
