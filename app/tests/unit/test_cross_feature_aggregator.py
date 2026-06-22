"""Feature E.6 — Cross-feature aggregator tests (plan §9 uyumlu)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import pytest


# ── Fake DB session (SQL substring routing) ───────────────────────────
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
    """SQL string'e bakıp route eder:
    - 'FROM araclar' → arac_rows
    - 'coaching_deliveries' → coaching_row
    - 'fuel_investigations' → theft_row
    - 'arac_bakimlari' (fetch_health_input içindeki) → health_row
    """

    def __init__(
        self,
        *,
        arac_rows: List[dict],
        coaching: dict,
        theft: dict,
        health_by_arac_id: dict[int, dict],
    ) -> None:
        self._arac = arac_rows
        self._coaching = coaching
        self._theft = theft
        self._health = health_by_arac_id

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        sql_text = str(sql_obj)
        if "coaching_deliveries" in sql_text:
            return _FakeResult([self._coaching])
        if "fuel_investigations" in sql_text:
            return _FakeResult([self._theft])
        # AUDIT-083: D.4 artık fetch_health_input_batch (unnest(:arac_ids::int[]))
        # kullanıyor — eski per-araç :aid yolu değil. Her arac_id için satır döndür.
        if "arac_bakimlari" in sql_text and params and "arac_ids" in params:
            rows = []
            for aid in params["arac_ids"]:
                h = self._health.get(
                    int(aid),
                    {"last_periyodik": None, "open_ariza": 0, "open_acil": 0},
                )
                rows.append({"arac_id": int(aid), **h})
            return _FakeResult(rows)
        if "FROM araclar" in sql_text:
            return _FakeResult(self._arac)
        return _FakeResult([])


class _FakeUoW:
    def __init__(self, **kw) -> None:
        self.session = _FakeSession(**kw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── Helpers ────────────────────────────────────────────────────────────
def _utc_days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# ── Testler ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_aggregate_empty_data():
    """Hiç araç, koçluk, hırsızlık verisi yok → 3 kalem 0."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[],
        coaching={"evaluated": 0, "avg_delta": 0},
        theft={"real_thefts": 0, "avg_sapma": 0},
        health_by_arac_id={},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    assert impact.maintenance_delay_loss_tl == 0
    assert impact.coaching_savings_tl == 0
    assert impact.theft_loss_tl == 0
    assert impact.period_days == 90
    assert impact.confidence == 0.55  # plan §9 v1


@pytest.mark.asyncio
async def test_aggregate_d4_maintenance_loss_calculation():
    """D.4 factor 1.07 araç → period_l × 0.07 × diesel_price = ekstra TL."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[{"id": 1, "period_l": 10_000}],
        # 400 gün önce PERIYODIK → factor 1.07
        health_by_arac_id={
            1: {
                "last_periyodik": _utc_days_ago(400),
                "open_ariza": 0,
                "open_acil": 0,
            },
        },
        coaching={"evaluated": 0, "avg_delta": 0},
        theft={"real_thefts": 0, "avg_sapma": 0},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    # extra_pct = 1.07 - 1.0 = 0.07; 10000 × 0.07 = 700 L × 50 = 35000 TL
    assert impact.maintenance_delay_loss_tl == 35_000


@pytest.mark.asyncio
async def test_aggregate_d4_skips_factor_at_or_below_one():
    """factor ≤ 1.0 araç sayılmamalı (bonus/nötr factor)."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[
            {"id": 1, "period_l": 10_000},  # fresh PERIYODIK → factor 0.96
            {"id": 2, "period_l": 10_000},  # PERIYODIK yok → factor 1.05 (NO_HISTORY)
        ],
        health_by_arac_id={
            # Fresh PERIYODIK (10g önce) → factor 0.96 (skip)
            1: {
                "last_periyodik": _utc_days_ago(10),
                "open_ariza": 0,
                "open_acil": 0,
            },
            # No history → factor 1.05 (dahil)
            2: {
                "last_periyodik": None,
                "open_ariza": 0,
                "open_acil": 0,
            },
        },
        coaching={"evaluated": 0, "avg_delta": 0},
        theft={"real_thefts": 0, "avg_sapma": 0},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    # Sadece araç 2 sayılmalı: 10000 × 0.05 = 500 L × 50 = 25000 TL
    assert impact.maintenance_delay_loss_tl == 25_000


