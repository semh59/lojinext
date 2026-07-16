"""Use-case: tek araç için dönemsel detay rapor."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

from app.core.utils.clock import current_date
from v2.modules.reports.domain.report_metrics import calculate_performance_score
from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def generate_vehicle_report(
    repos: ReportRepos,
    arac_id: int,
    month: Optional[int] = None,
    year: Optional[int] = None,
    days: int = 30,
) -> Dict:
    # Raporlar tarihsel veri okur — pasifleştirilmiş araç için de üretilebilmeli
    arac = await repos.arac_repo.get_by_id(arac_id, include_inactive=True)
    if not arac:
        return {"error": "Arac bulunamadi"}

    if month and year:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    else:
        end_date = current_date()
        start_date = end_date - timedelta(days=days)

    stats = await repos.analiz_repo.get_vehicle_summary_stats(arac_id, start_date)
    gunluk = await repos.analiz_repo.get_daily_consumption_series(days)
    guzergahlar = await repos.analiz_repo.get_top_routes_by_vehicle(
        arac_id, start_date, limit=5
    )

    hedef_tuketim = arac.get(
        "hedef_tuketim", getattr(repos.analiz_repo, "DEFAULT_FILO_ORTALAMA", 32.0)
    )
    return {
        "plaka": arac["plaka"],
        "marka": arac["marka"],
        "model": arac.get("model", ""),
        "hedef_tuketim": hedef_tuketim,
        "performance_score": calculate_performance_score(
            stats.get("ort_tuketim"),
            hedef_tuketim,
        ),
        "arac": arac,
        "donem": f"{month}/{year}" if month else f"Son {days} gun",
        "istatistikler": stats,
        "gunluk_trend": gunluk,
        "top_guzergahlar": guzergahlar,
    }
