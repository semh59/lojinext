"""Feature E.3 — compute_fleet_carbon + foundation tests."""

from __future__ import annotations

from typing import Any, List, Optional

import pytest


# ── Fake session (paylaşılan stub pattern) ─────────────────────────────
class _FakeMappings:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        return _FakeResult(self._rows)


class _FakeUoW:
    def __init__(self, rows: List[dict]) -> None:
        self.session = _FakeSession(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── compute_fleet_carbon ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_compute_fleet_carbon_empty():
    """Hiç araç yok → total_co2=0, vehicle_count=0."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    uow = _FakeUoW([])
    report = await compute_fleet_carbon(uow, period_days=30)
    assert report.total_co2_kg == 0
    assert report.total_km == 0
    assert report.vehicle_count == 0
    assert report.by_euro_class == {}
    assert report.top_emitters == []


@pytest.mark.asyncio
async def test_compute_fleet_carbon_single_euro_vi_vehicle():
    """1 araç Euro VI, 10K L tüketim, 30K km → CO2 = 26,300, kg/km ≈ 0.877."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    rows = [
        {
            "id": 1,
            "plaka": "34 ABC 123",
            "yil": 2020,
            "total_l": 10_000,
            "total_km": 30_000,
        }
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    # 10000 × 2.63 = 26300
    assert report.total_co2_kg == 26_300
    assert report.total_km == 30_000
    # 26300 / 30000 = 0.877
    assert report.co2_per_km == pytest.approx(0.877, abs=0.001)
    assert report.vehicle_count == 1
    assert "VI" in report.by_euro_class
    assert report.by_euro_class["VI"] == 26_300


@pytest.mark.asyncio
async def test_compute_fleet_carbon_mixed_classes():
    """3 araç, 3 farklı Euro sınıfı → by_euro_class doğru kırılım."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    rows = [
        {
            "id": 1,
            "plaka": "VI1",
            "yil": 2020,
            "total_l": 10_000,
            "total_km": 30_000,
        },  # Euro VI
        {
            "id": 2,
            "plaka": "IV1",
            "yil": 2007,
            "total_l": 5_000,
            "total_km": 15_000,
        },  # Euro IV
        {
            "id": 3,
            "plaka": "O1",
            "yil": 1985,
            "total_l": 3_000,
            "total_km": 10_000,
        },  # Euro 0
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    assert report.vehicle_count == 3
    assert set(report.by_euro_class.keys()) == {"VI", "IV", "0"}
    # Euro 0: 3000 × 3.20 = 9600
    assert report.by_euro_class["0"] == 9_600


@pytest.mark.asyncio
async def test_compute_fleet_carbon_delta_pct_above_benchmark():
    """Filo benchmark üstü → delta_pct > 0."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )
    from v2.modules.analytics_executive.domain.carbon_footprint import (
        SECTOR_BENCHMARK_CO2_PER_KM,
    )

    rows = [
        {
            "id": 1,
            "plaka": "OLD",
            "yil": 1990,
            "total_l": 50_000,
            "total_km": 100_000,
        }
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    assert report.benchmark_co2_per_km == SECTOR_BENCHMARK_CO2_PER_KM
    # 50000 × 3.20 / 100000 = 1.6 kg/km > 0.72 benchmark → büyük + delta
    assert report.delta_pct > 100  # %100+ benchmark üstü


@pytest.mark.asyncio
async def test_compute_fleet_carbon_top_emitters_limit_10():
    """15 araç → top_emitters sadece 10 dönmeli."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    rows = [
        {
            "id": i,
            "plaka": f"P{i:02d}",
            "yil": 2020,
            "total_l": 1_000 * (i + 1),
            "total_km": 5_000,
        }
        for i in range(15)
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    assert report.vehicle_count == 15
    assert len(report.top_emitters) == 10
    # Sıralı (en yüksek CO2 başta)
    co2_list = [e.co2_kg for e in report.top_emitters]
    assert co2_list == sorted(co2_list, reverse=True)


@pytest.mark.asyncio
async def test_compute_fleet_carbon_skip_zero_co2_emitters():
    """Sıfır tüketim olan araç top_emitters'e girmemeli (gürültü)."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    rows = [
        {
            "id": 1,
            "plaka": "ACTIVE",
            "yil": 2020,
            "total_l": 10_000,
            "total_km": 30_000,
        },
        {"id": 2, "plaka": "IDLE", "yil": 2020, "total_l": 0, "total_km": 0},
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    # IDLE araç vehicle_count'a dahil ama top_emitters'a değil
    assert report.vehicle_count == 2
    assert len(report.top_emitters) == 1
    assert report.top_emitters[0].plaka == "ACTIVE"


@pytest.mark.asyncio
async def test_compute_fleet_carbon_zero_km_no_division_error():
    """total_km=0 → co2_per_km=0 (division by zero patlamamalı)."""
    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    rows = [
        {
            "id": 1,
            "plaka": "X",
            "yil": 2020,
            "total_l": 0,
            "total_km": 0,
        }
    ]
    uow = _FakeUoW(rows)
    report = await compute_fleet_carbon(uow, period_days=30)
    assert report.co2_per_km == 0.0
    assert report.delta_pct < 0  # benchmark altı (sıfır)


@pytest.mark.asyncio
async def test_compute_fleet_carbon_period_dates():
    """period_start ve period_end doğru hesaplanmalı."""
    from datetime import date, timedelta

    from v2.modules.analytics_executive.application.get_fleet_carbon import (
        compute_fleet_carbon,
    )

    uow = _FakeUoW([])
    report = await compute_fleet_carbon(uow, period_days=60)
    today = date.today()
    assert report.period_end == today
    assert report.period_start == today - timedelta(days=60)
