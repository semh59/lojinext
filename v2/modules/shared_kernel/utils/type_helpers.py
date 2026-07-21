"""Shared type conversion utilities."""

from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    """Convert value to float safely, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
