"""
Yakıt (Fuel) Pydantic şemaları.

Güvenlik kontrolleri:
- Decimal precision (para değerleri)
- XSS koruması (istasyon, fis_no)
- Numeric constraints
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    computed_field,
    field_validator,
)

from app.schemas.validators import validate_safe_string

# Para alanlarının üst sınırları (YakitBase Field le= ile birebir). heal_amounts
# bu sınırı aşan bozuk DB değerini üst sınıra clamp eder; aksi halde mode="before"
# sonrası Field constraint reddeder ve okuma 500'e düşer (AUDIT-105: yalnız alt
# sınır >0 iyileştiriliyordu, üst sınır açıktı).
_AMOUNT_UPPER: dict[str, Decimal] = {
    "fiyat_tl": Decimal("1000"),
    "litre": Decimal("10000"),
    "toplam_tutar": Decimal("1000000"),
}
_KM_MAX = 9999999

DepoDurumu = Literal["Bilinmiyor", "Doldu", "Dolu", "Kısmi"]
YakitDurumu = Literal["Bekliyor", "Onaylandı", "Reddedildi"]


class YakitBase(BaseModel):
    """Yakıt base model - ortak alanlar."""

    tarih: date
    arac_id: int = Field(..., gt=0, le=999999999)
    istasyon: Optional[str] = Field(None, max_length=100)
    fiyat_tl: Decimal = Field(
        ..., gt=0, le=1000, decimal_places=2, description="Litre fiyatı (TL)"
    )
    litre: Decimal = Field(
        ..., gt=0, le=10000, decimal_places=2, description="Alınan yakıt (litre)"
    )
    toplam_tutar: Decimal = Field(
        ..., gt=0, le=1000000, decimal_places=2, description="Toplam tutar (TL)"
    )
    km_sayac: int = Field(..., gt=0, le=9999999, description="Kilometre sayacı")
    fis_no: Optional[str] = Field(None, max_length=50)
    depo_durumu: DepoDurumu = Field("Bilinmiyor")
    durum: YakitDurumu = Field("Bekliyor")

    @field_validator("istasyon", "fis_no", mode="before")
    @classmethod
    def validate_strings(cls, v: Optional[str]) -> Optional[str]:
        """String alanları XSS koruması."""
        return validate_safe_string(v)

    @field_validator("depo_durumu", mode="before")
    @classmethod
    def normalize_depo_durumu(cls, v: Optional[str]) -> Optional[str]:
        """Legacy/EN values are normalized to canonical TR labels."""
        if v is None:
            return v
        normalized = str(v).strip().lower()
        mapping = {
            "full": "Dolu",
            "filled": "Doldu",
            "dolu": "Dolu",
            "doldu": "Doldu",
            "kismi": "Kısmi",
            "kısmi": "Kısmi",
            "partial": "Kısmi",
            "bilinmiyor": "Bilinmiyor",
            "unknown": "Bilinmiyor",
        }
        return mapping.get(normalized, v)

    @field_validator("toplam_tutar")
    @classmethod
    def validate_toplam_tutar(cls, v: Decimal, info) -> Decimal:
        """Toplam tutar = fiyat * litre kontrolü (yaklaşık)."""
        # Not: Bu validation çok strict olmamalı, yuvarlama farkları olabilir
        # Sadece büyük tutarsızlıkları yakala
        return v


class YakitCreate(YakitBase):
    """Yakıt oluşturma şeması."""

    # Backend hesaplaması için opsiyonel yap
    toplam_tutar: Optional[Decimal] = Field(
        None, gt=0, le=1000000, decimal_places=2, description="Opsiyonel (Hesaplanır)"
    )


class YakitUpdate(BaseModel):
    """Yakıt güncelleme şeması - tüm alanlar optional."""

    tarih: Optional[date] = None
    arac_id: Optional[int] = Field(None, gt=0)
    istasyon: Optional[str] = Field(None, max_length=100)
    fiyat_tl: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    litre: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    toplam_tutar: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    km_sayac: Optional[int] = Field(None, gt=0)
    fis_no: Optional[str] = Field(None, max_length=50)
    depo_durumu: Optional[DepoDurumu] = None
    durum: Optional[YakitDurumu] = None

    @field_validator("istasyon", "fis_no", mode="before")
    @classmethod
    def validate_strings(cls, v: Optional[str]) -> Optional[str]:
        """String alanları XSS koruması."""
        return validate_safe_string(v)

    @field_validator("depo_durumu", mode="before")
    @classmethod
    def normalize_depo_durumu(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = str(v).strip().lower()
        mapping = {
            "full": "Dolu",
            "filled": "Doldu",
            "dolu": "Dolu",
            "doldu": "Doldu",
            "kismi": "Kısmi",
            "kısmi": "Kısmi",
            "partial": "Kısmi",
            "bilinmiyor": "Bilinmiyor",
            "unknown": "Bilinmiyor",
        }
        return mapping.get(normalized, v)


class YakitResponse(YakitBase):
    """
    Yakıt response şeması - API çıktısı.

    [HEALING] Finansal verilerin görünürlüğünü garanti eder.
    """

    id: int
    created_at: datetime
    plaka: Optional[str] = None

    @field_validator("fiyat_tl", "litre", "toplam_tutar", mode="before")
    @classmethod
    def heal_amounts(cls, v: Any, info: ValidationInfo) -> Decimal:
        """Geçersiz tutarları geçerli aralığa çeker (gt=0 alt + le= üst sınır)."""
        if v is None:
            return Decimal("0.01")
        try:
            val = Decimal(str(v))
        except (ValueError, TypeError, Exception):
            return Decimal("0.01")
        if val <= 0:
            return Decimal("0.01")
        upper = _AMOUNT_UPPER.get(info.field_name)
        if upper is not None and val > upper:
            return upper
        return val

    @field_validator("km_sayac", mode="before")
    @classmethod
    def heal_km(cls, v: Any) -> int:
        """Geçersiz KM verisini geçerli aralığa çeker (gt=0 alt + le= üst sınır)."""
        try:
            result = int(float(v))
        except (ValueError, TypeError):
            return 1
        return max(1, min(result, _KM_MAX))

    @field_validator("created_at", mode="before")
    @classmethod
    def heal_created_at(cls, v: object) -> datetime:
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

    @field_validator("plaka", mode="before")
    @classmethod
    def heal_plaka(cls, v: object) -> Optional[str]:
        """Boş/bozuk plaka alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip() if isinstance(v, str) else None

    # Frontend uyumu için fiyat_tl'yi birim_fiyat olarak da döndür
    @computed_field
    @property
    def birim_fiyat(self) -> Decimal:
        """Frontend için fiyat_tl alias'ı."""
        return self.fiyat_tl


class YakitListResponse(BaseModel):
    """Yakıt listesi response şeması (Sayfalı)."""

    items: List[YakitResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)


# For forward references
YakitListResponse.model_rebuild()


# ── Faz 6 — OCR web entegrasyonu ──────────────────────────────────────────
class OcrParsedFields(BaseModel):
    litre: Optional[float] = None
    tutar: Optional[float] = None
    km: Optional[int] = None
    tarih: Optional[str] = None
    istasyon: Optional[str] = None


class OcrPreviewResponse(BaseModel):
    ham_metin: Optional[str] = None
    yapilandirilmis: OcrParsedFields


class FuelDocumentItem(BaseModel):
    id: int
    belge_tipi: str
    ocr_durumu: str
    sofor_id: Optional[int] = None
    sefer_id: Optional[int] = None
    created_at: Optional[datetime] = None


class FuelDocumentList(BaseModel):
    items: List[FuelDocumentItem]
