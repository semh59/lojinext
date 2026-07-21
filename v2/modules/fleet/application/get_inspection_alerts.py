"""Use-case: muayenesi yaklaşan/geçmiş araç ve dorseleri listele."""

from typing import Any, Dict, List

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_vehicle_inspection_alerts(
    within_days: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Muayenesi yaklaşan veya geçmiş araçların listesi ({expiring, overdue})."""
    async with UnitOfWork() as uow:
        return await uow.arac_repo.get_inspection_alerts(within_days)


async def get_trailer_inspection_alerts(
    repo: DorseRepository, within_days: int
) -> Dict[str, List[Dict[str, Any]]]:
    """Muayenesi yaklaşan veya geçmiş dorselerin listesi ({expiring, overdue})."""
    return await repo.get_inspection_alerts(within_days)
