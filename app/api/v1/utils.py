"""Shared helpers for API v1 endpoint handlers."""

from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException


def parse_date_param(value: Optional[str], field_name: str = "tarih") -> Optional[date]:
    """Parse an optional YYYY-MM-DD query parameter.

    Returns None when value is None/empty; raises HTTP 400 on invalid format.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz tarih formatı '{field_name}': YYYY-MM-DD kullanın.",
        )
