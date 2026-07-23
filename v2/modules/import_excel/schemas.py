"""Import job history/preview/commit response schemas (dalga 16 — eski app/schemas/api_responses.py'den taşındı)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ImportHistoryItem(BaseModel):
    """One row from the import-job history table."""

    id: int
    dosya_adi: str
    aktarim_tipi: str
    durum: str
    toplam: int
    basarili: int
    hatali: int
    baslama_zamani: Optional[datetime] = None
    yukleyen_id: Optional[int] = None

    @field_validator("dosya_adi", "aktarim_tipi", "durum", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("toplam", "basarili", "hatali", mode="before")
    @classmethod
    def heal_ints(cls, v: Any) -> int:
        """Bozuk int değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("baslama_zamani", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> Optional[datetime]:
        """Bozuk datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None


class ImportPreviewResponse(BaseModel):
    filename: Optional[str] = None
    aktarim_tipi: str
    headers: List[str]
    total_rows: int
    preview: List[Dict[str, Any]]


class ImportCommitResponse(BaseModel):
    job_id: int
    basarili: int
    hatali: int
    errors: Dict[str, str] = Field(default_factory=dict)
