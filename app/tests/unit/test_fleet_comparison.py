"""Reports v2 RV2.2 — Fleet comparison tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import pytest


# ── Fake DB ────────────────────────────────────────────────────────────
class _FakeMappings:
    def __init__(self, rows) -> None:
        self._rows = rows

    def one(self):
        return self._rows[0] if self._rows else {}


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    """Tarih başına farklı period metrik döner.

    `start` parametresine bakarak current/previous ayırır.
    """

    def __init__(
        self,
        *,
        current_metrics: dict,
        previous_metrics: dict,
        current_start: date,
    ) -> None:
        self._current = current_metrics
        self._previous = previous_metrics
        self._current_start = current_start

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        params = params or {}
        if params.get("start") == self._current_start:
            return _FakeResult([self._current])
        return _FakeResult([self._previous])


class _FakeUoW:
    def __init__(self, **kw) -> None:
        self.session = _FakeSession(**kw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── _delta_pct ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "current, previous, expected",
    [
        (100, 100, 0.0),
        (110, 100, 10.0),
        (90, 100, -10.0),
        (100, 0, None),  # previous=0 → anlamsız
        (0, 100, -100.0),
        (33.33, 30, 11.1),  # yuvarlanmış
    ],
)
def test_delta_pct(current, previous, expected):
    from app.core.services.fleet_comparison import _delta_pct

    assert _delta_pct(current, previous) == expected


# ── _period_dates ──────────────────────────────────────────────────────
def test_period_dates_week():
    from app.core.services.fleet_comparison import _period_dates

    cs, ce, ps, pe = _period_dates("week")
    assert (ce - cs).days == 7
    assert (pe - ps).days == 7
    assert pe == cs  # önceki dönem mevcut'un başlangıcında biter


def test_period_dates_month():
    from app.core.services.fleet_comparison import _period_dates

    cs, ce, ps, pe = _period_dates("month")
    assert (ce - cs).days == 30
    assert (pe - ps).days == 30


# ── compute_fleet_comparison ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_compute_comparison_zero_previous_period():
    """Önceki period boşsa delta None döner."""
    from datetime import date as _date

    from app.core.services.fleet_comparison import compute_fleet_comparison

    today = _date.today()
    current_start = today - timedelta(days=30)
    uow = _FakeUoW(
        current_metrics={"fuel_l": 1000, "trip_count": 5, "anomaly_count": 2},
        previous_metrics={"fuel_l": 0, "trip_count": 0, "anomaly_count": 0},
        current_start=current_start,
    )
    result = await compute_fleet_comparison(
        uow,
        period="month",
        diesel_price_tl=50.0,
    )
    assert result.fuel_l_delta_pct is None
    assert result.trip_delta_pct is None
    assert result.anomaly_delta_pct is None
    assert result.current.fuel_l == 1000
    assert result.current.fuel_cost_tl == 50_000  # 1000 × 50


@pytest.mark.asyncio
async def test_compute_comparison_positive_delta():
    """Bu ay 1100 L, geçen 1000 L → +10% delta."""
    from datetime import date as _date

    from app.core.services.fleet_comparison import compute_fleet_comparison

    current_start = _date.today() - timedelta(days=30)
    uow = _FakeUoW(
        current_metrics={"fuel_l": 1100, "trip_count": 15, "anomaly_count": 5},
        previous_metrics={"fuel_l": 1000, "trip_count": 12, "anomaly_count": 4},
        current_start=current_start,
    )
    result = await compute_fleet_comparison(
        uow,
        period="month",
        diesel_price_tl=50.0,
    )
    assert result.fuel_l_delta_pct == 10.0
    assert result.fuel_cost_delta_pct == 10.0
    assert result.trip_delta_pct == 25.0  # (15-12)/12 = 25%
    assert result.anomaly_delta_pct == 25.0


@pytest.mark.asyncio
async def test_compute_comparison_negative_delta_improvement():
    """Bu ay daha az yakıt → negative delta (iyileşme)."""
    from datetime import date as _date

    from app.core.services.fleet_comparison import compute_fleet_comparison

    current_start = _date.today() - timedelta(days=7)
    uow = _FakeUoW(
        current_metrics={"fuel_l": 900, "trip_count": 10, "anomaly_count": 1},
        previous_metrics={"fuel_l": 1000, "trip_count": 10, "anomaly_count": 5},
        current_start=current_start,
    )
    result = await compute_fleet_comparison(
        uow,
        period="week",
    )
    assert result.fuel_l_delta_pct == -10.0
    assert result.anomaly_delta_pct == -80.0  # 5 → 1: -80%
    assert result.period == "week"
