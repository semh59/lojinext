"""Feature E.5 — Cashflow projection tests (plan §8 uyumlu)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, List, Optional

import pytest


# ── Fake DB + predictor ────────────────────────────────────────────────
class _FakeMappings:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0] if self._rows else {}


class _FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    """SQL string'e bakıp uygun rows döner.

    - 'durum = 'Planned'' → fuel rows
    - 'arac_bakimlari' + 'AVG' → avg_cost row
    """

    def __init__(
        self,
        fuel_rows: List[dict],
        avg_cost: Optional[float],
    ) -> None:
        self._fuel = fuel_rows
        self._avg = avg_cost

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        sql_text = str(sql_obj)
        if "Planned" in sql_text:
            return _FakeResult(self._fuel)
        if "arac_bakimlari" in sql_text and "AVG" in sql_text:
            return _FakeResult([{"avg_cost": self._avg}])
        return _FakeResult([])


class _FakeUoW:
    def __init__(self, fuel_rows, avg_cost) -> None:
        self.session = _FakeSession(fuel_rows, avg_cost)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


class _Pred:
    """MaintenancePredictor.predict_all stub."""

    def __init__(self, preds) -> None:
        self._preds = preds

    async def predict_all(self):
        return self._preds


class _PredItem:
    """Plan §4.1 Prediction dataclass-uyumlu minimal stub."""

    def __init__(
        self,
        *,
        predictable: bool = True,
        predicted_date: Optional[date] = None,
    ) -> None:
        self.predictable = predictable
        self.predicted_date = predicted_date


# ── Testler ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_project_cashflow_empty_fleet():
    """Hiç planlı sefer + hiç bakım tahmini → 0 tüm kalemler."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    uow = _FakeUoW(fuel_rows=[], avg_cost=None)
    projection = await project_cashflow(
        uow,
        horizon_days=84,  # 12 hafta
        diesel_price_tl=50.0,
        avg_bakim_cost_fallback_tl=5000.0,
        predictor=_Pred([]),
    )
    assert projection.total_fuel_tl == 0
    assert projection.total_maintenance_tl == 0
    assert projection.grand_total_tl == 0
    assert len(projection.weeks) == 12
    assert projection.assumptions["avg_bakim_cost_tl"] == 5000.0
    assert projection.assumptions["upcoming_bakim_count"] == 0


@pytest.mark.asyncio
async def test_project_cashflow_fuel_only():
    """Sadece yakıt verisi → maintenance + penalty 0."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    fuel_rows = [
        {"tarih": today + timedelta(days=3), "total_l": 200},
        {"tarih": today + timedelta(days=10), "total_l": 150},
    ]
    uow = _FakeUoW(fuel_rows=fuel_rows, avg_cost=None)
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        diesel_price_tl=50.0,
        predictor=_Pred([]),
    )
    # 200 L → 200 × 50 = 10000 TL (week 0)
    # 150 L → 150 × 50 = 7500 TL (week 1)
    assert projection.weeks[0].fuel_tl == 10_000
    assert projection.weeks[1].fuel_tl == 7_500
    assert projection.total_fuel_tl == 17_500
    assert projection.total_maintenance_tl == 0


@pytest.mark.asyncio
async def test_project_cashflow_maintenance_uses_avg_cost():
    """avg_cost varsa onu kullan; fallback değil."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    preds = [
        _PredItem(predicted_date=today + timedelta(days=5)),
        _PredItem(predicted_date=today + timedelta(days=20)),
    ]
    uow = _FakeUoW(fuel_rows=[], avg_cost=8000.0)
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_Pred(preds),
        avg_bakim_cost_fallback_tl=5000.0,
    )
    # 2 bakım × 8000 (avg, fallback değil) = 16000
    assert projection.total_maintenance_tl == 16_000
    assert projection.assumptions["avg_bakim_cost_tl"] == 8_000
    assert projection.assumptions["upcoming_bakim_count"] == 2


