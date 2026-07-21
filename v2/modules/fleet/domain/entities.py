"""Fleet internal Pydantic entities — dalga 16'da app/core/entities/models.py'den
taşındı. `Arac` ve `VehicleStats`, HTTP-yüzeyi `schemas.py`'deki
`AracCreate`/`AracUpdate`/`AracResponse`'dan AYRI, application/domain
katmanının kendi içinde kullandığı hafif DTO'lardır (ör. yaş/euro-sınıfı
hesaplaması gerektiren `ensemble_service.py` gibi cross-module tüketiciler).
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field, computed_field, field_validator

from v2.modules.shared_kernel.domain.base_entity import BaseEntity


def validate_plaka_str(v: str) -> str:
    v = v.upper().strip()
    v = " ".join(v.split())  # Normalize spaces
    pattern = r"^(\d{2})\s*([A-Z]{1})\s*(\d{4})$|^(\d{2})\s*([A-Z]{2})\s*(\d{3,4})$|^(\d{2})\s*([A-Z]{3,4})\s*(\d{2,3})$"  # noqa: E501
    match = re.match(pattern, v)
    if not match:
        basic_pattern = r"^(\d{2})\s*([A-Z]{1,3})\s*(\d{2,4})$"
        if not re.match(basic_pattern, v):
            raise ValueError(f"Geçersiz plaka formatı: {v}")
        return v
    parts = [g for g in match.groups() if g]
    return f"{parts[0]} {parts[1]} {parts[2]}"


class Arac(BaseEntity):
    """Araç entity'si - tam validation ile"""

    plaka: str = Field(..., min_length=7, max_length=12)
    marka: str = Field(..., min_length=2, max_length=50)
    model: str | None = Field(default=None, max_length=50)
    yil: int | None = Field(default=None, ge=1980, le=2030)
    tank_kapasitesi: int = Field(default=600, ge=100, le=2000)
    hedef_tuketim: float = Field(default=32.0, ge=15.0, le=60.0)

    # Technical Specs
    bos_agirlik_kg: float = Field(default=8000.0, ge=2000.0, le=15000.0)
    hava_direnc_katsayisi: float = Field(default=0.7, ge=0.3, le=1.2)
    on_kesit_alani_m2: float = Field(default=8.5, ge=4.0, le=12.0)
    motor_verimliligi: float = Field(default=0.38, ge=0.2, le=0.55)
    lastik_direnc_katsayisi: float = Field(default=0.007, ge=0.004, le=0.015)
    maks_yuk_kapasitesi_kg: int = Field(default=26000, ge=1000, le=40000)

    aktif: bool = True
    notlar: str | None = Field(default=None, max_length=2000)

    # Stats (Joined from Repo)
    toplam_km: float | None = 0.0
    toplam_sefer: int | None = 0
    ort_tuketim: float | None = 0.0

    @computed_field
    @property
    def yas(self) -> int | None:
        """Araç yaşı (yıl bazında) - dinamik hesaplama"""
        return date.today().year - self.yil if self.yil else None

    @computed_field
    @property
    def euro_sinifi(self) -> str:
        """
        Euro emisyon sınıfı tahmini.
        Eski araçlar daha fazla yakıt harcar.
        """
        if not self.yil:
            return "Bilinmiyor"
        if self.yil >= 2014:
            return "Euro 6"
        elif self.yil >= 2009:
            return "Euro 5"
        elif self.yil >= 2006:
            return "Euro 4"
        return "Euro 3"

    @computed_field
    @property
    def yas_faktoru(self) -> float:
        """
        Araç yaşına göre yakıt tüketim faktörü.
        Yeni araç = 1.0, her 5 yıl için +%2 artış
        """

        yas = self.yas
        if yas is None:
            return 1.0  # Yıl bilgisi yok — nötr (5 yıl baseline'ına eşdeğer) faktör
        if yas <= 2:
            return 0.98  # Yeni araç avantajı
        elif yas <= 5:
            return 1.0
        elif yas <= 10:
            return 1.02 + (yas - 5) * 0.005  # 1.02 - 1.045
        else:
            return 1.05 + (yas - 10) * 0.01  # 1.05+ (max ~1.15)

    @field_validator("plaka")
    @classmethod
    def validate_plaka(cls, v: str) -> str:
        """Plaka formatını doğrula ve standardize et"""
        if not v:
            raise ValueError("Plaka boş olamaz")
        return validate_plaka_str(v)


class VehicleStats(BaseModel):
    """Araç bazlı istatistikler"""

    arac_id: int
    plaka: str
    toplam_sefer: int = 0
    toplam_km: float = 0.0
    ort_tuketim: float = 0.0
    toplam_yakit: float = 0.0
    en_iyi_tuketim: float | None = None
    en_kotu_tuketim: float | None = None
    anomali_sayisi: int = 0
    eei: float | None = None
