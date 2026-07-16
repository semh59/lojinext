"""Repo resolution shared by the report-generation use-cases.

Mirrors the ``uow: Optional[UnitOfWork] = None`` fallback shape used
throughout v2 (e.g. ``v2.modules.driver.domain.driver_stats._repos``): when a
``UnitOfWork`` is supplied its repos are reused (single shared session,
required inside an already-open transaction); otherwise each repo's
module-level singleton getter is used. ``analiz_repo`` is a cross-module,
temporary (documented) dependency — it belongs to the not-yet-migrated
analytics_executive module. Fields are typed ``Any`` because callers also
pass ``unittest.mock.AsyncMock`` stand-ins in tests, not just the real repo
classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.database.unit_of_work import UnitOfWork


@dataclass
class ReportRepos:
    analiz_repo: Any
    arac_repo: Any
    sofor_repo: Any
    yakit_repo: Any


def resolve_repos(uow: Optional[UnitOfWork] = None) -> ReportRepos:
    if uow is not None:
        return ReportRepos(
            analiz_repo=uow.analiz_repo,
            arac_repo=uow.arac_repo,
            sofor_repo=uow.sofor_repo,
            yakit_repo=uow.yakit_repo,
        )

    from app.database.repositories.analiz_repo import get_analiz_repo
    from v2.modules.driver.infrastructure.repository import get_sofor_repo
    from v2.modules.fleet.infrastructure.vehicle_repository import get_arac_repo
    from v2.modules.fuel.infrastructure.repository import get_yakit_repo

    return ReportRepos(
        analiz_repo=get_analiz_repo(),
        arac_repo=get_arac_repo(),
        sofor_repo=get_sofor_repo(),
        yakit_repo=get_yakit_repo(),
    )
