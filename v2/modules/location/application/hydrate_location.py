"""Use-case: hydrate a location's route with Mapbox+Open-Meteo segments (Phase 3.2).

Commit kararı çağıranındır (route'un kendi ``db``/``UOWDep`` session'ı) —
``LokasyonHydrator.hydrate()``'in kendi docstring'indeki invaryant: aynı
session içinde mutate edip caller'ın commit etmesini bekler.
"""

from typing import Any, Dict

from v2.modules.location.application.hydration import LokasyonHydrator
from v2.modules.location.infrastructure.repository import LokasyonRepository


async def hydrate_location(
    repo: LokasyonRepository, hydrator: LokasyonHydrator, lokasyon_id: int
) -> Dict[str, Any]:
    """Lokasyona ait ham güzergah verisini hesapla + (in-memory) doldur.

    Raises:
        ValueError("not_found"): lokasyon yok.
        ValueError("missing_coords"): cikis/varis lat-lon eksik.
        ValueError("provider_unavailable"): Mapbox/Open-Meteo başarısız.
    """
    sim = await repo.get_with_segments(lokasyon_id)
    if sim is None:
        raise ValueError("not_found")

    if (
        sim.cikis_lat is None
        or sim.cikis_lon is None
        or sim.varis_lat is None
        or sim.varis_lon is None
    ):
        raise ValueError("missing_coords")

    result = await hydrator.hydrate(sim)
    if result is None:
        raise ValueError("provider_unavailable")

    return {
        "lokasyon_id": result.lokasyon_id,
        "raw_segment_count": result.raw_segment_count,
        "resampled_segment_count": result.resampled_segment_count,
        "elevation_coverage_pct": result.elevation_coverage_pct,
        "total_km": result.total_km,
        "total_ascent_m": result.total_ascent_m,
        "total_descent_m": result.total_descent_m,
        "hydrated_at": sim.hydrated_at,
    }
