"""Use-case: filo-geneli özet istatistikler (araç/dorse sayıları, muayene uyarısı)."""

from typing import Any, Dict

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_vehicle_fleet_stats() -> Dict[str, Any]:
    """Araç filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
    async with UnitOfWork() as uow:
        return await uow.arac_repo.get_fleet_stats()


async def get_trailer_fleet_stats(repo: DorseRepository) -> Dict[str, Any]:
    """Dorse filosu genel istatistikleri (toplam, aktif, muayene uyarısı)."""
    return await repo.get_fleet_stats()
