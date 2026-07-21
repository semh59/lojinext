"""Use-case: read a driver by id / paged & filtered listing."""

from typing import Any, Dict, Optional

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_all_paged(
    skip: int = 0,
    limit: int = 100,
    aktif_only: bool = True,
    search: Optional[str] = None,
    ehliyet_sinifi: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Returns paged and filtered driver list."""
    filters: Dict[str, Any] = {}
    if ehliyet_sinifi:
        filters["ehliyet_sinifi"] = ehliyet_sinifi
    if min_score is not None:
        filters["score_ge"] = min_score
    if max_score is not None:
        filters["score_le"] = max_score

    async with UnitOfWork() as uow:
        items = await uow.sofor_repo.get_all(
            offset=skip,
            limit=limit,
            sadece_aktif=aktif_only,
            search=search,
            filters=filters,
        )
        total = await uow.sofor_repo.count_all(
            sadece_aktif=aktif_only,
            search=search,
            filters=filters,
        )

    return {"items": items, "total": total}


async def get_by_id(
    sofor_id: int, include_inactive: bool = False
) -> Optional[Dict[str, Any]]:
    """Retrieves a driver by ID.

    ``include_inactive=True``: pasif/soft-deleted şoförleri de döner — ham
    PK lookup semantiğini koruyan çağıranlar (dalga-1-6+8 dedektif
    denetiminde ``application/`` katmanına taşınan `read_sofor`/
    performans-tekil-GET endpoint'leri/`delete_sofor`) bunu kullanır;
    varsayılan ``False`` diğer mevcut çağıranlarla (create/update sonrası
    refetch) tutarlıdır.
    """
    async with UnitOfWork() as uow:
        return await uow.sofor_repo.get_by_id(
            sofor_id, include_inactive=include_inactive
        )


async def get_driver_fleet_stats() -> Dict[str, int]:
    """Sürücü filosu özeti — toplam + aktif sayısı (tek sorgu)."""
    from sqlalchemy import text

    async with UnitOfWork() as uow:
        row = (
            (
                await uow.session.execute(
                    text(
                        "SELECT COUNT(*) AS total, "
                        "COUNT(*) FILTER (WHERE aktif = true) AS active "
                        "FROM soforler"
                    )
                )
            )
            .mappings()
            .one()
        )
    return {"total": row["total"], "active": row["active"]}
