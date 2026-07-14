"""Coverage tests for app/core/services/report_service.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report_service(**repo_overrides):
    """Build a ReportService with all repos mocked."""
    from app.core.services.report_service import ReportService

    mock_arac = AsyncMock()
    mock_sofor = AsyncMock()
    mock_sefer = AsyncMock()
    mock_yakit = AsyncMock()
    mock_analiz = AsyncMock()

    svc = ReportService.__new__(ReportService)
    svc.arac_repo = repo_overrides.get("arac_repo", mock_arac)
    svc.sofor_repo = repo_overrides.get("sofor_repo", mock_sofor)
    svc.sefer_repo = repo_overrides.get("sefer_repo", mock_sefer)
    svc.yakit_repo = repo_overrides.get("yakit_repo", mock_yakit)
    svc._analiz_repo = repo_overrides.get("analiz_repo", mock_analiz)
    # NOT: `_degerlendirme_service` attribute'u kaldırıldı — ReportService
    # artık SoforDegerlendirmeService tutmuyor (dalga 5, B.1 free-function
    # refactor); `generate_driver_report` evaluate_driver'ı doğrudan çağırır.
    return svc


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class TestStaticHelpers:
    def test_calculate_performance_score_perfect(self):
        from app.core.services.report_service import ReportService

        score = ReportService._calculate_performance_score(30.0, 30.0)
        assert score == 100.0

    def test_calculate_performance_score_over_target(self):
        from app.core.services.report_service import ReportService

        # 40 actual vs 30 target → 33% over → 66.7 score
        score = ReportService._calculate_performance_score(40.0, 30.0)
        assert 60.0 < score < 70.0

    def test_calculate_performance_score_zero_actual(self):
        from app.core.services.report_service import ReportService

        score = ReportService._calculate_performance_score(0.0, 30.0)
        assert score == 0.0

    def test_calculate_performance_score_zero_target(self):
        from app.core.services.report_service import ReportService

        score = ReportService._calculate_performance_score(30.0, 0.0)
        assert score == 0.0

    def test_calculate_performance_score_under_target(self):
        from app.core.services.report_service import ReportService

        # Under target → should be capped at 100
        score = ReportService._calculate_performance_score(10.0, 30.0)
        assert score == 100.0

    def test_get_first_available_returns_first_match(self):
        from app.core.services.report_service import ReportService

        data = {"a": None, "b": 42, "c": 99}
        result = ReportService._get_first_available(data, "a", "b", "c", default=0)
        assert result == 42

    def test_get_first_available_returns_default(self):
        from app.core.services.report_service import ReportService

        data = {"a": None, "b": None}
        result = ReportService._get_first_available(data, "a", "b", default=7)
        assert result == 7

    def test_prefer_positive_returns_primary_when_positive(self):
        from app.core.services.report_service import ReportService

        result = ReportService._prefer_positive(50, 100)
        assert result == 50

    def test_prefer_positive_returns_fallback_when_zero(self):
        from app.core.services.report_service import ReportService

        result = ReportService._prefer_positive(0, 100)
        assert result == 100

    def test_prefer_positive_returns_fallback_on_none(self):
        from app.core.services.report_service import ReportService

        result = ReportService._prefer_positive(None, 99)
        assert result == 99


# ---------------------------------------------------------------------------
# get_dashboard_summary
# ---------------------------------------------------------------------------


class TestGetDashboardSummary:
    async def test_delegates_to_generate_fleet_summary(self):
        svc = _make_report_service()
        fleet_result = {
            "total_trips": 10,
            "total_distance": 5000,
            "total_fuel": 1500,
            "avg_consumption": 30.0,
            "total_cost": 45000,
            "total_vehicles": 8,
        }
        svc.generate_fleet_summary = AsyncMock(return_value=fleet_result)

        result = await svc.get_dashboard_summary(days=30)

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
        svc = _make_report_service()
        trend_result = {
            "degisimler": {
                "toplam_sefer_degisim": 5.0,
                "toplam_km_degisim": -2.0,
                "ortalama_tuketim_degisim": 1.5,
                "toplam_yakit_degisim": 3.0,
            }
        }
        svc.generate_monthly_trend = AsyncMock(return_value=trend_result)

        result = await svc.get_monthly_comparison()
        assert result["sefer_degisim"] == 5.0
        assert result["km_degisim"] == -2.0
        assert result["tuketim_degisim"] == 1.5
        assert result["yakit_degisim"] == 3.0


# ---------------------------------------------------------------------------
# get_daily_consumption_trend
# ---------------------------------------------------------------------------


class TestGetDailyConsumptionTrend:
    async def test_delegates_to_analiz_repo(self):
        svc = _make_report_service()
        svc._analiz_repo.get_daily_consumption_series = AsyncMock(
            return_value=[{"day": 1}]
        )

        result = await svc.get_daily_consumption_trend(days=7)
        assert result == [{"day": 1}]


# ---------------------------------------------------------------------------
# generate_monthly_trend
# ---------------------------------------------------------------------------


class TestGenerateMonthlyTrend:
    async def test_computes_degisimler_with_previous_month(self):
        svc = _make_report_service()
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
        svc._analiz_repo.get_period_stats = AsyncMock(side_effect=[bu_ay, gecen_ay])

        result = await svc.generate_monthly_trend(year=2024, month=6)

        assert result["donem"] == "2024-06"
        assert result["bu_ay"] == bu_ay
        assert result["gecen_ay"] == gecen_ay
        sefer_change = result["degisimler"]["toplam_sefer_degisim"]
        assert sefer_change == pytest.approx(25.0)  # (100-80)/80*100

    async def test_december_wraps_to_january(self):
        svc = _make_report_service()
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
        svc._analiz_repo.get_period_stats = AsyncMock(side_effect=[bu_ay, gecen_ay])

        result = await svc.generate_monthly_trend(year=2024, month=12)
        # Previous month = November (gecen_ay has 0 values → degisim = 0)
        assert result["degisimler"]["toplam_sefer_degisim"] == 0


# ---------------------------------------------------------------------------
# generate_vehicle_report
# ---------------------------------------------------------------------------


class TestGenerateVehicleReport:
    async def test_returns_error_when_vehicle_not_found(self):
        svc = _make_report_service()
        svc.arac_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.generate_vehicle_report(arac_id=999)
        assert result == {"error": "Arac bulunamadi"}

    async def test_returns_vehicle_report_with_month_year(self):
        svc = _make_report_service()
        arac = {
            "plaka": "34ABC",
            "marka": "Mercedes",
            "model": "Actros",
            "hedef_tuketim": 32.0,
        }
        svc.arac_repo.get_by_id = AsyncMock(return_value=arac)
        svc._analiz_repo.get_vehicle_summary_stats = AsyncMock(
            return_value={"ort_tuketim": 30.0}
        )
        svc._analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
        svc._analiz_repo.get_top_routes_by_vehicle = AsyncMock(return_value=[])

        result = await svc.generate_vehicle_report(arac_id=1, month=3, year=2024)
        assert result["plaka"] == "34ABC"
        assert result["donem"] == "3/2024"
        assert "performance_score" in result

    async def test_returns_vehicle_report_without_month_year(self):
        svc = _make_report_service()
        arac = {
            "plaka": "06XYZ",
            "marka": "Volvo",
            "model": "FH",
            "hedef_tuketim": 35.0,
        }
        svc.arac_repo.get_by_id = AsyncMock(return_value=arac)
        svc._analiz_repo.get_vehicle_summary_stats = AsyncMock(
            return_value={"ort_tuketim": None}
        )
        svc._analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
        svc._analiz_repo.get_top_routes_by_vehicle = AsyncMock(return_value=[])

        result = await svc.generate_vehicle_report(arac_id=2, days=30)
        assert "Son 30 gun" in result["donem"]


# ---------------------------------------------------------------------------
# generate_driver_report
# ---------------------------------------------------------------------------


class TestGenerateDriverReport:
    async def test_returns_error_when_driver_not_found(self):
        svc = _make_report_service()
        svc.sofor_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.generate_driver_report(sofor_id=999)
        assert result == {"error": "Sofor bulunamadi"}

    async def test_returns_driver_report(self):
        # NOT: eski `svc._degerlendirme_service` (SoforDegerlendirmeService)
        # kaldırıldı (dalga 5, B.1 free-function refactor) — generate_driver_report
        # artık v2.modules.driver.domain.evaluation.evaluate_driver'ı fonksiyon
        # gövdesi içinde yerel import ediyor, patch hedefi KAYNAK modül.
        svc = _make_report_service()
        sofor = {"id": 1, "ad_soyad": "Ahmet Yılmaz"}
        svc.sofor_repo.get_by_id = AsyncMock(return_value=sofor)

        mock_eval = MagicMock()
        mock_eval.model_dump.return_value = {"score": 80}

        with patch(
            "v2.modules.driver.domain.evaluation.evaluate_driver",
            AsyncMock(return_value=mock_eval),
        ):
            result = await svc.generate_driver_report(sofor_id=1)

        assert result["sofor"] == sofor
        assert result["degerlendirme"] == {"score": 80}


# ---------------------------------------------------------------------------
# generate_fleet_summary
# ---------------------------------------------------------------------------


class TestGenerateFleetSummary:
    async def test_uses_yakit_repo_fallback_when_stats_zero(self):
        svc = _make_report_service()
        # stats returns zeros
        svc._analiz_repo.get_fleet_performance_stats = AsyncMock(
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
        svc.yakit_repo.get_stats = AsyncMock(
            return_value={
                "total_distance": 10000,
                "total_consumption": 3000,
                "avg_consumption": 30.0,
                "total_cost": 90000,
            }
        )
        svc._analiz_repo.get_top_performing_vehicles = AsyncMock(return_value=[])
        svc.arac_repo.count_all = AsyncMock(return_value=5)

        result = await svc.generate_fleet_summary(days=30)
        assert result["total_vehicles"] == 5
        assert result["total_distance"] == 10000

    async def test_runtime_error_in_yakit_repo_is_swallowed(self):
        svc = _make_report_service()
        svc._analiz_repo.get_fleet_performance_stats = AsyncMock(
            return_value={
                "total_vehicles": 3,
                "total_trips": 10,
            }
        )
        mock_get_stats = AsyncMock(side_effect=RuntimeError("Session gone"))
        svc.yakit_repo.get_stats = mock_get_stats
        svc._analiz_repo.get_top_performing_vehicles = AsyncMock(return_value=[])

        result = await svc.generate_fleet_summary(days=7)
        # Should not raise; total_vehicles from stats
        assert result["total_vehicles"] == 3
