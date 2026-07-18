"""Public surface of the reports module.

Other modules that need to call into reports must import from here, not
from ``application/``, ``domain/``, or ``infrastructure/`` directly.

There is no ``ReportService`` class — each use-case is a standalone
function taking an explicit ``ReportRepos`` bundle (built via
``resolve_repos(uow)``, mirroring the ``uow: Optional[UnitOfWork] = None``
fallback shape used throughout v2, e.g.
``v2.modules.driver.application.driver_stats``). This avoids hiding shared
repo state behind a stateful facade for seven otherwise-unrelated
use-cases (fleet summary / vehicle report / driver report / monthly trend /
dashboard summary / monthly comparison / daily consumption trend).
"""

from v2.modules.reports.application.aggregate_today_triage import (
    TodayTriage,
    TriageAction,
    TriageItem,
    aggregate_today_triage,
)
from v2.modules.reports.application.compute_fleet_comparison import (
    FleetComparison,
    PeriodMetrics,
    PeriodType,
    compute_fleet_comparison,
)
from v2.modules.reports.application.generate_driver_report import generate_driver_report
from v2.modules.reports.application.generate_fleet_summary import generate_fleet_summary
from v2.modules.reports.application.generate_monthly_trend import generate_monthly_trend
from v2.modules.reports.application.generate_vehicle_report import (
    generate_vehicle_report,
)
from v2.modules.reports.application.get_dashboard_summary import get_dashboard_summary
from v2.modules.reports.application.get_monthly_comparison import get_monthly_comparison
from v2.modules.reports.infrastructure.pdf_export import (
    PDFReportGenerator,
    get_report_generator,
)
from v2.modules.reports.infrastructure.repo_access import ReportRepos, resolve_repos

__all__ = [
    "generate_fleet_summary",
    "generate_vehicle_report",
    "generate_driver_report",
    "generate_monthly_trend",
    "get_dashboard_summary",
    "get_monthly_comparison",
    "ReportRepos",
    "resolve_repos",
    "aggregate_today_triage",
    "TodayTriage",
    "TriageItem",
    "TriageAction",
    "compute_fleet_comparison",
    "FleetComparison",
    "PeriodMetrics",
    "PeriodType",
    "PDFReportGenerator",
    "get_report_generator",
]
