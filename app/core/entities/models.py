"""
TIR Yakıt Takip Sistemi - Pydantic Entities
Type-safe veri modelleri
"""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.utils.sefer_status import ensure_canonical_sefer_status


class DurumEnum(str, Enum):
    """Genel kayıt/onay durumu (legacy). NOT: YakitAlimi.durum artık bu enum'u
    KULLANMIYOR — DB CHECK + request şeması Türkçe ('Bekliyor'/'Onaylandi')
    olduğu için entity `durum: str` oldu (İngilizce DurumEnum DB'den okunan
    Türkçe değeri reddedip fuel response'unu 400'e düşürüyordu). Sefer durumu
    için ayrı `SeferDurumEnum` (Planned/Completed/Cancelled) kullanılır; bu iki
    enum farklı domain'lerdir, BİRLEŞTİRİLMEMELİDİR (MODEL-005)."""

    BEKLIYOR = "Pending"
    ONAYLANDI = "Approved"
    REDDEDILDI = "Rejected"
    TAMAM = "Done"
    HATA = "Error"
    IPTAL = "Cancelled"
    PLANLANDI = "Planned"
    YOLDA = "InTransit"
    DEVAM_EDIYOR = "InProgress"
    TAMAMLANDI = "Completed"


class SeferDurumEnum(str, Enum):
    """Sefer durum sözleşmesi (canonical) — Sefer entity'leri için.

    DB CHECK ('Planned','Completed','Cancelled') ile birebir. Yakıt/onay
    durumu için `DurumEnum` kullanılır; bu ikisi ayrı domain'lerdir."""

    PLANLANDI = "Planned"
    TAMAMLANDI = "Completed"
    IPTAL = "Cancelled"


class ZorlukEnum(str, Enum):
    """Güzergah zorluğu"""

    KOLAY = "Easy"
    NORMAL = "Normal"
    ZOR = "Hard"


class SeverityEnum(str, Enum):
    """Anomali şiddeti"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Anomali tipleri"""

    TUKETIM = "tuketim"
    MALIYET = "maliyet"
    SEFER = "sefer"


class AnomalyResult(BaseModel):
    """Anomali sonucu (Pydantic versiyonu)"""

    tip: AnomalyType
    kaynak_tip: str
    kaynak_id: int
    deger: float
    beklenen_deger: float
    sapma_yuzde: float
    severity: SeverityEnum
    aciklama: str
    rca_summary: Optional[str] = None
    suggested_action: Optional[str] = None
    tarih: Optional[date] = None
    index: Optional[int] = None
    z_score: Optional[float] = None

    @property
    def value(self) -> float:
        return self.deger

    @property
    def message(self) -> str:
        return self.aciklama


# ============== BASE ENTITY ==============


class BaseEntity(BaseModel):
    """Tüm entity'ler için ortak base"""

    id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True, str_strip_whitespace=True, use_enum_values=True
    )


# ============== ARAÇ ==============


class Arac(BaseEntity):
    """Araç entity'si - tam validation ile"""

    plaka: str = Field(..., min_length=7, max_length=12)
    marka: str = Field(..., min_length=2, max_length=50)
    model: Optional[str] = Field(default=None, max_length=50)
    yil: Optional[int] = Field(default=None, ge=1980, le=2030)
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
    notlar: Optional[str] = Field(default=None, max_length=2000)

    # Stats (Joined from Repo)
    toplam_km: Optional[float] = 0.0
    toplam_sefer: Optional[int] = 0
    ort_tuketim: Optional[float] = 0.0

    @computed_field
    @property
    def yas(self) -> Optional[int]:
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


# Helper validator function for plaka
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


