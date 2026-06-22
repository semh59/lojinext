"""
LojiNext AI - Dashboard Service
Collects dashboard statistics and recent activity in parallel.
"""

import asyncio
import threading
from datetime import date
from typing import Any, Dict, Optional

from app.core.utils.clock import current_date
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DashboardService:
    """Dashboard summary and card data service."""

    def __init__(self, report_service=None, sefer_repo=None):
        if report_service is not None:
            self.report_service = report_service
        else:
            from app.core.services.report_service import get_report_service

            self.report_service = get_report_service()

        self.sefer_repo = sefer_repo  # None = use UoW in get_dashboard_data

    async def get_dashboard_data(self, recent_limit: int = 10) -> Dict[str, Any]:
        """
        Fetch dashboard cards/charts in parallel.
        """
        async with UnitOfWork() as uow:
            repo = self.sefer_repo if self.sefer_repo is not None else uow.sefer_repo
            analiz_repo = uow.analiz_repo

            tasks = (
                self.report_service.get_dashboard_summary(),
                self.report_service.get_monthly_comparison(),
                repo.get_all(limit=recent_limit, filters={"is_deleted": False}),
                repo.count(filters={"is_deleted": False}),
                _safe_await(
                    analiz_repo.get_monthly_consumption_series()
                    if hasattr(analiz_repo, "get_monthly_consumption_series")
                    else []
                ),
            )
            (
                stats,
                comparisons,
                recent_trips,
                total_trips,
                chart_data,
            ) = await asyncio.gather(*tasks)

        return {
            "stats": stats or {},
            "comparisons": comparisons or {},
            "recent_trips": recent_trips or [],
            "total_trips": int(total_trips or 0),
            "chart_data": chart_data or [],
        }

    async def get_dashboard_summary(self, today_utc: Optional[date] = None) -> Dict:
        """
        Compatibility method for older callers expecting condensed summary.
        """
        today_utc = today_utc or current_date()
        data = await self.get_dashboard_data()
        comparisons = data.get("comparisons", {}) or {}

        return {
            **(data.get("stats", {}) or {}),
            "trends": {
                "sefer": comparisons.get("sefer_degisim", 0),
                "km": comparisons.get("km_degisim", 0),
                "tuketim": comparisons.get("tuketim_degisim", 0),
            },
            "today": today_utc.isoformat(),
        }


async def _safe_await(value_or_coro):
    if asyncio.iscoroutine(value_or_coro):
        return await value_or_coro
    return value_or_coro


_dashboard_service = None
_dashboard_service_lock = threading.Lock()


def get_dashboard_service() -> DashboardService:
    """Thread-safe singleton provider."""
    global _dashboard_service
    if _dashboard_service is None:
        with _dashboard_service_lock:
            if _dashboard_service is None:
                _dashboard_service = DashboardService()
    return _dashboard_service
