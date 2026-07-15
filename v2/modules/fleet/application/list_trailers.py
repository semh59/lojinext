"""Use-case: list/paginate trailers."""

from typing import Any, Dict, List, Optional

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository


async def get_trailer_by_id(
    repo: DorseRepository, dorse_id: int, include_inactive: bool = False
) -> Optional[Dict[str, Any]]:
    """Get trailer by ID.

    ``include_inactive=True``: pasif/soft-deleted dorseleri de döner — ham
    PK lookup semantiğini koruyan çağıranlar (dalga-1-6+8 dedektif
    denetiminde ``application/`` katmanına taşınan ``read_dorse``/
    ``update_dorse``) bunu kullanır; varsayılan ``False`` ``get_all``/
    ``count`` ile tutarlıdır.
    """
    return await repo.get_by_id(dorse_id, include_inactive=include_inactive)


async def get_all_trailers(repo: DorseRepository, **kwargs) -> List[Dict[str, Any]]:
    """Get all trailers with optional filters."""
    return await repo.get_all(**kwargs)


async def get_all_trailers_paged(
    repo: DorseRepository,
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    aktif_only: bool = True,
    marka: Optional[str] = None,
    model: Optional[str] = None,
    min_yil: Optional[int] = None,
    max_yil: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Get trailers with pagination, search and filters.

    get_all_vehicles_paged ile aynı desen (2026-07-09 tasarım denetimi
    bulgusu): frontend'in "Detaylı Filtre" paneli (marka/model/min_yil/
    max_yil) + dorseService.getAll bu parametreleri zaten gönderiyordu,
    backend hiçbirini kabul etmiyordu — filtre sessizce hiçbir şey
    yapmıyordu. `yil_ge`/`yil_le`, BaseRepository.get_all'ın genel
    range-filter desteğidir (repo katmanında ek kod gerektirmez).
    """
    filters: Dict[str, Any] = {}
    if marka:
        filters["marka"] = marka
    if model:
        filters["model"] = model
    if min_yil is not None:
        filters["yil_ge"] = min_yil
    if max_yil is not None:
        filters["yil_le"] = max_yil

    return await repo.get_paged(
        skip=skip,
        limit=limit,
        search=search,
        aktif_only=aktif_only,
        filters=filters,
    )
