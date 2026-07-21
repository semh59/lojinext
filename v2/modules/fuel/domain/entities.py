"""Fuel internal Pydantic entities — dalga 16'da app/core/entities/models.py'den
taşındı. `YakitAlimi`/`YakitAlimiCreate`/`YakitPeriyodu`, HTTP-yüzeyi
`schemas.py`'deki `YakitCreate`/`YakitUpdate`/`YakitResponse`'dan AYRI,
application katmanının (`add_yakit.py`, `bulk_add_yakit.py`, `get_yakit.py`,
`list_yakit.py`, `calculate_period.py`, `recalculate_vehicle_periods.py`) ve
`domain/period_matcher.py`'nin kullandığı dahili DTO'lardır.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from v2.modules.shared_kernel.domain.base_entity import BaseEntity


class YakitAlimi(BaseEntity):
    """Yakıt alımı entity'si"""

    tarih: date
    arac_id: int = Field(..., gt=0)
    istasyon: Optional[str] = Field(default=None, max_length=100)
    fiyat_tl: Decimal = Field(..., gt=Decimal("0"), le=Decimal("1000"))
    litre: float = Field(..., gt=0, le=10000)
    km_sayac: int = Field(..., gt=0)
    fis_no: Optional[str] = Field(default=None, max_length=50)
    depo_durumu: str = Field(default="Bilinmiyor", max_length=20)
    aktif: bool = True
    # DB CHECK + request şeması Türkçe ('Bekliyor'/'Onaylandi'); DurumEnum
    # (İngilizce 'Pending'...) buraya UYMAZ — DB'den okunan Türkçe değeri
    # reddedip fuel list/create response'unu 400'e düşürüyordu. Şema katmanı
    # (YakitAlimiCreate) zaten geçerli durum setini doğruluyor.
    durum: str = Field(default="Bekliyor", max_length=20)

    # İlişkili veri (optional, JOIN'den gelir)
    plaka: Optional[str] = None

    @field_validator("fiyat_tl", mode="before")
    @classmethod
    def normalize_fiyat(cls, v: Any) -> Decimal:
        """Float değerleri Decimal'e çevirirken yuvarla"""
        if isinstance(v, float):
            # Float hassasiyet sorununu çözmek için string üzerinden çevir
            # Ancak önce yuvarla ki 41.050000001 gibi değerler 41.05 olsun
            return Decimal(f"{v:.2f}")
        return v

    @field_validator("fiyat_tl")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Fiyat en fazla 2 ondalık basamak içerebilir"""
        # Quantize to 2 decimal places to be safe
        return v.quantize(Decimal("0.01"))

    @computed_field
    @property
    def toplam_tutar(self) -> Decimal:
        """Toplam tutarı hesapla"""
        return round(self.fiyat_tl * Decimal(str(self.litre)), 2)


class YakitAlimiCreate(BaseModel):
    """Yakıt alımı oluşturma DTO"""

    tarih: date
    arac_id: int = Field(..., gt=0)
    istasyon: Optional[str] = Field(default=None, max_length=100)
    fiyat_tl: Decimal = Field(..., gt=Decimal("0"), le=Decimal("1000"))
    litre: float = Field(..., gt=0, le=2000)
    km_sayac: int = Field(..., gt=0)
    fis_no: Optional[str] = Field(default=None, max_length=50)
    depo_durumu: Optional[str] = "Bilinmiyor"


class YakitPeriyodu(BaseModel):
    """İki depo dolumu arasındaki periyot verisi"""

    id: Optional[int] = None
    arac_id: int
    alim1_id: Optional[int] = None
    alim2_id: Optional[int] = None
    alim1_tarih: Optional[date] = None
    alim1_km: Optional[int] = None
    alim1_litre: Optional[float] = None
    alim2_tarih: Optional[date] = None
    alim2_km: Optional[int] = None
    baslangic_km: Optional[int] = None
    bitis_km: Optional[int] = None
    ara_mesafe: int
    toplam_yakit: float
    ort_tuketim: float = 0.0
    baslangic_tarih: Optional[date] = None
    bitis_tarih: Optional[date] = None
    durum: Optional[str] = None

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "YakitPeriyodu":
        if self.baslangic_km is None:
            self.baslangic_km = self.alim1_km
        if self.bitis_km is None:
            self.bitis_km = self.alim2_km
        if self.baslangic_tarih is None:
            self.baslangic_tarih = self.alim1_tarih
        if self.bitis_tarih is None:
            self.bitis_tarih = self.alim2_tarih
        if self.alim1_km is None:
            self.alim1_km = self.baslangic_km
        if self.alim2_km is None:
            self.alim2_km = self.bitis_km
        if self.alim1_tarih is None:
            self.alim1_tarih = self.baslangic_tarih
        if self.alim2_tarih is None:
            self.alim2_tarih = self.bitis_tarih
        return self
