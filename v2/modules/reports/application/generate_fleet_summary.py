"""Use-case: filo genelinde özet rapor (dashboard + PDF/Excel export kaynağı)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

from v2.modules.reports.domain.report_metrics import (
    get_first_available,
    prefer_positive,
)
from v2.modules.reports.infrastructure.repo_access import ReportRepos
from v2.modules.shared_kernel.utils.clock import current_date


async def generate_fleet_summary(
    repos: ReportRepos,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = 30,
) -> Dict:
    if not start_date:
        start_date = current_date() - timedelta(days=days)

    try:
        stats = await repos.analiz_repo.get_fleet_performance_stats(start_date)
    except Exception:
        stats = {}

    yakit_stats: Dict = {}
    get_stats = getattr(repos.yakit_repo, "get_stats", None)
    if callable(get_stats):
        try:
            yakit_stats = await get_stats(
                baslangic_tarih=start_date,
                bitis_tarih=end_date,
            )
        except Exception:
            yakit_stats = {}

    total_vehicles = get_first_available(
        stats, "total_vehicles", "toplam_arac", default=0
    )
    if total_vehicles == 0:
        count_all = getattr(repos.arac_repo, "count_all", None)
        if callable(count_all):
            total_vehicles = await count_all()

    try:
        araclar = await repos.analiz_repo.get_top_performing_vehicles(limit=15)
    except Exception:
        araclar = []

    total_distance = get_first_available(
        stats, "total_distance", "toplam_km", default=0
    )
    total_fuel = get_first_available(stats, "total_fuel", "toplam_yakit", default=0)
    avg_consumption = get_first_available(
        stats, "avg_consumption", "filo_ortalama", "ortalama_tuketim", default=0
    )
    total_cost = get_first_available(stats, "total_cost", "toplam_harcama", default=0)

    total_distance = prefer_positive(
        total_distance, get_first_available(yakit_stats, "total_distance", default=0)
    )
    total_fuel = prefer_positive(
        total_fuel, get_first_available(yakit_stats, "total_consumption", default=0)
    )
    avg_consumption = prefer_positive(
        avg_consumption, get_first_available(yakit_stats, "avg_consumption", default=0)
    )
    total_cost = prefer_positive(
        total_cost, get_first_available(yakit_stats, "total_cost", default=0)
    )

    return {
        "donem": f"Son {days} gun" if not end_date else f"{start_date} - {end_date}",
        "genel": stats,
        "total_vehicles": total_vehicles,
        "total_trips": get_first_available(
            stats, "total_trips", "toplam_sefer", default=0
        ),
        "total_distance": total_distance,
        "total_fuel": total_fuel,
        "avg_consumption": avg_consumption,
        "total_cost": total_cost,
        "vehicle_performance": araclar,
    }
