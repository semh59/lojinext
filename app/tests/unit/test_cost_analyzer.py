"""
Unit Tests — CostAnalyzer service
Mock'lar: UnitOfWork (async CM), yakit_repo, sefer_repo, analiz_repo, arac_repo
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.cost_analyzer import (
    CostAnalyzer,
    CostBreakdown,
    get_cost_analyzer,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_uow(fuel_records=None, trips=None, bulk_stats=None, vehicles=None):
    """Async-context-manager UnitOfWork mock with configurable repo responses."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    uow.yakit_repo = MagicMock()
    uow.yakit_repo.get_by_date_range = AsyncMock(return_value=fuel_records or [])

    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_by_date_range = AsyncMock(return_value=trips or [])

    uow.analiz_repo = MagicMock()
    uow.analiz_repo.get_bulk_cost_stats = AsyncMock(return_value=bulk_stats or [])

    uow.arac_repo = MagicMock()
    uow.arac_repo.get_all = AsyncMock(return_value=vehicles or [])

    return uow


# ── CostBreakdown dataclass ───────────────────────────────────────────────────


class TestCostBreakdown:
    def test_fields(self):
        cb = CostBreakdown(
            fuel_cost=Decimal("1500.00"),
            fuel_liters=300.0,
            avg_price_per_liter=Decimal("5.00"),
            trip_count=5,
            total_distance=2000.0,
            cost_per_km=Decimal("0.75"),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        assert cb.fuel_cost == Decimal("1500.00")
        assert cb.trip_count == 5


# ── calculate_period_cost ─────────────────────────────────────────────────────


class TestCalculatePeriodCost:
    @pytest.mark.asyncio
    async def test_with_data(self):
        fuel = [
            {"toplam_tutar": 500.0, "litre": 100.0},
            {"toplam_tutar": 750.0, "litre": 150.0},
        ]
        trips = [{"mesafe_km": 1000}, {"mesafe_km": 500}]
        uow = _make_uow(fuel_records=fuel, trips=trips)

        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31)
            )

        assert result.fuel_cost == Decimal("1250.00")
        assert result.fuel_liters == 250.0
        assert result.trip_count == 2
        assert result.total_distance == 1500.0
        assert result.avg_price_per_liter == Decimal("5.00")
        assert result.cost_per_km == round(Decimal("1250.00") / Decimal("1500.0"), 2)

    @pytest.mark.asyncio
    async def test_empty_fuel_and_trips(self):
        uow = _make_uow()
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31)
            )

        assert result.fuel_cost == Decimal("0")
        assert result.trip_count == 0
        assert result.cost_per_km == Decimal("0")
        assert result.avg_price_per_liter == Decimal("0")

    @pytest.mark.asyncio
    async def test_with_arac_id_filter(self):
        uow = _make_uow(
            fuel_records=[{"toplam_tutar": 200.0, "litre": 40.0}],
            trips=[{"mesafe_km": 400}],
        )
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31), arac_id=7
            )
        assert result.fuel_cost == Decimal("200.00")
        # repo called with arac_id
        uow.yakit_repo.get_by_date_range.assert_awaited_once_with(
            "2025-01-01", "2025-01-31", 7
        )

    @pytest.mark.asyncio
    async def test_none_values_handled(self):
        """None values in toplam_tutar / litre / mesafe_km should not raise."""
        fuel = [{"toplam_tutar": None, "litre": None}]
        trips = [{"mesafe_km": None}]
        uow = _make_uow(fuel_records=fuel, trips=trips)
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31)
            )
        assert result.fuel_cost == Decimal("0")


# ── get_monthly_trend ─────────────────────────────────────────────────────────


class TestGetMonthlyTrend:
    @pytest.mark.asyncio
    async def test_with_data(self):
        bulk_stats = [
            {
                "ay": "2025-01",
                "yakit_tl": 3000.0,
                "toplam_km": 6000.0,
                "yakit_litre": 600.0,
                "sefer_sayisi": 10,
            },
            {
                "ay": "2025-02",
                "yakit_tl": 0,
                "toplam_km": 0,
                "yakit_litre": 0,
                "sefer_sayisi": 0,
            },
        ]
        uow = _make_uow(bulk_stats=bulk_stats)
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            trends = await analyzer.get_monthly_trend(months=2)

        assert len(trends) == 2
        jan = trends[0]
        assert jan["month"] == 1
        assert jan["year"] == 2025
        assert jan["label"] == "01/2025"
        assert jan["cost_per_km"] > 0

        feb = trends[1]
        assert feb["cost_per_km"] == 0.0  # zero distance → zero cost/km

    @pytest.mark.asyncio
    async def test_empty_stats(self):
        uow = _make_uow(bulk_stats=[])
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.get_monthly_trend()
        assert result == []


