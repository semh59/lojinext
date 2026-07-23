"""Trip internal Pydantic entities — dalga 16'da app/core/entities/models.py'den
taşındı. `Sefer`, HTTP-yüzeyi `schemas.py`'deki `SeferCreate`/`SeferUpdate`/
`SeferResponse`'dan AYRI, application katmanının repo satırlarını
(`Sefer.model_validate(row)`) doğrulanmış bir entity'ye çeviren dahili
okuma-modelidir (`list_trips.py`, `trip_service.py` facade'ının
`get_by_id`/`get_by_vehicle` metotları; fuel modülü de periyot-sefer
eşleştirmesi için tüketir — bkz. `v2.modules.fuel.domain.period_matcher`).

`DurumEnum` yalnız eski bir SQLite-uyum test yardımcısı (`tests/api/
test_api_integration.py`) tarafından kullanılıyor — gerçek prod çağıranı
yok (kendi docstring'i zaten `YakitAlimi.durum`'un bunu artık kullanmadığını
söylüyor). Silinmedi: maliyeti sıfıra yakın, testin kendisi taşımadan önce
de var olan bir bağımlılıktı.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field, computed_field, field_validator

from v2.modules.shared_kernel.domain.base_entity import BaseEntity
from v2.modules.trip.sefer_status import ensure_canonical_sefer_status


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
