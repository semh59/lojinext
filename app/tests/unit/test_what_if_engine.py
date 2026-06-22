"""Feature E.2 — What-if engine testleri (DB'siz, FakeSession ile)."""

from __future__ import annotations

from typing import Any, List, Optional

import pytest


# ── Fake DB session (sql string'e bakıp uygun rows döner) ───────────────
class _FakeMappings:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0] if self._rows else {}


class _FakeResult:
    def __init__(self, rows: List[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeSession:
    """SQL içeriğine göre farklı rows döndüren stub."""

    def __init__(self, response_map: dict[str, List[dict]]) -> None:
        # response_map: substring → rows
        self._map = response_map

    async def execute(self, sql_obj: Any, params: Optional[dict] = None):
        sql_text = str(sql_obj)
        for substring, rows in self._map.items():
            if substring in sql_text:
                return _FakeResult(rows)
        return _FakeResult([])


class _FakeUoW:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


# ── fleet_renewal ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_fleet_renewal_no_eligible_vehicles():
    from app.core.services.what_if_engine import simulate_fleet_renewal

    uow = _FakeUoW(_FakeSession({"a.yil < EXTRACT": []}))
    result = await simulate_fleet_renewal(
        uow,
        max_age_years=15,
        replacement_cost_per_vehicle_tl=2_000_000,
    )
    assert result.scenario_type == "fleet_renewal"
    assert result.yearly_savings_tl == 0
    assert result.upfront_cost_tl == 0
    assert result.payback_years is None
    assert "üstünde aktif araç yok" in result.reasons[0]


@pytest.mark.asyncio
async def test_fleet_renewal_with_3_vehicles_payback():
    from app.core.services.what_if_engine import simulate_fleet_renewal

    rows = [
        {
            "id": 1,
            "plaka": "A",
            "yil": 2008,
            "yearly_consum_l": 30_000,
            "yearly_km": 100_000,
        },
        {
            "id": 2,
            "plaka": "B",
            "yil": 2005,
            "yearly_consum_l": 28_000,
            "yearly_km": 95_000,
        },
        {
            "id": 3,
            "plaka": "C",
            "yil": 2007,
            "yearly_consum_l": 35_000,
            "yearly_km": 110_000,
        },
    ]
    uow = _FakeUoW(_FakeSession({"a.yil < EXTRACT": rows}))
    result = await simulate_fleet_renewal(
        uow,
        max_age_years=15,
        replacement_cost_per_vehicle_tl=2_000_000,
        expected_l_100km_improvement_pct=15.0,
        diesel_price_tl=50.0,
    )
    # Yıllık L: 30000+28000+35000 = 93000; tasarruf %15 = 13950 L
    # TL: 13950 × 50 = 697_500
    assert result.yearly_savings_tl == 697_500
    assert result.upfront_cost_tl == 6_000_000  # 3 × 2M
    # Payback = 6M / 697_500 ≈ 8.6 yıl
    assert result.payback_years == pytest.approx(8.6, abs=0.1)
    # CO2 azaltımı pozitif olmalı (eski araç vs Euro VI)
    assert result.co2_reduction_kg > 0
    assert result.confidence == 0.6  # n=3 < 5


@pytest.mark.asyncio
async def test_fleet_renewal_confidence_with_5_plus_vehicles():
    from app.core.services.what_if_engine import simulate_fleet_renewal

    rows = [
        {
            "id": i,
            "plaka": f"P{i}",
            "yil": 2008,
            "yearly_consum_l": 25_000,
            "yearly_km": 90_000,
        }
        for i in range(6)
    ]
    uow = _FakeUoW(_FakeSession({"a.yil < EXTRACT": rows}))
    result = await simulate_fleet_renewal(
        uow,
        max_age_years=15,
        replacement_cost_per_vehicle_tl=1_000_000,
    )
    assert result.confidence == 0.8  # n>=5


# ── training ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_training_no_drivers():
    from app.core.services.what_if_engine import simulate_training_program

    uow = _FakeUoW(
        _FakeSession(
            {
                "COUNT(DISTINCT s.id)": [{"driver_count": 0, "yearly_l": 0}],
            }
        )
    )
    result = await simulate_training_program(
        uow,
        improvement_pct=5.0,
        training_cost_per_driver_tl=3000,
    )
    assert result.scenario_type == "training"
    assert result.yearly_savings_tl == 0
    assert result.confidence == 0.5
    assert "Aktif şoför veya yıllık sefer verisi yok" in result.reasons[0]


@pytest.mark.asyncio
async def test_training_with_drivers_and_data():
    from app.core.services.what_if_engine import simulate_training_program

    uow = _FakeUoW(
        _FakeSession(
            {
                "COUNT(DISTINCT s.id)": [{"driver_count": 20, "yearly_l": 500_000}],
            }
        )
    )
    result = await simulate_training_program(
        uow,
        improvement_pct=5.0,
        training_cost_per_driver_tl=3000,
        diesel_price_tl=50.0,
    )
    # Tasarruf: 500_000 × 0.05 = 25_000 L × 50 = 1_250_000 TL
    assert result.yearly_savings_tl == 1_250_000
    # Upfront: 20 × 3000 = 60_000 TL
    assert result.upfront_cost_tl == 60_000
    # Payback = 60K / 1.25M ≈ 0.05 yıl
    assert result.payback_years == pytest.approx(0.05, abs=0.02)
    # 5-yıl ROI çok yüksek olmalı
    assert result.five_year_roi_pct > 1000


# ── route_portfolio ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_route_portfolio_no_data():
    from app.core.services.what_if_engine import simulate_route_portfolio

    uow = _FakeUoW(_FakeSession({"FROM lokasyonlar": []}))
    result = await simulate_route_portfolio(
        uow,
        drop_bottom_n=3,
        iterations=50,
    )
    assert result.scenario_type == "route_portfolio"
    assert result.yearly_savings_tl == 0
    assert "Yeterli sefer-bazlı güzergah verisi yok" in result.reasons[0]


@pytest.mark.asyncio
async def test_route_portfolio_monte_carlo_band_present():
    """3 worst route → P10/P50/P90 dolu olmalı."""
    from app.core.services.what_if_engine import simulate_route_portfolio

    rows = [
        # avg_consum > avg_predicted → pozitif deviation → tasarruf var
        {
            "id": 1,
            "cikis_yeri": "A",
            "varis_yeri": "B",
            "trip_count": 10,
            "avg_consum": 50.0,
            "avg_predicted": 40.0,
            "avg_km": 100,
        },
        {
            "id": 2,
            "cikis_yeri": "C",
            "varis_yeri": "D",
            "trip_count": 8,
            "avg_consum": 60.0,
            "avg_predicted": 50.0,
            "avg_km": 120,
        },
        {
            "id": 3,
            "cikis_yeri": "E",
            "varis_yeri": "F",
            "trip_count": 12,
            "avg_consum": 45.0,
            "avg_predicted": 40.0,
            "avg_km": 90,
        },
    ]
    uow = _FakeUoW(_FakeSession({"FROM lokasyonlar": rows}))
    result = await simulate_route_portfolio(
        uow,
        drop_bottom_n=3,
        iterations=100,
        diesel_price_tl=50.0,
        random_seed=42,
    )
    assert result.monte_carlo is not None
    mc = result.monte_carlo
    # P10 ≤ P50 ≤ P90
    assert mc["p10"] <= mc["p50"] <= mc["p90"]
    assert mc["iterations"] == 100
    assert result.yearly_savings_tl == mc["p50"]


@pytest.mark.asyncio
async def test_route_portfolio_deterministic_with_seed():
    """Aynı seed → aynı sonuç (regression için)."""
    from app.core.services.what_if_engine import simulate_route_portfolio

    rows = [
        {
            "id": 1,
            "cikis_yeri": "A",
            "varis_yeri": "B",
            "trip_count": 10,
            "avg_consum": 50.0,
            "avg_predicted": 40.0,
            "avg_km": 100,
        }
    ]
    uow1 = _FakeUoW(_FakeSession({"FROM lokasyonlar": rows}))
    uow2 = _FakeUoW(_FakeSession({"FROM lokasyonlar": rows}))
    r1 = await simulate_route_portfolio(
        uow1,
        drop_bottom_n=1,
        iterations=50,
        random_seed=123,
    )
    r2 = await simulate_route_portfolio(
        uow2,
        drop_bottom_n=1,
        iterations=50,
        random_seed=123,
    )
    assert r1.monte_carlo == r2.monte_carlo


# ── euro_class_for_year (E.3 foundation) ──────────────────────────────
def test_euro_class_for_year_boundaries():
    from app.core.ml.carbon_footprint import euro_class_for_year

    assert euro_class_for_year(2020).name == "VI"
    assert euro_class_for_year(2014).name == "VI"
    assert euro_class_for_year(2013).name == "V"
    assert euro_class_for_year(2009).name == "V"
    assert euro_class_for_year(2008).name == "IV"
    assert euro_class_for_year(2005).name == "III"
    assert euro_class_for_year(2000).name == "II"
    assert euro_class_for_year(1995).name == "I"
    assert euro_class_for_year(1990).name == "0"
    assert euro_class_for_year(None).name == "0"
    assert euro_class_for_year(0).name == "0"


def test_euro_class_co2_monotonic():
    """Yeni sınıflar düşük CO2/L, eski yüksek olmalı."""
    from app.core.ml.carbon_footprint import euro_class_for_year

    factors = [
        euro_class_for_year(yil).co2_factor_kg_per_l
        for yil in [2020, 2010, 2007, 2003, 1998, 1993, 1985]
    ]
    # Yeniden eskiye: monotonic artış
    assert factors == sorted(factors)
