import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DEGER_MAX_BYTES = 10_240  # 10 KB per preference value


class PreferenceBase(BaseModel):
    modul: str = Field(..., max_length=64)
    ayar_tipi: str = Field(..., max_length=64)
    deger: Any
    ad: Optional[str] = Field(None, max_length=128)
    is_default: bool = False

    @field_validator("deger", mode="before")
    @classmethod
    def limit_deger_size(cls, v: Any) -> Any:
        try:
            serialized = json.dumps(v, ensure_ascii=False)
        except (TypeError, ValueError):
            raise ValueError("deger JSON serileştirilemiyor")
        if len(serialized.encode()) > _DEGER_MAX_BYTES:
            raise ValueError(f"deger {_DEGER_MAX_BYTES // 1024} KB sınırını aşıyor")
        return v


class PreferenceCreate(PreferenceBase):
    pass


class PreferenceItem(PreferenceBase):
    id: int
    kullanici_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PreferenceListResponse(BaseModel):
    items: List[PreferenceItem]
