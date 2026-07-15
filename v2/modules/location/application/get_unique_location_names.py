"""Use-case: unique location names for autocomplete."""

from typing import List

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_unique_location_names(repo: LokasyonRepository) -> List[str]:
    return await repo.get_benzersiz_lokasyonlar()
