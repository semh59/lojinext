"""
Unit tests for reports' generate_fleet_summary/generate_monthly_trend/
generate_vehicle_report use-cases (formerly ReportService methods, split
into free functions in dalga 10 — B.1).
"""

from unittest.mock import AsyncMock

import pytest

from v2.modules.fuel.infrastructure.repository import get_yakit_repo
from v2.modules.reports.application.generate_fleet_summary import generate_fleet_summary
from v2.modules.reports.application.generate_monthly_trend import generate_monthly_trend
from v2.modules.reports.application.generate_vehicle_report import (
    generate_vehicle_report,
)
from v2.modules.reports.infrastructure.repo_access import ReportRepos


class TestReportService:
    @pytest.fixture
    def mock_repos(self):
        mock_analiz = AsyncMock()
        mock_sofor = AsyncMock()
        mock_arac = AsyncMock()
        return mock_analiz, mock_sofor, mock_arac

    @pytest.fixture
    def service(self, mock_repos, monkeypatch):
        mock_analiz, mock_sofor, mock_arac = mock_repos

        return ReportRepos(
            analiz_repo=mock_analiz,
            arac_repo=mock_arac,
            sofor_repo=mock_sofor,
            yakit_repo=get_yakit_repo(),
        )

    @pytest.mark.asyncio
    async def test_generate_fleet_summary(self, service, mock_repos):
        mock_analiz, _, _ = mock_repos

        mock_analiz.get_fleet_performance_stats.return_value = {
            "total_vehicles": 15,
            "total_trips": 100,
            "total_distance": 5000,
            "total_fuel": 1600,
            "avg_consumption": 32.0,
            "total_cost": 50000,
        }
        mock_analiz.get_top_performing_vehicles.return_value = [
            {"plaka": "34ABC", "score": 95}
        ]

        summary = await generate_fleet_summary(service, days=30)

        mock_analiz.get_fleet_performance_stats.assert_called_once()
        mock_analiz.get_top_performing_vehicles.assert_called_once()

        assert summary["total_vehicles"] == 15
        assert summary["avg_consumption"] == 32.0
        assert len(summary["vehicle_performance"]) == 1

    @pytest.mark.asyncio
    async def test_generate_fleet_summary_supports_legacy_stats_keys(
        self, service, mock_repos
    ):
        mock_analiz, _, mock_arac = mock_repos
        mock_analiz.get_fleet_performance_stats.return_value = {
            "toplam_sefer": 12,
            "toplam_km": 3600,
            "toplam_yakit": 1110.0,
            "filo_ortalama": 30.8,
            "toplam_harcama": 44000.0,
        }
        mock_analiz.get_top_performing_vehicles.return_value = []
        mock_arac.count_all.return_value = 4

        summary = await generate_fleet_summary(service, days=30)

        assert summary["total_vehicles"] == 4
        assert summary["total_trips"] == 12
        assert summary["total_distance"] == 3600
        assert summary["total_fuel"] == 1110.0
        assert summary["avg_consumption"] == 30.8
        assert summary["total_cost"] == 44000.0

    @pytest.mark.asyncio
    async def test_generate_monthly_trend(self, service, mock_repos):
        mock_analiz, _, _ = mock_repos
        mock_analiz.get_period_stats.side_effect = [
            {
                "toplam_sefer": 50,
                "toplam_km": 2000,
                "toplam_yakit": 600,
                "ortalama_tuketim": 30.0,
            },
            {
                "toplam_sefer": 45,
                "toplam_km": 1800,
                "toplam_yakit": 576,
                "ortalama_tuketim": 32.0,
            },
        ]

        stats = await generate_monthly_trend(service, year=2023, month=5)

        assert mock_analiz.get_period_stats.call_count == 2
        assert stats["bu_ay"]["ortalama_tuketim"] == 30.0
        assert stats["gecen_ay"]["ortalama_tuketim"] == 32.0
        assert "ortalama_tuketim_degisim" in stats["degisimler"]

    @pytest.mark.asyncio
    async def test_generate_vehicle_report(self, service, mock_repos):
        mock_analiz, _, mock_arac = mock_repos

        mock_arac.get_by_id.return_value = {
            "id": 1,
            "plaka": "34TEST",
            "marka": "Ford",
            "hedef_tuketim": 30.0,
        }
        mock_analiz.get_vehicle_summary_stats.return_value = {"ortalama_tuketim": 31.0}
        mock_analiz.get_daily_consumption_series.return_value = [
            {"date": "2023", "avg": 31.0}
        ]
        mock_analiz.get_top_routes_by_vehicle.return_value = []

        report = await generate_vehicle_report(service, arac_id=1, days=7)

        # Raporlar tarihsel veri okur — pasifleştirilmiş araç için de üretilebilmeli
        # (generate_vehicle_report.py, taşımadan önce de include_inactive=True idi)
        mock_arac.get_by_id.assert_called_once_with(1, include_inactive=True)
        mock_analiz.get_vehicle_summary_stats.assert_called_once()
        mock_analiz.get_daily_consumption_series.assert_called_once_with(7)

        assert report["plaka"] == "34TEST"
        assert report["istatistikler"]["ortalama_tuketim"] == 31.0
        assert len(report["gunluk_trend"]) == 1
