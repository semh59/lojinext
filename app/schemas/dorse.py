"""
Dorse (Trailer) Pydantic şemaları.
"""

from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import sanitize_string, validate_safe_string


class DorseBase(BaseModel):
    """Dorse base model - ortak alanlar."""

    plaka: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^[0-9A-Z\s]{3,20}$",
        description="Plaka formatı (ASCII Safe)",
    )

    marka: Optional[str] = Field(None, max_length=50)
    tipi: str = Field("Standart", max_length=50, description="Dorse tipi")
    yil: Optional[int] = Field(None, ge=1990, description="Üretim yılı")

    # Dorse Teknik Özellikleri
    bos_agirlik_kg: float = Field(
        6000.0, gt=0, le=20000, description="Boş Ağırlık (kg)"
    )
    maks_yuk_kapasitesi_kg: int = Field(
        24000, gt=0, le=40000, description="Maksimum Yük Kapasitesi (kg)"
    )
    lastik_sayisi: int = Field(6, ge=4, le=16, description="Lastik Sayısı")
    dorse_lastik_direnc_katsayisi: float = Field(
        0.006, gt=0.001, le=0.1, description="Dorse Lastik Direnç Katsayısı (Crr)"
    )
    dorse_hava_direnci: float = Field(
        0.2, gt=0.0, le=1.0, description="Dorse Hava Direnci Katkısı"
    )

    muayene_tarihi: Optional[date] = Field(
        None, description="Muayene Geçerlilik Tarihi"
    )
    aktif: bool = True
    notlar: Optional[str] = Field(None, max_length=500)

    @field_validator("yil")
    @classmethod
    def check_yil(cls, v: Optional[int]) -> Optional[int]:
        """Yıl kontrolü."""
        if v is None:
            return v
        current_year = datetime.now(timezone.utc).year
        if v > current_year + 1:
            raise ValueError(f"Yıl {current_year + 1} değerinden büyük olamaz")
        return v

    @field_validator("plaka", mode="before")
    @classmethod
    def sanitize_plaka(cls, v: Optional[str]) -> Optional[str]:
        """Plaka whitespace strip."""
        return sanitize_string(v) if isinstance(v, str) else v

    @field_validator("marka", "tipi", mode="before")
    @classmethod
    def validate_strings(cls, v: Optional[str]) -> Optional[str]:
        """XSS koruması."""
        return validate_safe_string(v)


class DorseCreate(DorseBase):
    """Dorse oluşturma şeması."""

    pass


class DorseUpdate(BaseModel):
    """Dorse güncelleme şeması."""

    plaka: Optional[str] = Field(
        None,
        min_length=3,
        max_length=20,
        pattern=r"^[0-9A-Z\s]{3,20}$",
        description="Plaka formatı (ASCII Safe)",
    )
    marka: Optional[str] = Field(None, max_length=50)
    tipi: Optional[str] = Field(None, max_length=50)
    yil: Optional[int] = Field(None, ge=1990)
    bos_agirlik_kg: Optional[float] = Field(None, gt=0)
    maks_yuk_kapasitesi_kg: Optional[int] = Field(None, gt=0)
    lastik_sayisi: Optional[int] = Field(None, ge=4)
    dorse_lastik_direnc_katsayisi: Optional[float] = Field(None, gt=0)
    dorse_hava_direnci: Optional[float] = Field(None, gt=0)
    muayene_tarihi: Optional[date] = None
    aktif: Optional[bool] = None
    notlar: Optional[str] = Field(None, max_length=500)


class DorseResponse(DorseBase):
    """Dorse response şeması."""

    id: int
    plaka: str = Field(..., description="Dorse plakası (Permissive in response)")
    created_at: datetime
    updated_at: datetime

    @field_validator("plaka", mode="before")
    @classmethod
    def heal_plaka(cls, v: Any) -> str:
        """Geçersiz plaka formatını bile kabul eder (Görünürlük için)"""
        if not v:
            return "BİLİNMİYOR"
        return str(v).strip().upper()

    @field_validator("yil", mode="before")
    @classmethod
    def heal_yil(cls, v: Any) -> Optional[int]:
        """Geçersiz yılları null'a çeker"""
        if v is None:
            return None
        try:
            val = int(v)
            if val < 1900 or val > 2100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("marka", "tipi", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> Optional[str]:
        """Boş/None string alanlarını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip() if isinstance(v, str) else None

    @field_validator(
        "bos_agirlik_kg",
        "dorse_hava_direnci",
        "dorse_lastik_direnc_katsayisi",
        mode="before",
    )
    @classmethod
    def heal_floats(cls, v: Any) -> float:
        """Bozuk float değerlerini 0.0 yapar."""
        if v is None:
            return 0.0
        try:
            val = float(v)
            return max(0.0, val)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("maks_yuk_kapasitesi_kg", "lastik_sayisi", mode="before")
    @classmethod
    def heal_ints(cls, v: Any) -> int:
        """Bozuk int değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> datetime:
        """Bozuk datetime değerlerini şu andan yapılır."""
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return v
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return dt
        except (ValueError, TypeError, Exception):
            return datetime.now(timezone.utc)

    model_config = ConfigDict(from_attributes=True)
