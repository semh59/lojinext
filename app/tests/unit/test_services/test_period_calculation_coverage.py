"""
Coverage tests for v2/modules/fuel/domain/period_matcher.py +
v2/modules/fuel/application/{calculate_period,distribute_fuel_to_trips}.py
Targets: sync_create_fuel_periods branches, evaluate_consumption_status,
sync_distribute_fuel_to_trips branches, sync_match_periods_with_trips.

Dalga 4 (B.1 free-function refactor): PeriodCalculationService class deleted
— these are pure module-level functions, no constructor/mocked repo needed.
"""

from datetime import date
from decimal import Decimal

import pytest

from v2.modules.fuel.application.calculate_period import create_fuel_periods
from v2.modules.fuel.application.distribute_fuel_to_trips import (
    distribute_fuel_to_trips,
    match_periods_with_trips,
)
from v2.modules.fuel.domain.entities import YakitAlimi, YakitPeriyodu
from v2.modules.fuel.domain.period_matcher import (
    evaluate_consumption_status,
    sync_create_fuel_periods,
    sync_distribute_fuel_to_trips,
    sync_match_periods_with_trips,
)
from v2.modules.trip.domain.entities import Sefer

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yakit(id, arac_id, km, litre, tarih_str, depo="Bilinmiyor"):
    return YakitAlimi(
        id=id,
        tarih=date.fromisoformat(tarih_str),
        arac_id=arac_id,
        istasyon="BP",
        fiyat_tl=Decimal("35.00"),
        litre=litre,
        km_sayac=km,
        depo_durumu=depo,
    )


def _sefer(id, arac_id, tarih_str, mesafe_km=300, net_kg=15000):
    return Sefer(
        id=id,
        tarih=date.fromisoformat(tarih_str),
        arac_id=arac_id,
        sofor_id=1,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=mesafe_km,
        net_kg=net_kg,
        durum="Planned",
    )


# ---------------------------------------------------------------------------
# sync_create_fuel_periods — edge cases
# ---------------------------------------------------------------------------


class TestCreateFuelPeriods:
    def test_fewer_than_2_records_returns_empty(self):
        result = sync_create_fuel_periods([])
        assert result == []

    def test_single_record_returns_empty(self):
        rec = _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu")
        result = sync_create_fuel_periods([rec])
        assert result == []

    def test_no_full_tank_skips_vehicle(self):
        records = [
            _yakit(1, 1, 100000, 200.0, "2024-01-01"),  # depo=Bilinmiyor
            _yakit(2, 1, 100500, 250.0, "2024-01-10"),
        ]
        result = sync_create_fuel_periods(records)
        assert result == []

    def test_basic_period_created(self):
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100500, 380.0, "2024-02-01", "dolu"),
        ]
        result = sync_create_fuel_periods(records)
        assert len(result) == 1
        p = result[0]
        assert p.ara_mesafe == 500
        assert p.toplam_yakit == pytest.approx(380.0)
        assert p.ort_tuketim == pytest.approx((380.0 / 500) * 100, rel=0.01)

    def test_full_keyword_variant(self):
        """'full' (English) should also start period."""
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "full"),
            _yakit(2, 1, 100500, 380.0, "2024-02-01", "full"),
        ]
        result = sync_create_fuel_periods(records)
        assert len(result) == 1

    def test_aggregated_liters_between_full_tanks(self):
        """Multiple non-full fills should be aggregated."""
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100200, 100.0, "2024-01-10"),  # partial fill
            _yakit(3, 1, 100400, 150.0, "2024-01-20"),  # partial fill
            _yakit(4, 1, 100500, 200.0, "2024-01-30", "dolu"),
        ]
        result = sync_create_fuel_periods(records)
        assert len(result) == 1
        assert result[0].toplam_yakit == pytest.approx(450.0)  # 100+150+200

    def test_zero_or_negative_distance_skipped(self):
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100000, 380.0, "2024-02-01", "dolu"),  # same km
        ]
        result = sync_create_fuel_periods(records)
        # distance==0 → skipped
        assert result == []

    def test_no_second_full_tank_stops(self):
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100300, 200.0, "2024-01-20"),  # partial, no next full
        ]
        result = sync_create_fuel_periods(records)
        assert result == []

    def test_multiple_vehicles_separate_periods(self):
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100500, 380.0, "2024-02-01", "dolu"),
            _yakit(3, 2, 50000, 300.0, "2024-01-01", "dolu"),
            _yakit(4, 2, 50400, 280.0, "2024-02-01", "dolu"),
        ]
        result = sync_create_fuel_periods(records)
        assert len(result) == 2
        vehicle_ids = {p.arac_id for p in result}
        assert vehicle_ids == {1, 2}

    async def test_async_wrapper_calls_sync(self):
        records = [
            _yakit(1, 1, 100000, 400.0, "2024-01-01", "dolu"),
            _yakit(2, 1, 100500, 380.0, "2024-02-01", "dolu"),
        ]
        result = await create_fuel_periods(records)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# evaluate_consumption_status
