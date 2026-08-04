"""Deterministic seasonal fuel-consumption factor.

Vendored (2026-08-04, Task 5 of the prediction_ml_service extraction) from
`v2.modules.route_simulation.application.weather_service.WeatherService.
get_seasonal_factor` -- that method is a pure date-in/float-out calendar
calculation with zero DB/HTTP dependency, so it's copied here rather than
pulling the whole route_simulation module (heavy Mapbox/Redis-dependent
code) into this service. Behavior must stay byte-identical to the source,
including the `settings.SEASONAL_FACTOR_MAX` cap (Faz 7 physical clamp).
"""

from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime as dt_datetime
from typing import Any

from app.config import settings


def get_seasonal_factor(target_date: Any) -> float:
    """Return a seasonal factor for model training and planning.

    This factor is a deterministic seasonal adjustment and is not presented
    to users as live weather truth.
    """
    target = target_date
    if isinstance(target, str):
        try:
            target = dt_date.fromisoformat(target)
        except ValueError:
            target = dt_date.today()
    elif not isinstance(target, (dt_date, dt_datetime)):
        target = dt_date.today()

    month = target.month
    if month in (12, 1, 2):
        raw = 1.10
    elif month in (3, 4, 10, 11):
        raw = 1.03
    elif month in (6, 7, 8):
        raw = 1.05
    else:
        raw = 1.0
    # Faz 7 -- seasonal is a FALLBACK; real cold weather_temperature
    # (<=1.20) is captured elsewhere -> this stays a physical cap
    # (avoids overfit).
    return min(raw, settings.SEASONAL_FACTOR_MAX)
