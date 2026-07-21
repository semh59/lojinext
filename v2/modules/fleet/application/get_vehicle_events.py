"""Use-case: bir aracın olay geçmişini (vehicle_event_log) getir."""

from typing import Any, Dict, List

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_vehicle_events(arac_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Araç olay geçmişini getir (son N kayıt)."""
    async with UnitOfWork() as uow:
        return await uow.arac_repo.get_vehicle_events(arac_id, limit)
