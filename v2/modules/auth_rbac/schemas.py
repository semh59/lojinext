"""
Kullanıcı (User) + Rol + Preference Pydantic şemaları - LojiNext auth_rbac.

Gelişmiş RBAC ve Email tabanlı kimlik doğrulama; kullanıcıya özel tercihler
(kayıtlı filtreler, sütunlar vb.).
"""

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from v2.modules.shared_kernel.schemas.validators import validate_password_complexity

_DEGER_MAX_BYTES = 10_240  # 10 KB per preference value


class RolRead(BaseModel):
    """Rol response şeması"""

    id: int
    ad: str
    yetkiler: dict
    olusturma: datetime

    model_config = ConfigDict(from_attributes=True)


class RolCreate(BaseModel):
    """Rol olusturma semasi."""

    ad: str = Field(..., min_length=2, max_length=50)
    yetkiler: dict[str, StrictBool]

    @field_validator("ad")
    @classmethod
    def validate_role_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Rol adi bos olamaz")
        return cleaned

    @field_validator("yetkiler")
    @classmethod
    def validate_permissions(
        cls, value: dict[str, StrictBool]
    ) -> dict[str, StrictBool]:
        if not value:
            raise ValueError("Yetkiler bos olamaz")

        normalized: dict[str, StrictBool] = {}
        for key, enabled in value.items():
            cleaned_key = key.strip()
            if not cleaned_key:
                raise ValueError("Yetki anahtari bos olamaz")
            normalized[cleaned_key] = enabled

        return normalized


class KullaniciBase(BaseModel):
    """Kullanıcı base model - ortak alanlar."""

    email: str = Field(..., description="Kurumsal e-posta adresi veya kullanıcı adı")
    ad_soyad: str = Field(..., min_length=2, max_length=100)
    aktif: bool = True
    sofor_id: Optional[int] = None


class KullaniciCreate(KullaniciBase):
    """Kullanıcı oluşturma şeması."""

    rol_id: int
    sifre: str = Field(..., min_length=8, max_length=128)

    @field_validator("sifre")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Password complexity validation."""
        return validate_password_complexity(v)


class KullaniciUpdate(BaseModel):
    """Kullanıcı güncelleme şeması."""

    email: Optional[str] = None
    ad_soyad: Optional[str] = None
    rol_id: Optional[int] = None
    aktif: Optional[bool] = None
    sifre: Optional[str] = Field(None, min_length=8, max_length=128)

    @field_validator("sifre")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Password complexity validation for updates."""
        if v is None:
            return v
        return validate_password_complexity(v)


class KullaniciRead(KullaniciBase):
    """Kullanıcı response şeması."""

    id: Optional[int] = None
    rol_id: int
    rol: Optional[RolRead] = None
    created_at: datetime
    updated_at: datetime
    son_giris: Optional[datetime] = None
    son_giris_ip: Optional[str] = None
    sifre_degisim_tarihi: Optional[datetime] = None

    @field_validator("ad_soyad", mode="before")
    @classmethod
    def heal_name(cls, v: object) -> str:
        """Boş/bozuk isim alanını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYEN KULLANICI"
        name = str(v).strip()
        return name if len(name) >= 2 else "BİLİNMİYEN KULLANICI"

    @field_validator("email", mode="before")
    @classmethod
    def heal_email(cls, v: object) -> str:
        """Boş/bozuk email alanını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "no-email@system.local"
        return str(v).strip()

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def heal_required_datetime(cls, v: object) -> datetime:
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

    @field_validator("son_giris", "sifre_degisim_tarihi", mode="before")
    @classmethod
    def heal_optional_datetime(cls, v: object) -> Optional[datetime]:
        """Bozuk optional datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None

    @field_validator("son_giris_ip", mode="before")
    @classmethod
    def heal_ip(cls, v: object) -> Optional[str]:
        """Boş/bozuk IP alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    model_config = ConfigDict(from_attributes=True)


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
