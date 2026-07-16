"""Use-case: AI/legacy dashboard tüketicileri için özet alanlar."""

from __future__ import annotations

from typing import Dict

from v2.modules.reports.application.generate_fleet_summary import generate_fleet_summary
from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def get_dashboard_summary(repos: ReportRepos, days: int = 30) -> Dict:
    summary = await generate_fleet_summary(repos, days=days)
    return {
        "toplam_sefer": summary.get("total_trips", 0),
        "toplam_km": summary.get("total_distance", 0),
        "toplam_yakit": summary.get("total_fuel", 0),
        "filo_ortalama": summary.get("avg_consumption", 0),
        "toplam_harcama": summary.get("total_cost", 0),
        "toplam_arac": summary.get("total_vehicles", 0),
        "aktif_arac": summary.get("total_vehicles", 0),
    }
