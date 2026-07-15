"""Use-case: fetch a single location by id."""

from typing import Any, Dict, Optional

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_location_by_id(
    repo: LokasyonRepository, lokasyon_id: int, include_inactive: bool = False
) -> Optional[Dict[str, Any]]:
    return await repo.get_by_id(lokasyon_id, include_inactive=include_inactive)