class AracCreate(BaseModel):
    """Araç oluşturma DTO"""

    plaka: str
    marka: str
    model: Optional[str] = None
    yil: int = 2020
    tank_kapasitesi: int = 600
    hedef_tuketim: float = 32.0

    # Optional elite specs for creation
    dingil_sayisi: int = 2
    yakit_tipi: str = "DIZEL"
    bos_agirlik_kg: Optional[float] = 8000.0
    hava_direnc_katsayisi: Optional[float] = 0.7
    on_kesit_alani_m2: Optional[float] = 8.5
    motor_verimliligi: Optional[float] = 0.38
    lastik_direnc_katsayisi: Optional[float] = 0.007
    maks_yuk_kapasitesi_kg: Optional[int] = 26000

    notlar: Optional[str] = None

    @field_validator("plaka")
    @classmethod
    def validate_plaka(cls, v: str) -> str:
        return validate_plaka_str(v)

    @field_validator("yil")
    @classmethod
    def validate_yil(cls, v: int) -> int:
        if v < 1980 or v > date.today().year + 1:
            raise ValueError("Geçersiz model yılı")
        return v


class AracUpdate(BaseModel):
    """Araç güncelleme DTO"""

    plaka: Optional[str] = None
    marka: Optional[str] = None
    model: Optional[str] = None
    yil: Optional[int] = None
    tank_kapasitesi: Optional[int] = None
    hedef_tuketim: Optional[float] = None
    aktif: Optional[bool] = None
    notlar: Optional[str] = None

    @field_validator("plaka")
    @classmethod
    def validate_plaka(cls, v: str) -> str:
        if v is None:
            return v
        return validate_plaka_str(v)


# ============== ŞOFÖR ==============


class Sofor(BaseEntity):
    """Şoför entity'si"""

    ad_soyad: str = Field(..., min_length=3, max_length=100)
    telefon: Optional[str] = Field(default=None, max_length=20)
    ise_baslama: Optional[date] = None
    ehliyet_sinifi: str = Field(default="E", max_length=5)

    # Behavioral Stats
    score: float = Field(default=1.0, ge=0.1, le=2.0)
    hiz_disiplin_skoru: float = Field(default=1.0, ge=0.5, le=1.5)
    agresif_surus_faktoru: float = Field(default=1.0, ge=0.5, le=1.5)

    aktif: bool = True
    notlar: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("ad_soyad")
    @classmethod
    def validate_ad_soyad(cls, v: str) -> str:
        """Ad soyadını title case yap"""
        return " ".join(word.capitalize() for word in v.strip().split())


class SoforCreate(BaseModel):
    """Şoför oluşturma DTO"""

    ad_soyad: str = Field(..., min_length=3)
    telefon: Optional[str] = None
    ise_baslama: Optional[date] = None
    ehliyet_sinifi: str = "E"
    notlar: Optional[str] = None

    @field_validator("ad_soyad")
    @classmethod
    def validate_ad_soyad(cls, v: str) -> str:
        return v.strip().title()


# ============== LOKASYON ==============


class Lokasyon(BaseEntity):
    """Lokasyon/güzergah entity'si"""

    cikis_yeri: str = Field(..., min_length=2, max_length=100)
    varis_yeri: str = Field(..., min_length=2, max_length=100)
    mesafe_km: float = Field(..., gt=0, le=5000)
    tahmini_sure_saat: Optional[float] = Field(default=None, ge=0, le=48)
    zorluk: ZorlukEnum = ZorlukEnum.NORMAL
    notlar: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("cikis_yeri", "varis_yeri")
    @classmethod
    def validate_yer(cls, v: str) -> str:
        return v.strip().title()


# ============== YAKIT ALIMI ==============


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


class YakitUpdate(BaseModel):
    """Yakıt alımı güncelleme DTO"""

    tarih: Optional[date] = None
    arac_id: Optional[int] = Field(None, gt=0)
    istasyon: Optional[str] = Field(None, max_length=100)
    fiyat_tl: Optional[Decimal] = Field(None, gt=Decimal("0"))
    litre: Optional[float] = Field(None, gt=0)
    km_sayac: Optional[int] = Field(None, gt=0)
    fis_no: Optional[str] = Field(None, max_length=50)
    depo_durumu: Optional[str] = None
    aktif: Optional[bool] = None

    @field_validator("fiyat_tl", mode="before")
    @classmethod
    def normalize_fiyat(cls, v: Any) -> Decimal:
        if isinstance(v, float):
            return Decimal(f"{v:.2f}")
        return v

    @computed_field
    @property
    def toplam_tutar(self) -> Optional[Decimal]:
        """Toplam tutarı hesapla (yalnız fiyat_tl VE litre'nin ikisi de
        verilmişse — kısmi güncellemede (yalnız istasyon/fis_no/vb. gibi
        alanlar) ikisi de None kalabilir; `YakitRepository.update_yakit`
        zaten bu alanı DB'den okuyup kendi yeniden hesaplıyor (bkz.
        infrastructure/repository.py) — bu computed_field yalnız hem
        fiyat_tl hem litre AYNI istekte verildiğinde anlamlı bir önizleme
        sunar, aksi halde crash etmemesi için None döner.
        """
        if self.fiyat_tl is None or self.litre is None:
            return None
        return round(self.fiyat_tl * Decimal(str(self.litre)), 2)


