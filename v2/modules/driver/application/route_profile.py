"""Şoför × güzergah tipi profili — per-type consumption coefficient."""

from __future__ import annotations

import statistics

ROUTE_TYPES = ["highway_dominant", "mountain", "urban", "mixed"]


def classify_route(route_analysis: dict) -> str:
    """Güzergahı 4 kategoriden birine atar."""
    total = sum(
        sum(float((v or {}).get(k, 0) or 0) for k in ("flat", "up", "down"))
        for v in route_analysis.values()
        if isinstance(v, dict)
    )
    if total == 0:
        return "mixed"

    motorway_km = sum(
        float((route_analysis.get("motorway") or {}).get(k, 0) or 0)
        for k in ("flat", "up", "down")
    )
    ascent = float(route_analysis.get("ascent_m") or 0)
    urban_km = sum(
        float((route_analysis.get("residential") or {}).get(k, 0) or 0)
        for k in ("flat", "up", "down")
    )

    if motorway_km / total > 0.6:
        return "highway_dominant"
    if ascent / max(total, 1) > 15:
        return "mountain"
    if urban_km / total > 0.3:
        return "urban"
    return "mixed"


async def get_driver_route_coefficient(
    sofor_id: int,
    route_type: str,
    min_trips: int = 5,
) -> float:
    """Şoförün belirli güzergah tipindeki tüketim sapma katsayısı.

    Yeterli veri yoksa 1.0 döndürür (nötr — tahmine dokunmaz).
    """
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        trips = await uow.sefer_repo.get_driver_trips_by_route_type(
            sofor_id=sofor_id, route_type=route_type, limit=50
        )

    if len(trips) < min_trips:
        return 1.0

    ratios = [
        t["gercek_tuketim"] / t["tahmini_tuketim"]
        for t in trips
        if t.get("gercek_tuketim")
        and t.get("tahmini_tuketim")
        and t["tahmini_tuketim"] > 0
    ]
    return round(statistics.median(ratios), 3) if ratios else 1.0
