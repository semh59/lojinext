"""Use-case: legacy dashboard tüketicileri için ay-ay değişim alanları."""

from __future__ import annotations

from typing import Dict, Optional

from v2.modules.reports.application.generate_monthly_trend import generate_monthly_trend
from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def get_monthly_comparison(
    repos: ReportRepos, year: Optional[int] = None, month: Optional[int] = None
) -> Dict:
    trend = await generate_monthly_trend(repos, year=year, month=month)
    changes = trend.get("degisimler", {})
    return {
        "sefer_degisim": changes.get("toplam_sefer_degisim", 0),
        "km_degisim": changes.get("toplam_km_degisim", 0),
        "tuketim_degisim": changes.get("ortalama_tuketim_degisim", 0),
        "yakit_degisim": changes.get("toplam_yakit_degisim", 0),
    }