@pytest.mark.asyncio
async def test_aggregate_a5_coaching_with_positive_delta():
    """AUDIT-082: tasarruf = evaluated × delta × period_km × IMPACT_RATIO × diesel.

    period_km yıllık km'nin period_days/365 oranıdır; eski formül sürücü sayısını
    (evaluated) ve period ölçeğini yok sayıyordu.
    """
    from app.core.services.cross_feature_aggregator import (
        COACHING_IMPACT_RATIO,
        COACHING_KM_PER_DRIVER_AVG,
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[],
        coaching={"evaluated": 5, "avg_delta": 0.1},  # +0.10 puan
        theft={"real_thefts": 0, "avg_sapma": 0},
        health_by_arac_id={},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    period_km = COACHING_KM_PER_DRIVER_AVG * (90 / 365.0)
    expected_l = 5 * 0.1 * period_km * COACHING_IMPACT_RATIO
    expected_tl = round(expected_l * 50.0, 0)
    assert impact.coaching_savings_tl == expected_tl


@pytest.mark.asyncio
async def test_aggregate_a5_zero_delta_no_savings():
    """avg_delta = 0 (veya negatif) → coaching_savings = 0."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[],
        coaching={"evaluated": 10, "avg_delta": 0.0},
        theft={"real_thefts": 0, "avg_sapma": 0},
        health_by_arac_id={},
    )
    impact = await aggregate_cross_feature(uow)
    assert impact.coaching_savings_tl == 0


@pytest.mark.asyncio
async def test_aggregate_b_theft_loss_calculation():
    """resolved real_theft × avg_sapma × THEFT_AVG_TRIP_L × diesel = TL."""
    from app.core.services.cross_feature_aggregator import (
        THEFT_AVG_TRIP_L,
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[],
        coaching={"evaluated": 0, "avg_delta": 0},
        theft={"real_thefts": 3, "avg_sapma": 25.0},  # %25 sapma
        health_by_arac_id={},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    # 3 × 200 L × 0.25 = 150 L × 50 = 7500 TL
    expected_tl = round(3 * THEFT_AVG_TRIP_L * 0.25 * 50.0, 0)
    assert impact.theft_loss_tl == expected_tl


@pytest.mark.asyncio
async def test_aggregate_b_zero_thefts():
    """Hiç real_theft yok → theft_loss = 0."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[],
        coaching={"evaluated": 0, "avg_delta": 0},
        theft={"real_thefts": 0, "avg_sapma": 0},
        health_by_arac_id={},
    )
    impact = await aggregate_cross_feature(uow)
    assert impact.theft_loss_tl == 0


@pytest.mark.asyncio
async def test_aggregate_all_three_motors_together():
    """3 motor da veriye sahip → 3 kalem dolu, confidence sabit 0.55."""
    from app.core.services.cross_feature_aggregator import (
        aggregate_cross_feature,
    )

    uow = _FakeUoW(
        arac_rows=[{"id": 1, "period_l": 5_000}],
        health_by_arac_id={
            1: {
                "last_periyodik": _utc_days_ago(400),  # factor 1.07
                "open_ariza": 0,
                "open_acil": 0,
            }
        },
        coaching={"evaluated": 3, "avg_delta": 0.05},
        theft={"real_thefts": 1, "avg_sapma": 20.0},
    )
    impact = await aggregate_cross_feature(
        uow,
        period_days=90,
        diesel_price_tl=50.0,
    )
    assert impact.maintenance_delay_loss_tl > 0
    assert impact.coaching_savings_tl > 0
    assert impact.theft_loss_tl > 0
    assert impact.confidence == 0.55
