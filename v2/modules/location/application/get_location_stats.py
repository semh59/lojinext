"""Use-case: fleet-wide location statistics for KPI cards."""

from typing import Any, Dict

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_location_stats(repo: LokasyonRepository) -> Dict[str, Any]:
    return await repo.get_location_stats()
