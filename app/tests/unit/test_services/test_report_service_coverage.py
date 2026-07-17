"""Coverage tests for v2/modules/reports/application/*.py + domain/report_metrics.py.

dalga 10 — ``ReportService`` sınıfı kaldırıldı (B.1, free-function refactor);
her use-case artık bağımsız bir fonksiyon, ortak durum ``ReportRepos`` bundle'ı
(mocklanmış repo'lardan oluşturulur, gerçek DB/session yok).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.reports.domain.report_metrics import (
    calculate_performance_score,
    get_first_available,
    prefer_positive,
)
from v2.modules.reports.infrastructure.repo_access import ReportRepos

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repos(**repo_overrides) -> ReportRepos:
    """Build a ReportRepos bundle with all repos mocked."""
    return ReportRepos(
        analiz_repo=repo_overrides.get("analiz_repo", AsyncMock()),
        arac_repo=repo_overrides.get("arac_repo", AsyncMock()),
        sofor_repo=repo_overrides.get("sofor_repo", AsyncMock()),
        yakit_repo=repo_overrides.get("yakit_repo", AsyncMock()),
    )


# ---------------------------------------------------------------------------
# Static helpers (domain/report_metrics.py)
# ---------------------------------------------------------------------------


class TestStaticHelpers:
    def test_calculate_performance_score_perfect(self):
        score = calculate_performance_score(30.0, 30.0)
        assert score == 100.0

    def test_calculate_performance_score_over_target(self):
        # 40 actual vs 30 target → 33% over → 66.7 score
        score = calculate_performance_score(40.0, 30.0)
        assert 60.0 < score < 70.0

    def test_calculate_performance_score_zero_actual(self):
        score = calculate_performance_score(0.0, 30.0)
        assert score == 0.0

    def test_calculate_performance_score_zero_target(self):
        score = calculate_performance_score(30.0, 0.0)
        assert score == 0.0

    def test_calculate_performance_score_under_target(self):
        # Under target → should be capped at 100
        score = calculate_performance_score(10.0, 30.0)
        assert score == 100.0

    def test_get_first_available_returns_first_match(self):
        data = {"a": None, "b": 42, "c": 99}
        result = get_first_available(data, "a", "b", "c", default=0)
        assert result == 42

    def test_get_first_available_returns_default(self):
        data = {"a": None, "b": None}
        result = get_first_available(data, "a", "b", default=7)
        assert result == 7

    def test_prefer_positive_returns_primary_when_positive(self):
        result = prefer_positive(50, 100)
        assert result == 50

    def test_prefer_positive_returns_fallback_when_zero(self):
        result = prefer_positive(0, 100)
        assert result == 100

    def test_prefer_positive_returns_fallback_on_none(self):
        result = prefer_positive(None, 99)
        assert result == 99


# ---------------------------------------------------------------------------
# get_dashboard_summary
# ---------------------------------------------------------------------------


class TestGetDashboardSummary:
    async def test_delegates_to_generate_fleet_summary(self):
        from v2.modules.reports.application.get_dashboard_summary import (
            get_dashboard_summary,
        )

        repos = _make_repos()
        fleet_result = {
            "total_trips": 10,
            "total_distance": 5000,
            "total_fuel": 1500,
            "avg_consumption": 30.0,
            "total_cost": 45000,
            "total_vehicles": 8,
        }

        with patch(
            "v2.modules.reports.application.get_dashboard_summary.generate_fleet_summary",
            AsyncMock(return_value=fleet_result),
        ):
            result = await get_dashboard_summary(repos, days=30)

        assert result["toplam_sefer"] == 10
        assert result["toplam_km"] == 5000
        assert result["toplam_yakit"] == 1500
        assert result["filo_ortalama"] == 30.0
        assert result["toplam_harcama"] == 45000
        assert result["toplam_arac"] == 8
        assert result["aktif_arac"] == 8


# ---------------------------------------------------------------------------
# get_monthly_comparison
# ---------------------------------------------------------------------------


class TestGetMonthlyComparison:
    async def test_returns_change_dict(self):
        from v2.modules.reports.application.get_monthly_comparison import (
            get_monthly_comparison,
        )

        repos = _make_repos()
        trend_result = {
            "degisimler": {
                "toplam_sefer_degisim": 5.0,
                "toplam_km_degisim": -2.0,
                "ortalama_tuketim_degisim": 1.5,
                "toplam_yakit_degisim": 3.0,
            }
        }

        with patch(
            "v2.modules.reports.application.get_monthly_comparison.generate_monthly_trend",
            AsyncMock(return_value=trend_result),
        ):
            result = await get_monthly_comparison(repos)

        assert result["sefer_degisim"] == 5.0
        assert result["km_degisim"] == -2.0
        assert result["tuketim_degisim"] == 1.5
        assert result["yakit_degisim"] == 3.0


# ---------------------------------------------------------------------------
# get_daily_consumption_trend
# ---------------------------------------------------------------------------


class TestGetDailyConsumptionTrend:
    async def test_delegates_to_analiz_repo(self):
        from v2.modules.reports.application.get_daily_consumption_trend import (
            get_daily_consumption_trend,
        )

        repos = _make_repos()
        repos.analiz_repo.get_daily_consumption_series = AsyncMock(
            return_value=[{"day": 1}]
        )

        result = await get_daily_consumption_trend(repos, days=7)
        assert result == [{"day": 1}]


# ---------------------------------------------------------------------------
# generate_monthly_trend
# ---------------------------------------------------------------------------


class TestGenerateMonthlyTrend:
    async def test_computes_degisimler_with_previous_month(self):
        from v2.modules.reports.application.generate_monthly_trend import (
            generate_monthly_trend,
        )

        repos = _make_repos()
        bu_ay = {
            "toplam_sefer": 100,
            "toplam_km": 5000,
            "toplam_yakit": 1500,
            "ortalama_tuketim": 30.0,
        }
        gecen_ay = {
            "toplam_sefer": 80,
            "toplam_km": 4000,
            "toplam_yakit": 1200,
            "ortalama_tuketim": 30.0,
        }
        repos.analiz_repo.get_period_stats = AsyncMock(side_effect=[bu_ay, gecen_ay])

        result = await generate_monthly_trend(repos, year=2024, month=6)

        assert result["donem"] == "2024-06"
        assert result["bu_ay"] == bu_ay
        assert result["gecen_ay"] == gecen_ay
        sefer_change = result["degisimler"]["toplam_sefer_degisim"]
        assert sefer_change == pytest.approx(25.0)  # (100-80)/80*100

    async def test_december_wraps_to_january(self):
        from v2.modules.reports.application.generate_monthly_trend import (
            generate_monthly_trend,
        )

        repos = _make_repos()
        bu_ay = {
            "toplam_sefer": 50,
            "toplam_km": 2000,
            "toplam_yakit": 600,
            "ortalama_tuketim": 30.0,
        }
        gecen_ay = {
            "toplam_sefer": 0,
            "toplam_km": 0,
            "toplam_yakit": 0,
            "ortalama_tuketim": 0,
        }
        repos.analiz_repo.get_period_stats = AsyncMock(side_effect=[bu_ay, gecen_ay])

        result = await generate_monthly_trend(repos, year=2024, month=12)
        # Previous month = November (gecen_ay has 0 values → degisim = 0)
        assert result["degisimler"]["toplam_sefer_degisim"] == 0


# ---------------------------------------------------------------------------
# generate_vehicle_report
# ---------------------------------------------------------------------------


class TestGenerateVehicleReport:
    async def test_returns_error_when_vehicle_not_found(self):
        from v2.modules.reports.application.generate_vehicle_report import (
            generate_vehicle_report,
        )

        repos = _make_repos()
        repos.arac_repo.get_by_id = AsyncMock(return_value=None)

        result = await generate_vehicle_report(repos, arac_id=999)
        assert result == {"error": "Arac bulunamadi"}

    async def test_returns_vehicle_report_with_month_year(self):
        from v2.modules.reports.application.generate_vehicle_report import (
            generate_vehicle_report,
        )

        repos = _make_repos()
        arac = {
            "plaka": "34ABC",
            "marka": "Mercedes",
            "model": "Actros",
            "hedef_tuketim": 32.0,
        }
        repos.arac_repo.get_by_id = AsyncMock(return_value=arac)
        repos.analiz_repo.get_vehicle_summary_stats = AsyncMock(
            return_value={"ort_tuketim": 30.0}
        )
        repos.analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
        repos.analiz_repo.get_top_routes_by_vehicle = AsyncMock(return_value=[])

        result = await generate_vehicle_report(repos, arac_id=1, month=3, year=2024)
        assert result["plaka"] == "34ABC"
        assert result["donem"] == "3/2024"
        assert "performance_score" in result

    async def test_returns_vehicle_report_without_month_year(self):
        from v2.modules.reports.application.generate_vehicle_report import (
            generate_vehicle_report,
        )

        repos = _make_repos()
        arac = {
            "plaka": "06XYZ",
            "marka": "Volvo",
            "model": "FH",
            "hedef_tuketim": 35.0,
        }
        repos.arac_repo.get_by_id = AsyncMock(return_value=arac)
        repos.analiz_repo.get_vehicle_summary_stats = AsyncMock(
            return_value={"ort_tuketim": None}
        )
        repos.analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
        repos.analiz_repo.get_top_routes_by_vehicle = AsyncMock(return_value=[])

        result = await generate_vehicle_report(repos, arac_id=2, days=30)
        assert "Son 30 gun" in result["donem"]


# ---------------------------------------------------------------------------
# generate_driver_report
# ---------------------------------------------------------------------------


class TestGenerateDriverReport:
    async def test_returns_error_when_driver_not_found(self):
        from v2.modules.reports.application.generate_driver_report import (
            generate_driver_report,
        )

        repos = _make_repos()
        repos.sofor_repo.get_by_id = AsyncMock(return_value=None)

        result = await generate_driver_report(repos, sofor_id=999)
        assert result == {"error": "Sofor bulunamadi"}

    async def test_returns_driver_report(self):
        # evaluate_driver'ı generate_driver_report fonksiyon gövdesi içinde
        # yerel import ediyor (location'ın CLAUDE.md'sindeki aynı gotcha),
        # patch hedefi KAYNAK modül.
        from v2.modules.reports.application.generate_driver_report import (
            generate_driver_report,
        )

        repos = _make_repos()
        sofor = {"id": 1, "ad_soyad": "Ahmet Yılmaz"}
        repos.sofor_repo.get_by_id = AsyncMock(return_value=sofor)

        mock_eval = MagicMock()
        mock_eval.model_dump.return_value = {"score": 80}

        with patch(
            "v2.modules.driver.public.evaluate_driver",
            AsyncMock(return_value=mock_eval),
        ):
            result = await generate_driver_report(repos, sofor_id=1)

        assert result["sofor"] == sofor
        assert result["degerlendirme"] == {"score": 80}


# ---------------------------------------------------------------------------
# generate_fleet_summary
# ---------------------------------------------------------------------------


class TestGenerateFleetSummary:
    async def test_uses_yakit_repo_fallback_when_stats_zero(self):
        from v2.modules.reports.application.generate_fleet_summary import (
            generate_fleet_summary,
        )

        repos = _make_repos()
        # stats returns zeros
        repos.analiz_repo.get_fleet_performance_stats = AsyncMock(
            return_value={
                "total_vehicles": 0,
                "total_trips": 0,
                "total_distance": 0,
                "total_fuel": 0,
                "avg_consumption": 0,
                "total_cost": 0,
            }
        )
        # yakit_repo provides data
        repos.yakit_repo.get_stats = AsyncMock(
            return_value={
                "total_distance": 10000,
                "total_consumption": 3000,
                "avg_consumption": 30.0,
                "total_cost": 90000,
            }
        )
        repos.analiz_repo.get_top_performing_vehicles = AsyncMock(return_value=[])
        repos.arac_repo.count_all = AsyncMock(return_value=5)

        result = await generate_fleet_summary(repos, days=30)
        assert result["total_vehicles"] == 5
        assert result["total_distance"] == 10000

    async def test_runtime_error_in_yakit_repo_is_swallowed(self):
        from v2.modules.reports.application.generate_fleet_summary import (
            generate_fleet_summary,
        )

        repos = _make_repos()
        repos.analiz_repo.get_fleet_performance_stats = AsyncMock(
            return_value={
                "total_vehicles": 3,
                "total_trips": 10,
            }
        )
        mock_get_stats = AsyncMock(side_effect=RuntimeError("Session gone"))
        repos.yakit_repo.get_stats = mock_get_stats
        repos.analiz_repo.get_top_performing_vehicles = AsyncMock(return_value=[])

        result = await generate_fleet_summary(repos, days=7)
        # Should not raise; total_vehicles from stats
        assert result["total_vehicles"] == 3
