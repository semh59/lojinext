"""Use-case: son N günün günlük tüketim serisi."""

from __future__ import annotations

from v2.modules.reports.infrastructure.repo_access import ReportRepos


async def get_daily_consumption_trend(repos: ReportRepos, days: int = 30):
    return await repos.analiz_repo.get_daily_consumption_series(days)
