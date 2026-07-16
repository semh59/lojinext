"""Use-case: bu ay vs geçen ay trend karşılaştırması."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

from app.core.utils.clock import current_date
from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def generate_monthly_trend(
    repos: ReportRepos, year: Optional[int] = None, month: Optional[int] = None
) -> Dict:
    today = current_date()
    year = year or today.year
    month = month or today.month

    bu_ay_bas = date(year, month, 1)
    if month == 12:
        bu_ay_son = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        bu_ay_son = date(year, month + 1, 1) - timedelta(days=1)

    gecen_ay_son = bu_ay_bas - timedelta(days=1)
    gecen_ay_bas = gecen_ay_son.replace(day=1)

    bu_ay_data = await repos.analiz_repo.get_period_stats(bu_ay_bas, bu_ay_son)
    gecen_ay_data = await repos.analiz_repo.get_period_stats(gecen_ay_bas, gecen_ay_son)

    degisimler = {}
    for key in ["toplam_sefer", "toplam_km", "toplam_yakit", "ortalama_tuketim"]:
        bu = bu_ay_data.get(key, 0) or 0
        gecen = gecen_ay_data.get(key, 0) or 0
        if gecen > 0:
            degisimler[f"{key}_degisim"] = round((bu - gecen) / gecen * 100, 1)
        else:
            degisimler[f"{key}_degisim"] = 0

    return {
        "donem": f"{year}-{month:02d}",
        "bu_ay": bu_ay_data,
        "gecen_ay": gecen_ay_data,
        "degisimler": degisimler,
    }
