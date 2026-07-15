"""Use-case: fetch all locations unpaginated (Excel export)."""

from typing import Any, Dict, List

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_all_locations(repo: LokasyonRepository) -> List[Dict[str, Any]]:
    return await repo.get_all()
