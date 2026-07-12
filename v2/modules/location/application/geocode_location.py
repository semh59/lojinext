"""Use-case: geocode a free-text query into coordinate suggestions.

Cascading fallback chain: OpenRouteService -> Nominatim -> offline table.
"""

from v2.modules.location.infrastructure.geocode_providers import (
    geocode_via_nominatim,
    geocode_via_offline,
    geocode_via_openroute,
)


async def geocode_location(q: str, limit: int = 5) -> list[dict]:
    query = (q or "").strip()
    if len(query) < 2:
        return []

    ors_results = await geocode_via_openroute(query, limit=limit)
    if ors_results:
        return ors_results

    nominatim_results = await geocode_via_nominatim(query, limit=limit)
    if nominatim_results:
        return nominatim_results

    return geocode_via_offline(query)
