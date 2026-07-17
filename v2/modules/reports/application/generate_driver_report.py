"""Use-case: tek şoför için dönemsel değerlendirme raporu."""

from __future__ import annotations

from typing import Dict

from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def generate_driver_report(
    repos: ReportRepos, sofor_id: int, days: int = 30
) -> Dict:
    from v2.modules.driver.public import evaluate_driver

    # Raporlar tarihsel veri okur — pasifleştirilmiş şoför için de üretilebilmeli
    sofor = await repos.sofor_repo.get_by_id(sofor_id, include_inactive=True)
    if not sofor:
        return {"error": "Sofor bulunamadi"}

    # evaluate_driver's uow-fallback shape only reads `.analiz_repo` — ReportRepos
    # already exposes that attribute, so it can be passed through directly.
    degerlendirme = await evaluate_driver(sofor_id, uow=repos)
    return {
        "sofor": sofor,
        "donem": f"Son {days} gun",
        "degerlendirme": degerlendirme.model_dump() if degerlendirme else None,
    }
