"""Canonical trip status contract and normalization helpers."""

from __future__ import annotations

import unicodedata
from typing import Dict, Final, Optional, Tuple

TRIP_STATUS_PLANNED: Final = "Planned"
TRIP_STATUS_COMPLETED: Final = "Completed"
TRIP_STATUS_CANCELLED: Final = "Cancelled"

LEGACY_TRIP_STATUS_WAITING: Final = "Pending"
LEGACY_TRIP_STATUS_ON_WAY: Final = "InTransit"
LEGACY_TRIP_STATUS_IN_PROGRESS: Final = "InProgress"
LEGACY_TRIP_STATUS_OK: Final = "Done"

CANONICAL_TRIP_STATUSES: Final[Tuple[str, ...]] = (
    TRIP_STATUS_PLANNED,
    TRIP_STATUS_COMPLETED,
    TRIP_STATUS_CANCELLED,
)
CANONICAL_TRIP_STATUS_SET: Final[set[str]] = set(CANONICAL_TRIP_STATUSES)

READ_OPEN_TRIP_STATUSES: Final[Tuple[str, ...]] = (
    TRIP_STATUS_PLANNED,
    LEGACY_TRIP_STATUS_WAITING,
    LEGACY_TRIP_STATUS_ON_WAY,
    LEGACY_TRIP_STATUS_IN_PROGRESS,
)
READ_COMPLETED_TRIP_STATUSES: Final[Tuple[str, ...]] = (
    TRIP_STATUS_COMPLETED,
    LEGACY_TRIP_STATUS_OK,
)

TRIP_STATUS_TRANSITIONS: Final[Dict[str, Tuple[str, ...]]] = {
    TRIP_STATUS_PLANNED: (
        TRIP_STATUS_COMPLETED,
        TRIP_STATUS_CANCELLED,
    ),
    TRIP_STATUS_COMPLETED: (),
    TRIP_STATUS_CANCELLED: (),
}

_LEGACY_STATUS_ALIASES: Final[Dict[str, str]] = {
    LEGACY_TRIP_STATUS_WAITING: TRIP_STATUS_PLANNED,
    LEGACY_TRIP_STATUS_ON_WAY: TRIP_STATUS_PLANNED,
    LEGACY_TRIP_STATUS_IN_PROGRESS: TRIP_STATUS_PLANNED,
    LEGACY_TRIP_STATUS_OK: TRIP_STATUS_COMPLETED,
    # ASCII variations for backward compatibility
    "Iptal": TRIP_STATUS_CANCELLED,
    "IPTAL": TRIP_STATUS_CANCELLED,
    "iptal": TRIP_STATUS_CANCELLED,
    "Planlandi": TRIP_STATUS_PLANNED,
    "PLANLANDI": TRIP_STATUS_PLANNED,
    "planlandi": TRIP_STATUS_PLANNED,
    "Tamamlandi": TRIP_STATUS_COMPLETED,
    "TAMAMLANDI": TRIP_STATUS_COMPLETED,
    "tamamlandi": TRIP_STATUS_COMPLETED,
    # Old Turkish aliases (legacy data compatibility)
    "Planlandı": TRIP_STATUS_PLANNED,
    "Tamamlandı": TRIP_STATUS_COMPLETED,
    "İptal": TRIP_STATUS_CANCELLED,
    "Bekliyor": TRIP_STATUS_PLANNED,
    "Yolda": TRIP_STATUS_PLANNED,
    "Devam Ediyor": TRIP_STATUS_PLANNED,
    "Tamam": TRIP_STATUS_COMPLETED,
}


def _fold_status(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ascii_only.casefold().split())


_FOLDED_STATUS_MAP: Final[Dict[str, str]] = {
    _fold_status(status): status for status in CANONICAL_TRIP_STATUSES
}
for legacy_value, canonical_value in _LEGACY_STATUS_ALIASES.items():
    _FOLDED_STATUS_MAP[_fold_status(legacy_value)] = canonical_value


def normalize_trip_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    # str(SomeStrEnum.MEMBER) in Python 3.11+ returns "SomeStrEnum.MEMBER"
    # but .value always gives the canonical string — use it when available.
    if hasattr(value, "value"):
        value = value.value  # type: ignore[union-attr]

    raw = str(value).strip()
    if not raw:
        return raw

    if raw in CANONICAL_TRIP_STATUS_SET:
        return raw

    return _FOLDED_STATUS_MAP.get(_fold_status(raw), raw)


def ensure_canonical_trip_status(
    value: Optional[str], *, field_name: str = "status", allow_none: bool = True
) -> Optional[str]:
    normalized = normalize_trip_status(value)

    if normalized is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")

    if normalized not in CANONICAL_TRIP_STATUS_SET:
        allowed = ", ".join(CANONICAL_TRIP_STATUSES)
        raise ValueError(f"Invalid {field_name}: '{value}'. Valid values: {allowed}")

    return normalized
