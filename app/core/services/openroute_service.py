"""
TIR Yakıt Takip - OpenRouteService Entegrasyonu (Async)
Geocode (adres -> koordinat) entegrasyonu.
REFACTORED: blocking requests → httpx.AsyncClient, thread-safe singleton

2026-07-22 dead-code denetimi: rota-profili hesaplama tarafı (RouteProfile,
get_route_profile/get_route_profile_offline, _haversine_distance, sync
is_configured(), close()) silindi — sıfır prod çağıranı vardı (yalnız kendi
dedike testleri), v2/modules/route_simulation'ın kendi RouteSimulator/
get_route_details pipeline'ı tarafından zaten ikame edilmişti. Geocode
tarafı (bu dosyanın geri kalanı) hâlâ canlı —
v2/modules/location/infrastructure/geocode_providers.py'nin 3 aşamalı
geocode fallback zincirinin 2 aşaması burayı kullanıyor.
"""

import threading
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

try:
    import httpx

    from v2.modules.platform_infra.monitoring.external_api_probe import (
        get_monitored_client,
    )

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


class OpenRouteService:
    """
    OpenRouteService API entegrasyonu (Async)
    https://openrouteservice.org/

    Ücretsiz Tier: 2,000 istek/gün
    """

    TIMEOUT = 15.0  # seconds

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.OPENROUTESERVICE_API_KEY
        self.base_url = settings.OPENROUTE_API_BASE_URL
        # Geocode lives at the same host's root, not under /v2 (same bug
        # class already fixed in openroute_client.py and lokasyon_service.py
        # — found here independently during a 0-mock epic audit; the
        # previous f"{base_url}/geocode/search" always 404'd in prod since
        # base_url already contains /v2).
        _origin = urlsplit(self.base_url)
        self.geocode_url = urlunsplit(
            (_origin.scheme, _origin.netloc, "/geocode/search", "", "")
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> "httpx.AsyncClient":
        """Lazy-load async HTTP client (connection pooling)"""
        if self._client is None:
            self._client = get_monitored_client(timeout=self.TIMEOUT)
        return self._client

    async def _resolve_api_key(self) -> Optional[str]:
        """DB-configured key (admin UI) takes priority over the .env
        fallback — see v2.modules.admin_platform.public."""
        if not HTTPX_AVAILABLE:
            return None
        from v2.modules.admin_platform.public import (
            get_integration_secret,
        )

        return await get_integration_secret("openroute", self.api_key)

    async def is_configured_async(self) -> bool:
        """DB-aware configured check — an admin-only (no .env fallback) key
        is honored instead of silently falling to offline mode."""
        return bool(await self._resolve_api_key())

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Adres -> Koordinat dönüşümü (Async).
        """
        api_key = await self._resolve_api_key()
        if not api_key:
            return self.geocode_offline(address)

        try:
            client = await self._get_client()
            url = self.geocode_url
            params: Dict[str, Any] = {
                "api_key": api_key,
                "text": address,
                "size": 1,
                "boundary.country": "TR",
            }
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                if features:
                    coords = features[0].get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        return (coords[0], coords[1])

            return self.geocode_offline(address)

        except httpx.TimeoutException:
            logger.warning("Geocode timeout, falling back to offline")
            return self.geocode_offline(address)
        except Exception as e:
            logger.error(f"Geocode error: {e}, falling back to offline")
            return self.geocode_offline(address)

    def geocode_offline(self, address: str) -> Optional[Tuple[float, float]]:
        """Kısıtlı offline geocoding (Sadece test ve temel şehirler)"""
        major_cities = {
            "istanbul": (28.9784, 41.0082),
            "ankara": (32.8597, 39.9334),
            "izmir": (27.1384, 38.4237),
            "bursa": (29.0610, 40.1815),
            "antalya": (30.7133, 36.8969),
            "gebze": (29.4300, 40.8000),
            "kocaeli": (29.9167, 40.7667),
        }
        addr_lower = str(address).lower()
        for city, coords in major_cities.items():
            if city in addr_lower:
                return coords
        return None


# Thread-safe Singleton
_openroute_service: Optional[OpenRouteService] = None
_openroute_lock = threading.Lock()


def get_openroute_service() -> OpenRouteService:
    """Thread-safe Singleton OpenRouteService instance"""
    global _openroute_service
    if _openroute_service is None:
        with _openroute_lock:
            if _openroute_service is None:
                _openroute_service = OpenRouteService()
    return _openroute_service
