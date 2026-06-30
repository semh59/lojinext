"""
Unit Tests — CostAnalyzer service

0-mock (Dilim 27): all patch(UnitOfWork) removed.
- Empty-result tests → real DB via db_session (clean slate from conftest)
- Specific-data / calculation tests → narrow patch.object(Repo, 'method')
  so UoW opens a real session but repo data-access is controlled
- Pure logic tests (no DB call) → no fixture
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

import app.database.repositories.analiz_repo as analiz_repo_mod
import app.database.repositories.arac_repo as arac_repo_mod
import app.database.repositories.sefer_repo as sefer_repo_mod
import app.database.repositories.yakit_repo as yakit_repo_mod
from app.core.services.cost_analyzer import (
    CostAnalyzer,
    CostBreakdown,
    get_cost_analyzer,
)

pytestmark = pytest.mark.unit


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
    async def test_with_data(self):
        """Narrow repo mock: verify calculation logic with controlled rows."""
        fuel = [
            {"toplam_tutar": 500.0, "litre": 100.0},
            {"toplam_tutar": 750.0, "litre": 150.0},
        ]
        trips = [{"mesafe_km": 1000}, {"mesafe_km": 500}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ),
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31)
            )

        assert result.fuel_cost == Decimal("1250.00")
        assert result.fuel_liters == 250.0
        assert result.trip_count == 2
        assert result.total_distance == 1500.0
        assert result.avg_price_per_liter == Decimal("5.00")
        assert result.cost_per_km == round(Decimal("1250.00") / Decimal("1500.0"), 2)

    async def test_empty_fuel_and_trips(self, db_session):
        """Empty DB → all zeros returned."""
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_period_cost(
            date(2020, 1, 1), date(2020, 1, 31)
        )

        assert result.fuel_cost == Decimal("0")
        assert result.trip_count == 0
        assert result.cost_per_km == Decimal("0")
        assert result.avg_price_per_liter == Decimal("0")

    async def test_with_arac_id_filter(self):
        """Service must pass arac_id to yakit_repo.get_by_date_range."""
        fuel = [{"toplam_tutar": 200.0, "litre": 40.0}]
        trips = [{"mesafe_km": 400}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ) as mock_fuel,
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31), arac_id=7
            )

        assert result.fuel_cost == Decimal("200.00")
        mock_fuel.assert_awaited_once_with("2025-01-01", "2025-01-31", 7)

    async def test_none_values_handled(self):
        """None toplam_tutar/litre/mesafe_km must not raise."""
        fuel = [{"toplam_tutar": None, "litre": None}]
        trips = [{"mesafe_km": None}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ),
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.calculate_period_cost(
                date(2025, 1, 1), date(2025, 1, 31)
            )

        assert result.fuel_cost == Decimal("0")


# ── get_monthly_trend ─────────────────────────────────────────────────────────


class TestGetMonthlyTrend:
    async def test_with_data(self):
        """Narrow repo mock for controlled bulk-stats rows."""
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

        analyzer = CostAnalyzer()
        with patch.object(
            analiz_repo_mod.AnalizRepository,
            "get_bulk_cost_stats",
            AsyncMock(return_value=bulk_stats),
        ):
            trends = await analyzer.get_monthly_trend(months=2)

        assert len(trends) == 2
        jan = trends[0]
        assert jan["month"] == 1
        assert jan["year"] == 2025
        assert jan["label"] == "01/2025"
        assert jan["cost_per_km"] > 0

        feb = trends[1]
        assert feb["cost_per_km"] == 0.0

    async def test_empty_stats(self, db_session):
        """Empty DB → get_bulk_cost_stats returns [] → trend is []."""
        analyzer = CostAnalyzer()
        result = await analyzer.get_monthly_trend()
        assert result == []


# ── get_vehicle_cost_comparison ───────────────────────────────────────────────


class TestGetVehicleCostComparison:
    async def test_no_vehicles(self, db_session):
        """Empty DB → no active vehicles → result is []."""
        analyzer = CostAnalyzer()
        result = await analyzer.get_vehicle_cost_comparison()
        assert result == []

    async def test_single_vehicle_with_data(self):
        """Narrow repo mocks for vehicle fetch and per-vehicle cost calc."""
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        fuel = [{"toplam_tutar": 300.0, "litre": 60.0}]
        trips = [{"mesafe_km": 600.0}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                arac_repo_mod.AracRepository,
                "get_all",
                AsyncMock(return_value=vehicles),
            ),
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ),
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.get_vehicle_cost_comparison(months=1)

        assert len(result) == 1
        assert result[0]["arac_id"] == 1
        assert result[0]["plaka"] == "34ABC123"

    async def test_vehicle_calculation_error_returns_unavailable(self):
        """When calculate_period_cost raises, vehicle entry shows unavailable."""
        vehicles = [{"id": 5, "plaka": "06XYZ789"}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                arac_repo_mod.AracRepository,
                "get_all",
                AsyncMock(return_value=vehicles),
            ),
            patch.object(
                analyzer,
                "calculate_period_cost",
                side_effect=Exception("DB down"),
            ),
        ):
            result = await analyzer.get_vehicle_cost_comparison(months=1)

        assert len(result) == 1
        assert result[0]["unavailable"] is True
        assert result[0]["error_code"] == "SERVICE_UNAVAILABLE"


# ── calculate_savings_potential ───────────────────────────────────────────────


class TestCalculateSavingsPotential:
    async def test_invalid_target(self):
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_savings_potential(target_consumption=0)
        assert "error" in result

    async def test_no_source_data(self, db_session):
        """Empty DB → no distance/fuel → error returned."""
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_savings_potential(target_consumption=30.0)
        assert "error" in result

    async def test_with_real_data(self):
        """Narrow repo mock for savings calculation with controlled source data."""
        fuel = [{"toplam_tutar": 1500.0, "litre": 300.0}]
        trips = [{"mesafe_km": 1000.0}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ),
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.calculate_savings_potential(target_consumption=25.0)

        assert "current_consumption" in result
        assert "potential_savings" in result
        assert "annual_projection" in result


# ── calculate_roi ─────────────────────────────────────────────────────────────


class TestCalculateROI:
    async def test_invalid_investment(self):
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_roi(investment=0)
        assert "error" in result

    async def test_no_source_data_propagates_error(self, db_session):
        """Empty DB → savings_potential has error → roi propagates it."""
        analyzer = CostAnalyzer()
        result = await analyzer.calculate_roi(investment=50000.0)
        assert "error" in result

    async def test_with_positive_savings(self):
        """Narrow repo mock for ROI with sufficient source data."""
        fuel = [{"toplam_tutar": 5000.0, "litre": 1000.0}]
        trips = [{"mesafe_km": 3000.0}]

        analyzer = CostAnalyzer()
        with (
            patch.object(
                yakit_repo_mod.YakitRepository,
                "get_by_date_range",
                AsyncMock(return_value=fuel),
            ),
            patch.object(
                sefer_repo_mod.SeferRepository,
                "get_by_date_range",
                AsyncMock(return_value=trips),
            ),
        ):
            result = await analyzer.calculate_roi(
                investment=10000.0, months=12, target_consumption=25.0
            )

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
