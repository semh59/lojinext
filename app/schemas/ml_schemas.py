from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class MLTaskBase(BaseModel):
    arac_id: int
    tetikleyen_kullanici_id: Optional[int] = None


class MLTrainingCreate(MLTaskBase):
    pass


class MLTaskRead(MLTaskBase):
    id: int
    hedef_versiyon: int
    ilerleme: float
    durum: str
    baslangic_zaman: Optional[datetime] = None
    bitis_zaman: Optional[datetime] = None
    hata_detay: Optional[str] = None
    # `EgitimKuyrugu`'nun gerçek kolon adı `olusturma` (bkz.
    # app/database/models.py) — `olusturma_tarihi` hiç var olmayan bir alan
    # adıydı. from_attributes=True ile model_validate(orm_obj) her satırda
    # ResponseValidationError'a (500) düşüyordu; POST /admin/ml/train/{id}
    # gerçek backend'e karşı curl ile doğrulanarak yakalandı.
    olusturma: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelVersionBase(BaseModel):
    arac_id: int
    versiyon: int
    r2_skoru: Optional[float] = None
    mae: Optional[float] = None
    mape: Optional[float] = None
    rmse: Optional[float] = None


class ModelVersionRead(ModelVersionBase):
    id: int
    veri_sayisi: int
    model_dosya_yolu: str
    kullanilan_ozellikler: Dict[str, Any]
    olusturma_zaman: datetime

    model_config = ConfigDict(from_attributes=True)
