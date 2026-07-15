"""Use-case: locations not analyzed in the last N days (or never analyzed)."""

from typing import Any, Dict, List

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_stale_locations(
    repo: LokasyonRepository, days: int
) -> List[Dict[str, Any]]:
    return await repo.get_stale_locations(days)
