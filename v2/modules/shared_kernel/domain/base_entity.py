"""Shared base Pydantic entity — dalga 16'da app/core/entities/models.py'den taşındı.

Gerçekten paylaşılan tek sınıf: fleet'in `Arac` ve trip'in `Sefer` internal
entity'leri bundan miras alır (bkz. ilgili modüllerin `domain/entities.py`'si).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BaseEntity(BaseModel):
    """Tüm entity'ler için ortak base"""

    id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True, str_strip_whitespace=True, use_enum_values=True
    )
