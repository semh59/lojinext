"""
Sefer (Trip) Pydantic semalari.

Guvenlik kontrolleri:
- XSS korumasi (cikis/varis yerleri)
- String sanitizasyonu
- Numeric constraints
"""

import enum
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from v2.modules.shared_kernel.schemas.validators import validate_safe_string
from v2.modules.trip.sefer_status import (
    CANONICAL_SEFER_STATUS_SET,
    SEFER_STATUS_PLANLANDI,
    ensure_canonical_sefer_status,
    normalize_sefer_status,
)

_schema_logger = logging.getLogger(__name__)


class TripStatus(str, enum.Enum):
    # Canonical durumlar — DB CHECK ('Planned','Completed','Cancelled') ile birebir.
    # ASSIGNED/IN_PROGRESS kaldırıldı (DB'de yok, ölü koddu — MODEL-001/ARCH-003).
    PLANNED = "Planned"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


SeferDurum = Literal[
    "Completed",
    "Cancelled",
    "Planned",
]


class SeferBase(BaseModel):
    """Sefer base model."""

    sefer_no: Optional[str] = Field(None, max_length=50)
    tarih: date
    saat: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    arac_id: int = Field(..., gt=0)
    dorse_id: Optional[int] = Field(None, gt=0)
    sofor_id: int = Field(..., gt=0)
    guzergah_id: Optional[int] = Field(None, gt=0)
    route_pair_id: Optional[str] = None

    # Weight Info
    bos_agirlik_kg: int = Field(0, ge=0)
    dolu_agirlik_kg: int = Field(0, ge=0)
    net_kg: int = Field(0, ge=0)
    ton: float = Field(0.0, ge=0.0)

    # Location
    cikis_yeri: str = Field(..., min_length=1, max_length=100)
    varis_yeri: str = Field(..., min_length=1, max_length=100)
    mesafe_km: float = Field(..., gt=0, le=10000)
    baslangic_km: Optional[int] = Field(None, ge=0, le=9999999)
    bitis_km: Optional[int] = Field(None, ge=0, le=9999999)

    bos_sefer: bool = False
    durum: SeferDurum = Field("Planned")
    dagitilan_yakit: Optional[Decimal] = Field(None, ge=0, le=10000)
    tuketim: Optional[float] = Field(None, ge=0, le=1000)
    ascent_m: Optional[float] = Field(None, ge=0, le=50000)
    descent_m: Optional[float] = Field(None, ge=0, le=50000)
    flat_distance_km: float = Field(0.0, ge=0.0, le=10000)
    otoban_mesafe_km: Optional[float] = Field(None, ge=0)
    sehir_ici_mesafe_km: Optional[float] = Field(None, ge=0)
    rota_detay: Optional[dict] = None
    tahmin_meta: Optional[dict] = None
    notlar: Optional[str] = Field(None, max_length=255)

    @field_validator("cikis_yeri", "varis_yeri", "notlar", mode="before")
    @classmethod
    def validate_location(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_string(v)

    @field_validator("dagitilan_yakit", mode="before")
    @classmethod
    def heal_yakit(cls, v: Any) -> Optional[Decimal]:
        """Bozuk yakıt değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = Decimal(str(v))
            return val if val >= 0 else None
        except (ValueError, TypeError, Exception):
            return None

    @field_validator("durum", mode="before")
    @classmethod
    def normalize_durum(cls, v: Optional[str]) -> Optional[str]:
        return ensure_canonical_sefer_status(v, field_name="durum", allow_none=False)

    @field_validator("bos_agirlik_kg", "dolu_agirlik_kg", "net_kg", mode="before")
    @classmethod
    def heal_weights(cls, v: Any) -> int:
        """Bozuk ağırlık değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("tarih", mode="after")
    @classmethod
    def validate_tarih_not_future(cls, v: date) -> date:
        if v > date.today() + timedelta(days=365):
            raise ValueError("Tarih en fazla 365 gun ileri olabilir")
        return v


class SeferCreate(SeferBase):
    """Sefer olusturma semasi."""

    # Override with stricter min_length=2 so FastAPI returns 422 on input validation
    cikis_yeri: str = Field(..., min_length=2, max_length=100)
    varis_yeri: str = Field(..., min_length=2, max_length=100)

    guzergah_id: Optional[int] = Field(None, gt=0)
    route_pair_id: Optional[str] = None

    # Round-trip support
    is_round_trip: bool = Field(False)
    return_net_kg: Optional[int] = Field(0, ge=0)
    return_sefer_no: Optional[str] = Field(None, max_length=50)

    @model_validator(mode="after")
    def validate_km_range(self) -> "SeferCreate":
        if self.baslangic_km is not None and self.bitis_km is not None:
            if self.bitis_km < self.baslangic_km:
                raise ValueError("Bitis km buyuk olmali")
        return self


class SeferUpdate(BaseModel):
    """Sefer guncelleme semasi."""

    tarih: Optional[date] = None
    saat: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    arac_id: Optional[int] = Field(None, gt=0)
    dorse_id: Optional[int] = Field(None, gt=0)
    sofor_id: Optional[int] = Field(None, gt=0)
    guzergah_id: Optional[int] = Field(None, gt=0)
    route_pair_id: Optional[str] = None

    bos_agirlik_kg: Optional[int] = Field(None, ge=0)
    dolu_agirlik_kg: Optional[int] = Field(None, ge=0)
    net_kg: Optional[int] = Field(None, ge=0)
    ton: Optional[float] = Field(None, ge=0.0)

    cikis_yeri: Optional[str] = Field(None, min_length=1, max_length=100)
    varis_yeri: Optional[str] = Field(None, min_length=1, max_length=100)
    mesafe_km: Optional[float] = Field(None)  # validator heals negatives
    baslangic_km: Optional[int] = Field(None, ge=0)
    bitis_km: Optional[int] = Field(None, ge=0)

    @field_validator("mesafe_km", mode="before")
    @classmethod
    def heal_mesafe_km(cls, v: Optional[float]) -> Optional[float]:
        """Heal non-positive mesafe_km to a safe minimum instead of rejecting."""
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if f > 0 else 1.0

    bos_sefer: Optional[bool] = None
    durum: Optional[TripStatus] = None  # Use Enum
    periyot_id: Optional[int] = Field(None, gt=0)
    dagitilan_yakit: Optional[Decimal] = Field(None, ge=0)
    tuketim: Optional[float] = Field(None, ge=0)
    ascent_m: Optional[float] = Field(None, ge=0)
    descent_m: Optional[float] = Field(None, ge=0)
    flat_distance_km: Optional[float] = Field(None, ge=0)
    tahmin_meta: Optional[dict] = None
    notlar: Optional[str] = Field(None, max_length=255)
    iptal_nedeni: Optional[str] = Field(None, max_length=255)

    sefer_no: Optional[str] = Field(None, max_length=50)
    is_round_trip: Optional[bool] = Field(None)
    return_net_kg: Optional[int] = Field(None, ge=0)
    return_sefer_no: Optional[str] = Field(None, max_length=50)
    version: Optional[int] = Field(None, ge=1)

    @field_validator("durum", mode="before")
    @classmethod
    def normalize_durum(cls, v: Optional[str]) -> Optional[str]:
        return ensure_canonical_sefer_status(v, field_name="durum", allow_none=True)

    @model_validator(mode="after")
    def validate_iptal(self) -> "SeferUpdate":
        if self.durum == TripStatus.CANCELLED and not (self.iptal_nedeni or "").strip():
            raise ValueError("İptal durumunda iptal_nedeni zorunludur")
        return self

    @model_validator(mode="after")
    def validate_km_range(self) -> "SeferUpdate":
        if self.baslangic_km is not None and self.bitis_km is not None:
            if self.bitis_km < self.baslangic_km:
                raise ValueError("Bitis km buyuk olmali")
        return self

    model_config = ConfigDict(from_attributes=True)


class SeferResponse(SeferBase):
    """Sefer response semasi."""

    id: int
    plaka: Optional[str] = None
    dorse_plakasi: Optional[str] = None
    sofor_adi: Optional[str] = None
    guzergah_adi: Optional[str] = None
    periyot_id: Optional[int] = None
    durum: TripStatus = TripStatus.PLANNED  # Standard Response; defaults to PLANNED
    onay_durumu: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("saat", mode="before")
    @classmethod
    def _coerce_empty_saat(cls, v: Optional[str]) -> Optional[str]:
        """Empty or invalid saat values from DB are coerced to None."""
        import re as _re

        _SAAT_RE = _re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
        if v is None or v == "":
            return None
        if not _SAAT_RE.match(str(v)):
            return None
        return v

    @field_validator("durum", mode="before")
    @classmethod
    def heal_durum(cls, v: Any) -> str:
        """Durum'u canonical forma (Planned/Completed/Cancelled) çevirir.

        Legacy Türkçe/ASCII değerler normalize edilir; tanınmayan/bozuk
        değerler güvenli şekilde Planned'e fallback eder.
        """
        normalized = normalize_sefer_status(v) if v is not None else None
        if normalized in CANONICAL_SEFER_STATUS_SET:
            return normalized
        return SEFER_STATUS_PLANLANDI

    @field_validator(
        "plaka",
        "dorse_plakasi",
        "sofor_adi",
        "guzergah_adi",
        "onay_durumu",
        mode="before",
    )
    @classmethod
    def heal_strings(cls, v: Any) -> Optional[str]:
        """Boş/None string alanlarını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip() if isinstance(v, str) else None

    @field_validator("mesafe_km", "flat_distance_km", mode="before")
    @classmethod
    def heal_required_floats(cls, v: Any) -> float:
        """Bozuk float değerlerini 1.0'a çeker (required fields)."""
        if v is None:
            _schema_logger.warning(
                "SeferResponse healing: None value replaced with 1.0 for required float field"
            )
            return 1.0
        try:
            val = float(v)
            if val <= 0:
                _schema_logger.warning(
                    "SeferResponse healing: non-positive value %r replaced with 1.0", v
                )
                return 1.0
            return val
        except (ValueError, TypeError):
            _schema_logger.warning(
                "SeferResponse healing: unparseable value %r replaced with 1.0", v
            )
            return 1.0

    @field_validator(
        "ton",
        "ascent_m",
        "descent_m",
        "otoban_mesafe_km",
        "sehir_ici_mesafe_km",
        "tuketim",
        mode="before",
    )
    @classmethod
    def heal_optional_floats(cls, v: Any) -> Optional[float]:
        """Bozuk float değerlerini NULL yapar (optional fields)."""
        if v is None:
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("tarih", mode="before")
    @classmethod
    def heal_tarih(cls, v: Any) -> Optional[date]:
        """Bozuk tarihleri NULL yapar."""
        from datetime import date as dt_date

        if v is None:
            return None
        if isinstance(v, dt_date):
            return v
        try:
            return dt_date.fromisoformat(str(v).split("T")[0])
        except (ValueError, TypeError, Exception):
            return None


# Bulk Schemas omitted for brevity but should be updated to use TripStatus
class SeferBulkStatusUpdate(BaseModel):
    sefer_ids: List[int]
    new_status: TripStatus


class SeferBulkCancel(BaseModel):
    sefer_ids: List[int]
    iptal_nedeni: str


class SeferBulkDelete(BaseModel):
    sefer_ids: List[int]


class SeferBulkResponse(BaseModel):
    success_count: int
    failed_count: int
    failed: List[int] = []


class SeferListResponse(BaseModel):
    items: List[SeferResponse]
    meta: Optional[dict] = None


class SeferStatsResponse(BaseModel):
    total_count: int
    completed_count: int
    cancelled_count: int
    planned_count: int
    in_progress_count: int
    total_distance_km: float
    avg_consumption: float


# ─── Sefer zaman-çizelgesi response şeması (dalga 16 — eski app/schemas/api_responses.py'den taşındı) ───────


class TripTimelineResponse(BaseModel):
    items: List[Dict[str, Any]]


class SeferOnayRequest(BaseModel):
    """`POST /trips/{sefer_id}/onay` gövdesi (dalga 1'de `app/schemas/
    telegram.py`'den taşındı — Telegram bot'a özgü değil, trip'in kendi
    onay endpoint'inin gövdesi)."""

    onay_notu: Optional[str] = Field(None, max_length=500)