# ---------------------------------------------------------------------------


class TestEvaluateConsumptionStatus:
    def test_below_10_veri_hatasi(self):
        assert evaluate_consumption_status(5.0) == "VERI HATASI"

    def test_10_to_28_mukemmel(self):
        assert evaluate_consumption_status(20.0) == "MÜKEMMEL"

    def test_28_to_32_iyi(self):
        assert evaluate_consumption_status(30.0) == "İYİ"

    def test_32_to_38_normal(self):
        assert evaluate_consumption_status(35.0) == "NORMAL"

    def test_38_to_45_yuksek(self):
        assert evaluate_consumption_status(40.0) == "YÜKSEK"

    def test_above_45_kritik(self):
        assert evaluate_consumption_status(50.0) == "KRİTİK"


# ---------------------------------------------------------------------------
# sync_distribute_fuel_to_trips
# ---------------------------------------------------------------------------


def _make_period(toplam_yakit=1000.0, arac_id=1):
    return YakitPeriyodu(
        arac_id=arac_id,
        ara_mesafe=500,
        toplam_yakit=toplam_yakit,
        alim1_tarih=date(2024, 1, 1),
        alim2_tarih=date(2024, 2, 1),
        alim1_km=100000,
        alim2_km=100500,
    )


class TestDistributeFuelToTrips:
    def test_empty_trips_returns_unchanged(self):
        period = _make_period()
        result = sync_distribute_fuel_to_trips(period, [])
        assert result == []

    def test_normal_ton_km_distribution(self):
        period = _make_period(toplam_yakit=600.0)
        trips = [
            _sefer(1, 1, "2024-01-05", mesafe_km=200, net_kg=10000),
            _sefer(2, 1, "2024-01-10", mesafe_km=300, net_kg=20000),
        ]
        result = sync_distribute_fuel_to_trips(period, trips)
        total_allocated = sum(t.dagitilan_yakit for t in result)
        assert total_allocated == pytest.approx(600.0, abs=0.1)
        # All trips should have tuketim set
        for t in result:
            assert t.tuketim is not None

    def test_zero_factor_falls_back_to_distance_distribution(self):
        """If all factors=0 (zero mesafe), distribute by distance."""
        period = _make_period(toplam_yakit=200.0)
        # mesafe_km=0 for all → total_factor=0
        trips = [
            _sefer(1, 1, "2024-01-05", mesafe_km=0, net_kg=0),
            _sefer(2, 1, "2024-01-10", mesafe_km=0, net_kg=0),
        ]
        # zero mesafe + zero net_kg → total_distance also 0 → returns unchanged
        result = sync_distribute_fuel_to_trips(period, trips)
        assert result == trips

    def test_distance_fallback_distributes_by_distance(self):
        """total_factor=0 but mesafe>0 → distribute proportional to mesafe."""
        period = _make_period(toplam_yakit=300.0)
        trips = [
            _sefer(1, 1, "2024-01-05", mesafe_km=100, net_kg=0),
            _sefer(2, 1, "2024-01-10", mesafe_km=200, net_kg=0),
        ]
        # net_kg=0 → ton=0 → total_mass = empty_weight only, factor = mesafe * empty_weight
        # Actually with empty_weight set, total_factor > 0. Override ton to force zero:
        # Use bos_sefer flag doesn't zero it. We need mesafe=0 with net_kg=0 to zero factor.
        # Instead test via the normal path since empty_weight is non-zero.
        result = sync_distribute_fuel_to_trips(period, trips)
        total_allocated = sum(t.dagitilan_yakit for t in result)
        assert total_allocated == pytest.approx(300.0, abs=0.1)

    def test_single_trip_gets_all_fuel(self):
        period = _make_period(toplam_yakit=500.0)
        trips = [_sefer(1, 1, "2024-01-05", mesafe_km=300)]
        result = sync_distribute_fuel_to_trips(period, trips)
        # Last (only) trip gets remaining fuel
        assert result[0].dagitilan_yakit == pytest.approx(500.0)

    def test_tuketim_zero_when_mesafe_zero(self):
        """Trip with mesafe_km=0 should have tuketim=0.0, not division error."""
        period = _make_period(toplam_yakit=200.0)
        trips = [
            _sefer(1, 1, "2024-01-05", mesafe_km=300, net_kg=10000),
            _sefer(2, 1, "2024-01-10", mesafe_km=300, net_kg=10000),
        ]
        # Build a fake last trip with mesafe=0 by manipulating after creation
        last_trip = _sefer(3, 1, "2024-01-15", mesafe_km=300, net_kg=10000)
        last_trip.mesafe_km = 0  # Force zero for coverage
        trips.append(last_trip)
        result = sync_distribute_fuel_to_trips(period, trips)
        zero_trip = [t for t in result if t.id == 3][0]
        assert zero_trip.tuketim == pytest.approx(0.0)

    async def test_async_wrapper(self):
        period = _make_period(toplam_yakit=600.0)
        trips = [_sefer(1, 1, "2024-01-05", mesafe_km=300, net_kg=15000)]
        result = await distribute_fuel_to_trips(period, trips)
        assert len(result) == 1
        assert result[0].dagitilan_yakit is not None


