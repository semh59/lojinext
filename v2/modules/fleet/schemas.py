"""
Fleet modülü Pydantic şemaları — Araç (Vehicle), Dorse (Trailer), Bakım tahmini.

Güvenlik kontrolleri:
- Plaka format regex validasyonu
- String length constraints
- XSS/injection koruması
- Null byte sanitizasyonu
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.schemas.validators import (
    PLAKA_PATTERN_STR,
    sanitize_string,
    validate_safe_string,
)

# ── Araç (Vehicle) ──────────────────────────────────────────────────────


class AracBase(BaseModel):
    """Araç base model - ortak alanlar."""

    plaka: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=PLAKA_PATTERN_STR,
        description="Plaka formatı (Permissive)",
    )
    marka: str = Field(..., min_length=2, max_length=50)
    model: Optional[str] = Field(None, max_length=50)
    yil: Optional[int] = Field(None, ge=1990, description="Üretim yılı")
    tank_kapasitesi: int = Field(
        600, gt=0, le=5000, description="Tank kapasitesi (litre)"
    )
    hedef_tuketim: float = Field(
        32.0, gt=0, le=100, description="Hedef tüketim (lt/100km)"
    )

    # Araç Teknik Özellikleri (Aerodinamik)
    bos_agirlik_kg: float = Field(
        8000.0, gt=0, le=40000, description="Boş Ağırlık (kg)"
    )
    hava_direnc_katsayisi: float = Field(
        0.7, gt=0.1, le=2.0, description="Hava Direnç Katsayısı (Cd)"
    )
    on_kesit_alani_m2: float = Field(
        8.5, gt=1.0, le=20.0, description="Ön Kesit Alanı (m2)"
    )
    motor_verimliligi: float = Field(
        0.38, gt=0.1, le=1.0, description="Motor Verimliliği (0-1 arası)"
    )
    lastik_direnc_katsayisi: float = Field(
        0.007, gt=0.001, le=0.1, description="Lastik Direnç Katsayısı (Crr)"
    )
    maks_yuk_kapasitesi_kg: int = Field(
        26000, gt=0, le=50000, description="Maksimum Yük Kapasitesi (kg)"
    )
    dingil_sayisi: int = Field(2, ge=1, le=10, description="Dingil sayısı")
    yakit_tipi: str = Field("DIZEL", max_length=20, description="Yakıt tipi")

    aktif: bool = True
    muayene_tarihi: Optional[date] = Field(
        None, description="Muayene Geçerlilik Tarihi"
    )
    sigorta_tarihi: Optional[date] = Field(
        None, description="Sigorta Geçerlilik Tarihi"
    )
    motor_no: Optional[str] = Field(None, max_length=50)
    sasi_no: Optional[str] = Field(None, max_length=50)
    notlar: Optional[str] = Field(None, max_length=500)

    @field_validator("yil")
    @classmethod
    def check_yil(cls, v: Optional[int]) -> Optional[int]:
        """Yıl kontrolü - gelecek yıl + 1'den büyük olamaz."""
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

    @field_validator("marka", "model", mode="before")
    @classmethod
    def validate_marka_model(cls, v: Optional[str]) -> Optional[str]:
        """Marka ve model XSS koruması."""
        return validate_safe_string(v)

    @field_validator("motor_no", "sasi_no", mode="before")
    @classmethod
    def validate_motor_sasi(cls, v: Optional[str]) -> Optional[str]:
        """Motor/şasi no XSS koruması."""
        return validate_safe_string(v)

    @field_validator("notlar", mode="before")
    @classmethod
    def validate_notlar(cls, v: Optional[str]) -> Optional[str]:
        """Notlar alanı XSS koruması."""
        return validate_safe_string(v)


class AracCreate(AracBase):
    """Araç oluşturma şeması."""

    pass