# ============== SEFER ==============


class Sefer(BaseEntity):
    """Sefer entity'si"""

    sefer_no: Optional[str] = None
    tarih: date
    saat: Optional[str] = Field(default=None, max_length=5)
    # Foreign Keys
    guzergah_id: Optional[int] = None
    arac_id: int = Field(..., gt=0)
    dorse_id: Optional[int] = None
    sofor_id: int = Field(..., gt=0)
    periyot_id: Optional[int] = None

    # Weight Info
    bos_agirlik_kg: int = Field(default=0, ge=0)
    dolu_agirlik_kg: int = Field(default=0, ge=0)
    net_kg: int = Field(default=0, ge=0)

    cikis_yeri: str = Field(..., min_length=2)
    varis_yeri: str = Field(..., min_length=2)
    mesafe_km: float = Field(..., ge=0, le=5000)
    bos_sefer: bool = False
    durum: SeferDurumEnum = SeferDurumEnum.PLANLANDI

    # Hesaplanan alanlar
    dagitilan_yakit: Optional[float] = None
    tuketim: Optional[float] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    flat_distance_km: float = 0.0
    otoban_mesafe_km: Optional[float] = None
    sehir_ici_mesafe_km: Optional[float] = None
    tahmini_tuketim: Optional[float] = None
    tahmin_meta: Optional[Dict[str, Any]] = None
    rota_detay: Optional[Dict[str, Any]] = None

    # Telegram onay akışı
    onay_durumu: Optional[str] = None

    # İlişkili veri (JOIN'den)
    plaka: Optional[str] = None
    sofor_adi: Optional[str] = None
    guzergah_adi: Optional[str] = None

    @computed_field
    @property
    def ton(self) -> float:
        """Net ağırlığı tona çevir"""
        return round(self.net_kg / 1000, 2)

    @field_validator("durum", mode="before")
    @classmethod
    def normalize_durum(cls, v: Optional[str]) -> Optional[str]:
        return ensure_canonical_sefer_status(v, field_name="durum", allow_none=False)


class SeferCreate(BaseModel):
    """Sefer oluşturma DTO"""

    sefer_no: Optional[str] = None
    tarih: date
    saat: Optional[str] = None
    arac_id: int = Field(..., gt=0)
    sofor_id: int = Field(..., gt=0)
    guzergah_id: Optional[int] = Field(None, gt=0)
    dorse_id: Optional[int] = Field(None, gt=0)

    # Weight Info
    bos_agirlik_kg: int = Field(0, ge=0)
    dolu_agirlik_kg: int = Field(0, ge=0)
    net_kg: int = Field(0, ge=0)
    ton: float = Field(0.0, ge=0.0)

    cikis_yeri: str = Field(..., min_length=2)
    varis_yeri: str = Field(..., min_length=2)
    mesafe_km: float = Field(..., gt=0, le=5000)
    bos_sefer: bool = False
    durum: SeferDurumEnum = SeferDurumEnum.PLANLANDI
    ascent_m: float = 0.0
    descent_m: float = 0.0
    flat_distance_km: float = 0.0
    tahmini_tuketim: Optional[float] = None
    notlar: Optional[str] = None

    # Round-trip support
    is_round_trip: bool = False
    return_net_kg: Optional[int] = 0
    return_sefer_no: Optional[str] = None

    @field_validator("cikis_yeri", "varis_yeri")
    @classmethod
    def validate_yer(cls, v: str) -> str:
        return v.strip().title()

    @field_validator("durum", mode="before")
    @classmethod
    def normalize_durum(cls, v: Optional[str]) -> Optional[str]:
        return ensure_canonical_sefer_status(v, field_name="durum", allow_none=False)