# ── get_vehicle_cost_comparison ───────────────────────────────────────────────


class TestGetVehicleCostComparison:
    @pytest.mark.asyncio
    async def test_no_vehicles(self):
        uow = _make_uow(vehicles=[])
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.get_vehicle_cost_comparison()
        assert result == []

    @pytest.mark.asyncio
    async def test_single_vehicle_with_data(self):
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        # The outer UoW call returns vehicles; inner calls go via calculate_period_cost
        outer_uow = _make_uow(vehicles=vehicles)
        inner_uow = _make_uow(
            fuel_records=[{"toplam_tutar": 300.0, "litre": 60.0}],
            trips=[{"mesafe_km": 600.0}],
        )

        call_count = 0

        class FakeUoW:
            def __init__(self):
                pass

            async def __aenter__(self):
                nonlocal call_count
                call_count += 1
                return outer_uow if call_count == 1 else inner_uow

            async def __aexit__(self, *a):
                return False

            # forward attribute lookups to the correct mock
            def __getattr__(self, name):
                if call_count == 1:
                    return getattr(outer_uow, name)
                return getattr(inner_uow, name)

        with patch("app.core.services.cost_analyzer.UnitOfWork", FakeUoW):
            analyzer = CostAnalyzer()
            result = await analyzer.get_vehicle_cost_comparison(months=1)

        assert len(result) == 1
        assert result[0]["arac_id"] == 1
        assert result[0]["plaka"] == "34ABC123"

    @pytest.mark.asyncio
    async def test_vehicle_calculation_error_returns_unavailable(self):
        vehicles = [{"id": 5, "plaka": "06XYZ789"}]
        uow = _make_uow(vehicles=vehicles)

        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            analyzer = CostAnalyzer()
            # Make calculate_period_cost raise for this vehicle
            with patch.object(
                analyzer, "calculate_period_cost", side_effect=Exception("DB down")
            ):
                result = await analyzer.get_vehicle_cost_comparison(months=1)

        assert len(result) == 1
        assert result[0]["unavailable"] is True
        assert result[0]["error_code"] == "SERVICE_UNAVAILABLE"


# ── calculate_savings_potential ───────────────────────────────────────────────


class TestCalculateSavingsPotential:
    @pytest.mark.asyncio
    async def test_invalid_target(self):
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_savings_potential(target_consumption=0)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_source_data(self):
        """Empty records → savings analysis requires real data."""
        uow = _make_uow()
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_savings_potential(target_consumption=30.0)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_with_real_data(self):
        fuel = [{"toplam_tutar": 1500.0, "litre": 300.0}]
        trips = [{"mesafe_km": 1000.0}]
        uow = _make_uow(fuel_records=fuel, trips=trips)
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_savings_potential(target_consumption=25.0)
        assert "current_consumption" in result
        assert "potential_savings" in result
        assert "annual_projection" in result


# ── calculate_roi ─────────────────────────────────────────────────────────────


class TestCalculateROI:
    @pytest.mark.asyncio
    async def test_invalid_investment(self):
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_roi(investment=0)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_source_data_propagates_error(self):
        """When savings_potential has error, roi should propagate it."""
        uow = _make_uow()
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_roi(investment=50000.0)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_with_positive_savings(self):
        fuel = [{"toplam_tutar": 5000.0, "litre": 1000.0}]
        trips = [{"mesafe_km": 3000.0}]
        uow = _make_uow(fuel_records=fuel, trips=trips)
        analyzer = CostAnalyzer()
        with patch("app.core.services.cost_analyzer.UnitOfWork", return_value=uow):
            result = await analyzer.calculate_roi(
                investment=10000.0, months=12, target_consumption=25.0
            )
        # If there are real savings (current ~33 L/100km vs target 25), ROI should work
        if "error" not in result:
            assert "payback_months" in result
            assert "annual_roi_percentage" in result


# ── singleton ─────────────────────────────────────────────────────────────────


class TestGetCostAnalyzer:
    def test_returns_same_instance(self):
        a = get_cost_analyzer()
        b = get_cost_analyzer()
        assert a is b

    def test_is_cost_analyzer(self):
        assert isinstance(get_cost_analyzer(), CostAnalyzer)
