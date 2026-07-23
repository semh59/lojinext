"""Use-cases: fetch a single fuel record or a vehicle's fuel history."""

from typing import List, Optional

from v2.modules.fuel.domain.entities import YakitAlimi
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_yakit_by_id(
    yakit_id: int, include_inactive: bool = False
) -> Optional[YakitAlimi]:
    """Retrieves fuel transaction details."""
    async with UnitOfWork() as uow:
        record = await uow.yakit_repo.get_by_id(
            yakit_id, include_inactive=include_inactive
        )
        if not record:
            return None
        return YakitAlimi.model_validate(dict(record))


async def get_by_vehicle(arac_id: int, limit: int = 50) -> List[YakitAlimi]:
    """Retrieves vehicle fuel history."""
    async with UnitOfWork() as uow:
        result = await uow.yakit_repo.get_all(arac_id=arac_id, limit=limit)
    rows = result.get("items", []) if isinstance(result, dict) else result
    return [YakitAlimi.model_validate(dict(r)) for r in rows]
