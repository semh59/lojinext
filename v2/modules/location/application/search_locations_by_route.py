"""Use-case: search locations by start/destination names."""

from typing import List

from v2.modules.location.infrastructure.models import Lokasyon
from v2.modules.location.infrastructure.repository import LokasyonRepository


async def search_locations_by_route(
    repo: LokasyonRepository, cikis: str, varis: str
) -> List[Lokasyon]:
    return await repo.search_by_route_names(cikis, varis)
