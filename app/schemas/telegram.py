from datetime import date, datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field


class SeferOnayRequest(BaseModel):
    onay_notu: Optional[str] = Field(None, max_length=500)


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

    model_config = {"from_attributes": True, "populate_by_name": True}


class SeferPDFRequest(BaseModel):
    baslangic_tarihi: date
    bitis_tarihi: date


class SoforTelegramInfo(BaseModel):
    sofor_id: int
    ad_soyad: str
    aktif: bool