class AracUpdate(BaseModel):
    """Araç güncelleme şeması - tüm alanlar optional."""

    plaka: Optional[str] = Field(
        None,
        min_length=3,
        max_length=20,
        pattern=PLAKA_PATTERN_STR,
    )
    marka: Optional[str] = Field(None, min_length=2, max_length=50)
    model: Optional[str] = Field(None, max_length=50)
    yil: Optional[int] = Field(None, ge=1990)
    tank_kapasitesi: Optional[int] = Field(None, gt=0, le=5000)
    hedef_tuketim: Optional[float] = Field(None, gt=0, le=100)
    bos_agirlik_kg: Optional[float] = Field(None, gt=0, le=40000)
    hava_direnc_katsayisi: Optional[float] = Field(None, gt=0.1, le=2.0)
    on_kesit_alani_m2: Optional[float] = Field(None, gt=1.0, le=20.0)
    motor_verimliligi: Optional[float] = Field(
        None, gt=0.1, le=1.0, description="Motor Verimliliği (0-1 arası)"
    )
    lastik_direnc_katsayisi: Optional[float] = Field(
        None, gt=0.001, le=0.1, description="Lastik Direnç Katsayısı (Crr)"
    )
    maks_yuk_kapasitesi_kg: Optional[int] = Field(
        None, gt=0, le=50000, description="Maksimum Yük Kapasitesi (kg)"
    )
    aktif: Optional[bool] = None
    muayene_tarihi: Optional[date] = Field(
        None, description="Muayene Geçerlilik Tarihi"
    )
    sigorta_tarihi: Optional[date] = Field(
        None, description="Sigorta Geçerlilik Tarihi"
    )
    motor_no: Optional[str] = Field(None, max_length=50)
    sasi_no: Optional[str] = Field(None, max_length=50)
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

    @field_validator("marka", "model", mode="before")
    @classmethod
    def validate_marka_model(cls, v: Optional[str]) -> Optional[str]:
        """Marka ve model XSS koruması."""
        return validate_safe_string(v)

    @field_validator("motor_no", "sasi_no", mode="before")
    @classmethod
    def validate_motor_sasi(cls, v: Optional[str]) -> Optional[str]:
        """Motor/şasi no XSS koruması."""
        return validate_safe_string(v)

    @field_validator("notlar", mode="before")
    @classmethod
    def validate_notlar(cls, v: Optional[str]) -> Optional[str]:
        """Notlar alanı XSS koruması."""
        return validate_safe_string(v)


_FLOAT_FALLBACKS: dict[str, float] = {
    "hedef_tuketim": 32.0,
    "bos_agirlik_kg": 8000.0,
    "hava_direnc_katsayisi": 0.7,
    "on_kesit_alani_m2": 8.5,
    "motor_verimliligi": 0.38,
    "lastik_direnc_katsayisi": 0.007,
}

# Geçerli (exclusive_lower, inclusive_upper) aralıkları — AracBase Field gt=/le=
# ile birebir. heal_* validator'ları bu aralık dışındaki bozuk DB değerlerini
# güvenli değere çeker; aksi halde mode="before" sonrası Field constraint reddeder
# ve okuma 500'e düşer (AUDIT-105: yalnız alt-sınır iyileştiriliyordu, üst-sınır açıktı).
_FLOAT_BOUNDS: dict[str, tuple[float, float]] = {
    "hedef_tuketim": (0.0, 100.0),
    "bos_agirlik_kg": (0.0, 40000.0),
    "hava_direnc_katsayisi": (0.1, 2.0),
    "on_kesit_alani_m2": (1.0, 20.0),
    "motor_verimliligi": (0.1, 1.0),
    "lastik_direnc_katsayisi": (0.001, 0.1),
}
# int alanları için (min_inclusive, max_inclusive) — gt=0 → min 1, ge=1 → min 1.
_INT_BOUNDS: dict[str, tuple[int, int]] = {
    "tank_kapasitesi": (1, 5000),
    "maks_yuk_kapasitesi_kg": (1, 50000),
    "dingil_sayisi": (1, 10),
}