@pytest.mark.asyncio
async def test_project_cashflow_avg_cost_fallback():
    """avg_cost None → fallback değer kullanılır."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    preds = [_PredItem(predicted_date=today + timedelta(days=5))]
    uow = _FakeUoW(fuel_rows=[], avg_cost=None)
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_Pred(preds),
        avg_bakim_cost_fallback_tl=4500.0,
    )
    assert projection.assumptions["avg_bakim_cost_tl"] == 4_500.0
    assert projection.total_maintenance_tl == 4_500


@pytest.mark.asyncio
async def test_project_cashflow_filters_out_of_horizon_bakim():
    """horizon_days dışına düşen bakım tahmini dahil edilmemeli."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    preds = [
        _PredItem(predicted_date=today + timedelta(days=10)),  # dahil
        _PredItem(predicted_date=today + timedelta(days=100)),  # horizon dışı
        _PredItem(predicted_date=today - timedelta(days=5)),  # geçmiş, dahil değil
    ]
    uow = _FakeUoW(fuel_rows=[], avg_cost=6000.0)
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_Pred(preds),
    )
    # Yalnız 1 bakım horizon içinde
    assert projection.assumptions["upcoming_bakim_count"] == 1
    assert projection.total_maintenance_tl == 6_000


@pytest.mark.asyncio
async def test_project_cashflow_unpredictable_excluded():
    """predictable=False bakım çağrısı sayılmamalı."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    preds = [
        _PredItem(predicted_date=today + timedelta(days=5), predictable=True),
        _PredItem(predicted_date=today + timedelta(days=10), predictable=False),
    ]
    uow = _FakeUoW(fuel_rows=[], avg_cost=5000.0)
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_Pred(preds),
    )
    assert projection.assumptions["upcoming_bakim_count"] == 1


@pytest.mark.asyncio
async def test_project_cashflow_horizon_clamp():
    """horizon_days < 7 → 7'ye yükseltilir; > 365 → 365'e indirilir."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    uow = _FakeUoW([], None)
    p_low = await project_cashflow(uow, horizon_days=3, predictor=_Pred([]))
    assert p_low.horizon_days == 7
    p_high = await project_cashflow(uow, horizon_days=500, predictor=_Pred([]))
    assert p_high.horizon_days == 365


@pytest.mark.asyncio
async def test_project_cashflow_grand_total_consistent():
    """grand_total = fuel + maintenance + penalty (cent sapması olmamalı)."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    today = date.today()
    uow = _FakeUoW(
        fuel_rows=[{"tarih": today + timedelta(days=2), "total_l": 100}],
        avg_cost=5000.0,
    )
    preds = [_PredItem(predicted_date=today + timedelta(days=4))]
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_Pred(preds),
        diesel_price_tl=50.0,
    )
    # Cezalar tablosu yokken total_penalty_tl=None → toplama dahil değil.
    # penalty_data_available=True olduğunda toplam = fuel + maintenance + penalty.
    expected = projection.total_fuel_tl + projection.total_maintenance_tl
    if projection.penalty_data_available and projection.total_penalty_tl is not None:
        expected += projection.total_penalty_tl
    assert projection.grand_total_tl == expected


@pytest.mark.asyncio
async def test_project_cashflow_predictor_failure_graceful():
    """Predictor exception fırlatırsa maintenance=0, fuel hesabı çalışır."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    class _BrokenPredictor:
        async def predict_all(self):
            raise RuntimeError("predictor down")

    today = date.today()
    uow = _FakeUoW(
        fuel_rows=[{"tarih": today + timedelta(days=2), "total_l": 100}],
        avg_cost=5000.0,
    )
    projection = await project_cashflow(
        uow,
        horizon_days=84,
        predictor=_BrokenPredictor(),
        diesel_price_tl=50.0,
    )
    assert projection.total_fuel_tl == 5_000  # 100 × 50
    assert projection.total_maintenance_tl == 0


@pytest.mark.asyncio
async def test_project_cashflow_weeks_count_matches_horizon():
    """AUDIT-026: weeks tüm horizon'u kapsar (ceil), artık kalan günler düşmez."""
    from v2.modules.analytics_executive.application.project_cashflow import (
        project_cashflow,
    )

    uow = _FakeUoW([], None)
    p30 = await project_cashflow(uow, horizon_days=30, predictor=_Pred([]))
    assert len(p30.weeks) == 5  # ceil(30/7) = 5 (gün 28-29 artık kapsanır)
    p90 = await project_cashflow(uow, horizon_days=90, predictor=_Pred([]))
    assert len(p90.weeks) == 13  # ceil(90/7) = 13 (gün 84-89 artık kapsanır)
