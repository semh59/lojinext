"""Geocoding provider adapters (external HTTP calls).

Three interchangeable strategies for the same task (geocode a free-text
query into lat/lon suggestions) — kept in one file because they are one
cohesive infrastructure concern (talk to geocoding providers), not three
unrelated responsibilities. ``application/geocode_location.py`` composes
them into the actual fallback-chain use-case.
"""

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.monitoring.external_api_probe import get_monitored_client

logger = get_logger(__name__)


def dedupe_geocode_results(results: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for result in results:
        key = (
            round(float(result["lat"]), 6),
            round(float(result["lon"]), 6),
            str(result["label"]).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


async def geocode_via_openroute(q: str, limit: int = 5) -> list[dict]:
    from urllib.parse import urlsplit, urlunsplit

    from app.core.services.openroute_service import get_openroute_service

    openroute_service = get_openroute_service()
    if not await openroute_service.is_configured_async():
        return []

    try:
        client = await openroute_service._get_client()
        # BUG (found via 0-mock epiği real-network test): geocode lives
        # at the host root, not under /v2 — appending "/geocode/search"
        # directly to base_url (which includes /v2) built a 404'ing URL
        # in real production. Derive the origin instead, matching
        # OpenRouteClient's geocode_url derivation.
        _origin = urlsplit(openroute_service.base_url)
        geocode_url = urlunsplit(
            (_origin.scheme, _origin.netloc, "/geocode/search", "", "")
        )
        response = await client.get(
            geocode_url,
            params={
                "api_key": openroute_service.api_key,
                "text": q,
                "size": limit,
                "boundary.country": "TR",
            },
        )
        if response.status_code != 200:
            logger.warning("ORS geocode failed with status %s", response.status_code)
            return []

        features = response.json().get("features", [])
        suggestions = []
        for feature in features[:limit]:
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            label = (
                feature.get("properties", {}).get("label")
                or feature.get("properties", {}).get("name")
                or q
            )
            suggestions.append(
                {
                    "lat": float(coords[1]),
                    "lon": float(coords[0]),
                    "label": str(label),
                    "source": "ors",
                }
            )
        return dedupe_geocode_results(suggestions)
    except Exception as exc:
        logger.warning("ORS geocode error: %s", exc)
        return []


async def geocode_via_nominatim(q: str, limit: int = 5) -> list[dict]:
    try:
        async with get_monitored_client(
            timeout=10.0,
            headers={"User-Agent": f"{settings.PROJECT_NAME}/geocode"},
        ) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": limit,
                    "countrycodes": "tr",
                },
            )

        if response.status_code != 200:
            logger.warning(
                "Nominatim geocode failed with status %s", response.status_code
            )
            return []

        suggestions = []
        for item in response.json()[:limit]:
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is None or lon is None:
                continue
            suggestions.append(
                {
                    "lat": float(lat),
                    "lon": float(lon),
                    "label": str(item.get("display_name") or q),
                    "source": "nominatim",
                }
            )
        return dedupe_geocode_results(suggestions)
    except Exception as exc:
        logger.warning("Nominatim geocode error: %s", exc)
        return []


def geocode_via_offline(q: str) -> list[dict]:
    from app.core.services.openroute_service import get_openroute_service

    coords = get_openroute_service().geocode_offline(q)
    if not coords:
        return []
    lon, lat = coords
    return [{"lat": float(lat), "lon": float(lon), "label": q, "source": "offline"}]
