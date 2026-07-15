"""Excel satır alanlarının doğrulama/normalize edilmesi.

``_parse_date_flexible`` burada CANONICAL implementasyondur — eskiden
``excel_column_map.py``'de tanımlıydı, ``import_service.py`` yalnız ona
yönlenen bir wrapper taşıyordu (iki dosyada aynı mantığın iki kopyası
gibi görünen ama aslında tek gerçek kaynağı olan bir desendi); taşımada
tek dosyaya birleştirildi.
"""

from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from app.core.exceptions import ImportValidationError
from app.schemas.validators import PLAKA_PATTERN

# Desteklenen tarih formatları (multi-locale support)
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%Y-%m-%dT%H:%M:%S",
]


def parse_date_flexible(val: Any) -> Optional[date]:
    """Farklı tarih formatlarını dene ve date'e çevir"""
    if not val or pd.isna(val):
        return None

    if isinstance(val, (datetime, date)):
        return val if isinstance(val, date) else val.date()

    if isinstance(val, pd.Timestamp):
        return val.date()

    if isinstance(val, str):
        val = val.strip()
        for fmt in DATE_FORMATS:
            try:
                if "T" in val and "T" not in fmt:
                    continue  # Skip simple formats for ISO strings
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


def validate_plaka(plaka: Any) -> str:
    if not plaka:
        raise ImportValidationError(["Plaka boş olamaz"], reason="INVALID_PLAKA")
    p = str(plaka).replace(" ", "").upper()
    if len(p) < 5:
        raise ImportValidationError(["Plaka uzunluğu geçersiz"], reason="INVALID_PLAKA")
    if not PLAKA_PATTERN.match(p):
        raise ImportValidationError(["Plaka formatı geçersiz"], reason="INVALID_PLAKA")
    return p


def validate_name(name: Any) -> str:
    if not name or len(str(name).strip()) < 2:
        raise ImportValidationError(
            ["İsim en az 2 karakter olmalı"], reason="INVALID_NAME"
        )
    return str(name).strip().title()


def validate_location(loc: Any) -> Any:
    return loc


def normalize_text(value: Any) -> str:
    s = str(value or "").strip().upper()
    # Türkçe büyük İ (U+0130) → ASCII I; karşılaştırma tutarlılığı için
    return s.replace("İ", "I")


def validate_numeric(val: Any, field: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        raise ImportValidationError([f"{field} sayı olmalı"], reason="INVALID_NUMERIC")