class SeferUpdate(BaseModel):
    """Sefer güncelleme DTO"""

    tarih: Optional[date] = None
    saat: Optional[str] = None
    arac_id: Optional[int] = Field(None, gt=0)
    sofor_id: Optional[int] = Field(None, gt=0)
    guzergah_id: Optional[int] = Field(None, gt=0)
    dorse_id: Optional[int] = Field(None, gt=0)
    # Weight Info
    bos_agirlik_kg: Optional[int] = Field(None, ge=0)
    dolu_agirlik_kg: Optional[int] = Field(None, ge=0)
    net_kg: Optional[int] = Field(None, ge=0)
    ton: Optional[float] = Field(None, ge=0.0)

    cikis_yeri: Optional[str] = None
    varis_yeri: Optional[str] = None
    mesafe_km: Optional[float] = Field(None, gt=0)
    bos_sefer: Optional[bool] = None
    durum: Optional[SeferDurumEnum] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    flat_distance_km: Optional[float] = None
    notlar: Optional[str] = None

    # Round-trip support (Update scenarios)
    is_round_trip: Optional[bool] = None
    return_net_kg: Optional[int] = None
    return_sefer_no: Optional[str] = None

    @field_validator("durum", mode="before")
    @classmethod
    def normalize_durum(cls, v: Optional[str]) -> Optional[str]:
        return ensure_canonical_sefer_status(v, field_name="durum", allow_none=True)

    # İptal desteği
    iptal_nedeni: Optional[str] = None

    @model_validator(mode="after")
    def validate_cancel_reason(self) -> "SeferUpdate":
        if self.durum == SeferDurumEnum.IPTAL and not (self.iptal_nedeni or "").strip():
            raise ValueError("Iptal durumunda iptal_nedeni zorunludur")
        return self


# ============== EK MODELLER (Stats & Utils) ==============


class Ayar(BaseEntity):
    """Sistem ayarları"""

    anahtar: str = Field(..., max_length=100)
    deger: str = Field(..., max_length=2000)
    aciklama: Optional[str] = None


class DashboardStats(BaseModel):
    """Dashboard özet istatistikleri"""

    toplam_sefer: int = 0
    aktif_arac: int = 0
    toplam_yakit_litre: float = 0.0
    toplam_maliyet_tl: float = 0.0
    filo_ortalama_tuketim: float = 0.0
    aylik_trend: List[Dict[str, Any]] = []


class VehicleStats(BaseModel):
    """Araç bazlı istatistikler"""

    arac_id: int
    plaka: str
    toplam_sefer: int = 0
    toplam_km: float = 0.0
    ort_tuketim: float = 0.0
    toplam_yakit: float = 0.0
    en_iyi_tuketim: Optional[float] = None
    en_kotu_tuketim: Optional[float] = None
    anomali_sayisi: int = 0
    eei: Optional[float] = None


class DriverStats(BaseModel):
    """Şoför bazlı istatistikler"""

    sofor_id: int
    ad_soyad: str
    toplam_sefer: int = 0
    toplam_km: float = 0.0
    ort_tuketim: float = 0.0
    skor: float = 1.0
    toplam_ton: float = 0.0
    bos_sefer_sayisi: int = 0
    toplam_yakit: float = 0.0
    en_iyi_tuketim: Optional[float] = None
    en_kotu_tuketim: Optional[float] = None
    filo_karsilastirma: float = 0.0
    performans_puani: Optional[float] = None
    trend: str = "stable"
    en_cok_gidilen_guzergah: Optional[str] = None
    guzergah_sayisi: int = 0


class PredictionResult(BaseModel):
    """AI/ML yakıt tahmini sonuç DTO'su (servis katmanı için)."""

    tahmin_l_100km: float
    guven_araligi_alt: float
    guven_araligi_ust: float
    fizik_basarimi: float
    feature_etkisi: Dict[str, float] = {}


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
