"""Use-case: dashboard kart sayaçları (aktif araç/şoför, bugünkü sefer, aylık trend).

``ReportRepos`` bilerek ``sefer_repo`` taşımaz (``ReportService``'in eski
metotlarının hiçbiri kullanmıyordu, bkz. ``infrastructure/repo_access.py``
docstring'i) — bu use-case'in ``uow.sefer_repo.count_today``'e ihtiyacı
olduğu için doğrudan ``uow`` alır, ``aggregate_today_triage``/
``compute_fleet_comparison`` ile aynı desen.
"""

from __future__ import annotations

from datetime import date
from typing import Dict

from app.database.unit_of_work import UnitOfWork


async def get_dashboard_counters(uow: UnitOfWork, today_utc: date) -> Dict:
    aktif_arac = await uow.arac_repo.count_active()
    aktif_sofor = await uow.sofor_repo.count_active()
    bugun_sefer = await uow.sefer_repo.count_today(today_utc)
    trends = await uow.analiz_repo.get_month_over_month_trends(today_utc)
    return {
        "aktif_arac": aktif_arac,
        "aktif_sofor": aktif_sofor,
        "bugun_sefer": bugun_sefer,
        "trends": trends,
    }