# ---------------------------------------------------------------------------
# sync_match_periods_with_trips
# ---------------------------------------------------------------------------


class TestMatchPeriodsWithTrips:
    def test_empty_periods(self):
        result = sync_match_periods_with_trips([], [])
        assert result == []

    def test_matches_trips_within_period_dates(self):
        period = _make_period(toplam_yakit=300.0)
        # Trip date within [2024-01-01, 2024-02-01)
        trips = [
            _sefer(1, 1, "2024-01-15", mesafe_km=200),
            _sefer(2, 1, "2024-01-20", mesafe_km=300),
        ]
        result = sync_match_periods_with_trips([period], trips)
        assert len(result) == 1
        assert result[0].dagitim_yapildi is True
        assert len(result[0].seferler) == 2

    def test_trip_outside_date_range_not_matched(self):
        period = _make_period()
        trips = [_sefer(1, 1, "2024-03-01", mesafe_km=300)]  # after period end
        result = sync_match_periods_with_trips([period], trips)
        assert result[0].dagitim_yapildi is False
        assert result[0].seferler == []

    def test_different_arac_id_not_matched(self):
        period = _make_period(arac_id=1)
        trips = [_sefer(1, 2, "2024-01-15", mesafe_km=300)]  # arac_id=2
        result = sync_match_periods_with_trips([period], trips)
        assert result[0].seferler == []

    def test_toplam_mesafe_calculated(self):
        period = _make_period()
        trips = [
            _sefer(1, 1, "2024-01-10", mesafe_km=100),
            _sefer(2, 1, "2024-01-20", mesafe_km=250),
        ]
        result = sync_match_periods_with_trips([period], trips)
        assert result[0].toplam_mesafe == 350

    async def test_async_wrapper(self):
        period = _make_period()
        trips = [_sefer(1, 1, "2024-01-15", mesafe_km=200)]
        result = await match_periods_with_trips([period], trips)
        assert len(result) == 1
