"""Use-case: list/paginate vehicles."""

from typing import Any, Dict, List, Optional

from v2.modules.fleet.domain.entities import Arac as AracEntity
from v2.modules.fleet.domain.entities import VehicleStats
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def get_all_vehicles_paged(
    skip: int = 0,
    limit: int = 100,
    aktif_only: bool = True,
    search: Optional[str] = None,
    marka: Optional[str] = None,
    model: Optional[str] = None,
    min_yil: Optional[int] = None,
    max_yil: Optional[int] = None,
) -> Dict[str, Any]:
    """Returns a paged and filtered list of vehicles."""
    filters: Dict[str, Any] = {}
    if marka:
        filters["marka"] = marka
    if model:
        filters["model"] = model
    if min_yil is not None:
        filters["yil_ge"] = min_yil
    if max_yil is not None:
        filters["yil_le"] = max_yil

    async with UnitOfWork() as uow:
        rows = await uow.arac_repo.get_all(
            offset=skip,
            limit=limit,
            sadece_aktif=aktif_only,
            search=search,
            filters=filters,
        )
        total = await uow.arac_repo.count_all(
            sadece_aktif=aktif_only,
            search=search,
            filters=filters,
        )

    vehicles: List[AracEntity] = []
    for r in rows:
        try:
            vehicles.append(AracEntity.model_validate(dict(r)))
        except Exception as e:
            logger.warning(f"Skipping invalid vehicle record ID {r.get('id')}: {e}")
            continue
    return {"items": vehicles, "total": total}


async def get_all_vehicles(only_active: bool = True) -> List[AracEntity]:
    """Lists all vehicles (Legacy support)."""
    result = await get_all_vehicles_paged(aktif_only=only_active)
    return result["items"]


async def get_vehicle_stats(arac_id: int) -> Optional[VehicleStats]:
    """Returns vehicle details and statistics."""
    async with UnitOfWork() as uow:
        row = await uow.arac_repo.get_arac_with_stats(arac_id)
    if not row:
        return None
    return VehicleStats.model_validate(dict(row))


async def get_vehicle_by_id(
    arac_id: int, include_inactive: bool = False
) -> Optional[AracEntity]:
    """Retrieves a vehicle by ID.

    ``include_inactive=True``: pasif/soft-deleted araçları da döner.
    """
    async with UnitOfWork() as uow:
        row = await uow.arac_repo.get_by_id(arac_id, include_inactive=include_inactive)
    if not row:
        return None
    return AracEntity.model_validate(dict(row))


async def get_vehicle_raw_by_id(
    arac_id: int,
    include_inactive: bool = False,
    uow: Optional[UnitOfWork] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves a vehicle by ID as a raw dict (no ``AracEntity`` conversion).

    ``get_vehicle_by_id``'nin `AracEntity.model_validate` adımı `plaka` gibi
    alanlarda 0-mock canlı DB doğrulamasında GÖRÜLMEYEN bir farka yol açtığı
    CI'da bulundu (dalga-1-6+8 dedektif denetimi düzeltmesi sırasında,
    2026-07-15) — bu fonksiyon ham PK lookup semantiğini (eski
    `db.get(Arac, arac_id)` davranışı) birebir koruyan çağıranlar (tekil
    GET/PUT endpoint'leri: `read_arac`/`update_arac`) için kullanılır.
    ``include_inactive=True``: pasif/soft-deleted araçları da döner.

    ``uow`` verilirse (create-then-read-back akışı, `create_arac` route'u)
    ÇAĞIRANIN transaction'ı doğrudan kullanılır; verilmezse kendi
    ``UnitOfWork()``'ünü açar (varsayılan davranış, mevcut çağıranlar
    korunur).
    """
    if uow is not None:
        return await uow.arac_repo.get_by_id(arac_id, include_inactive=include_inactive)
    async with UnitOfWork() as new_uow:
        return await new_uow.arac_repo.get_by_id(
            arac_id, include_inactive=include_inactive
        )
