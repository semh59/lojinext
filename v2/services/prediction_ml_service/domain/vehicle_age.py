"""Deterministic vehicle-age-derived factors.

Vendored (2026-08-04, Task 5 of the prediction_ml_service extraction) from
`v2.modules.fleet.domain.entities.Arac`'s `yas`/`yas_faktoru`/`euro_sinifi`
computed_field properties -- pure int-in/float-out calculations with no
DB dependency. The fleet.Arac Pydantic entity itself cannot be imported
here (fleet physically lives in the main backend's codebase), so only
this pure logic is copied; behavior must stay byte-identical to source.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple


def compute_vehicle_age_factor(yil: Optional[int]) -> Tuple[Optional[int], float]:
    """Return (yas, yas_faktoru) for a vehicle's model year."""
    yas = date.today().year - yil if yil else None
    if yas is None:
        return None, 1.0
    if yas <= 2:
        return yas, 0.98
    if yas <= 5:
        return yas, 1.0
    if yas <= 10:
        return yas, 1.02 + (yas - 5) * 0.005
    return yas, 1.05 + (yas - 10) * 0.01


def compute_euro_class(yil: Optional[int]) -> str:
    """Estimated Euro emission class from a vehicle's model year."""
    if not yil:
        return "Bilinmiyor"
    if yil >= 2014:
        return "Euro 6"
    if yil >= 2009:
        return "Euro 5"
    if yil >= 2006:
        return "Euro 4"
    return "Euro 3"