class AracResponse(AracBase):
    """
    Araç response şeması - API çıktısı.

    [HEALING] Bozuk verileri otomatik düzeltir veya sessizce kabul eder
    böylece liste görünümünü bozmaz.
    """

    id: int
    plaka: str = Field(
        ..., description="Türkiye plaka formatı (Permissive in response)"
    )
    created_at: datetime
    # Stats from Relation
    toplam_km: float = 0.0
    toplam_sefer: int = 0
    ort_tuketim: float = 0.0
    acik_ariza: int = 0  # açık (tamamlanmamış) ARIZA/ACIL sayısı

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
        """Geçersiz yılları null'a çeker, hata fırlatmaz"""
        if v is None:
            return None
        try:
            val = int(v)
            if val < 1900 or val > 2100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("marka", "model", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> Optional[str]:
        """Boş/None string alanlarını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip() if isinstance(v, str) else None

    @field_validator(
        "tank_kapasitesi", "maks_yuk_kapasitesi_kg", "dingil_sayisi", mode="before"
    )
    @classmethod
    def heal_ints(cls, v: Any, info: ValidationInfo) -> int:
        """Bozuk int değerlerini geçerli aralığa çeker (alt + üst sınır)."""
        lo, hi = _INT_BOUNDS.get(info.field_name, (1, 2**31))
        if v is None:
            return lo
        try:
            return max(lo, min(int(v), hi))
        except (ValueError, TypeError):
            return lo

    @field_validator(
        "hedef_tuketim",
        "bos_agirlik_kg",
        "hava_direnc_katsayisi",
        "on_kesit_alani_m2",
        "motor_verimliligi",
        "lastik_direnc_katsayisi",
        mode="before",
    )
    @classmethod
    def heal_floats(cls, v: Any, info: ValidationInfo) -> float:
        """Bozuk float değerlerini alan varsayılanına döndürür.

        Aralık [gt_lower (exclusive), le_upper (inclusive)] dışındaki değerler
        (None, <=lower, >upper, sayı-olmayan) güvenli fallback'e indirgenir;
        böylece üst-sınır ihlali olan bozuk DB verisi okuma'da 500 üretmez.
        """
        fallback = _FLOAT_FALLBACKS.get(info.field_name, 1.0)
        if v is None:
            return fallback
        try:
            val = float(v)
        except (ValueError, TypeError):
            return fallback
        lower, upper = _FLOAT_BOUNDS.get(info.field_name, (0.0, float("inf")))
        if val <= lower or val > upper:
            return fallback
        return val

    @field_validator("created_at", mode="before")
    @classmethod
    def heal_created_at(cls, v: Any) -> datetime:
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

    @field_validator("toplam_km", "ort_tuketim", mode="before")
    @classmethod
    def heal_stats(cls, v: Any) -> float:
        """Bozuk istatistik değerlerini 0.0 yapar."""
        if v is None:
            return 0.0
        try:
            val = float(v)
            return max(0.0, val)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("toplam_sefer", mode="before")
    @classmethod
    def heal_sefer_count(cls, v: Any) -> int:
        """Bozuk sefer sayısını 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    model_config = ConfigDict(from_attributes=True)


# ── Dorse (Trailer) ─────────────────────────────────────────────────────


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
    model: Optional[str] = Field(None, max_length=50)
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

    @field_validator("marka", "model", "tipi", mode="before")
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
    model: Optional[str] = Field(None, max_length=50)
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


# ── Feature D — Tahmine Dayalı Bakım ────────────────────────────────────

RiskLevel = Literal["overdue", "soon", "normal", "low"]


class MaintenancePrediction(BaseModel):
    """D.1 — tek araç + bakım tipi için tahmin çıktısı."""

    model_config = ConfigDict(from_attributes=True)

    arac_id: int
    plaka: str
    bakim_tipi: str
    predictable: bool = Field(
        ..., description="False ise diğer tüm alanlar None/0/low olabilir"
    )
    predicted_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    confidence: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel = "low"
    savings_pct: float = Field(0.0, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list, max_length=10)
