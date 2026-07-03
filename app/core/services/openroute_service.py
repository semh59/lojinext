"""
TIR Yakıt Takip - OpenRouteService Entegrasyonu (Async)
Rota profili, yükseklik, bayır/düzlük hesaplama
REFACTORED: blocking requests → httpx.AsyncClient, thread-safe singleton
"""

import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import httpx

    from app.infrastructure.monitoring.external_api_probe import get_monitored_client

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.config import settings
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreakerError,
    CircuitBreakerRegistry,
)
from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry

logger = get_logger(__name__)


@dataclass
class RouteProfile:
    """Rota profili verisi"""

    distance_km: float
    duration_hours: float
    ascent_m: float  # Toplam tırmanış (bayır)
    descent_m: float  # Toplam iniş (düzlük)
    elevation_gain_ratio: float  # Bayır/düzlük oranı
    # True → haversine+sabit katsayıdan üretildi (API ulaşılamaz), gerçek veri yok.
    is_offline: bool = False


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
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> "httpx.AsyncClient":
        """Lazy-load async HTTP client (connection pooling)"""
        if self._client is None:
            self._client = get_monitored_client(timeout=self.TIMEOUT)
        return self._client

    def is_configured(self) -> bool:
        """API key var mı kontrol et"""
        return bool(self.api_key) and HTTPX_AVAILABLE

    def _haversine_distance(
        self, lon1: float, lat1: float, lon2: float, lat2: float
    ) -> float:
        """İki nokta arasındaki kuş uçuşu mesafeyi (KM) hesaplar"""
        import math

        R = 6371  # Dünya yarıçapı (km)
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) * math.sin(dLon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_route_profile_offline(
        self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]
    ) -> RouteProfile:
        """
        İnternet yoksa kuş uçuşu mesafe üzerinden tahmini profil döndür.
        """
        # Kuş uçuşu mesafeyi hesapla ve %25 yol kıvrım payı ekle
        air_distance = self._haversine_distance(
            start_coords[0], start_coords[1], end_coords[0], end_coords[1]
        )
        distance_km = air_distance * 1.25

        # Ortalama 70 km/s hız varsayımı
        duration_hours = distance_km / 70.0

        # Türkiye geneli için ortalama yükseklik tırmanışı
        ascent = (distance_km / 100) * 450
        descent = (distance_km / 100) * 400

        return RouteProfile(
            distance_km=round(distance_km, 1),
            duration_hours=round(duration_hours, 2),
            ascent_m=round(ascent, 0),
            descent_m=round(descent, 0),
            elevation_gain_ratio=0.53,
            is_offline=True,
        )

    async def get_route_profile(
        self,
        start_coords: Tuple[float, float],  # (lon, lat)
        end_coords: Tuple[float, float],  # (lon, lat)
        vehicle_type: str = "driving-hgv",  # Heavy Goods Vehicle (TIR)
    ) -> Optional[RouteProfile]:
        """
        İki nokta arasındaki rota profilini al (Async).
        İnternet yoksa veya API anahtarı eksikse offline fallback kullanır.
        """
        # Eğer yapılandırılmamışsa direkt offline'a düş
        if not self.is_configured():
            return self.get_route_profile_offline(start_coords, end_coords)

        try:
            # Rate Limiter: 2 istek/saniye (günlük 2000 limit)
            rate_limiter = RateLimiterRegistry.get_sync(
                "openroute", rate=2.0, period=1.0
            )
            await rate_limiter.acquire()

            # Circuit Breaker: 5 hata → 60 saniye bekleme
            circuit = CircuitBreakerRegistry.get_sync(
                "openroute", fail_max=5, reset_timeout=60.0
            )

            client = await self._get_client()
            url = f"{self.base_url}/directions/{vehicle_type}"
            headers = {
                "Content-Type": "application/json",
            }
            params = {"api_key": self.api_key}
            body = {
                "coordinates": [list(start_coords), list(end_coords)],
                "elevation": True,
                "instructions": False,
            }

            async def _make_request():
                return await client.post(url, json=body, headers=headers, params=params)

            response = await circuit.call(_make_request)

            if response.status_code == 200:
                data = response.json()
                route = data.get("routes", [{}])[0]
                summary = route.get("summary", {})

                distance_m = summary.get("distance", 0)
                distance_km = distance_m / 1000
                duration_sec = summary.get("duration", 0)
                ascent = summary.get("ascent", 0)
                descent = summary.get("descent", 0)

                total_elevation = ascent + descent
                ratio = (ascent / total_elevation) if total_elevation > 0 else 0.5

                return RouteProfile(
                    distance_km=round(distance_km, 1),
                    duration_hours=round(duration_sec / 3600, 2),
                    ascent_m=round(ascent, 0),
                    descent_m=round(descent, 0),
                    elevation_gain_ratio=round(ratio, 2),
                )
            else:
                logger.warning(
                    f"OpenRouteService error {response.status_code}, falling back to offline."
                )
                return self.get_route_profile_offline(start_coords, end_coords)

        except httpx.TimeoutException:
            logger.warning("OpenRouteService timeout, falling back to offline.")
            return self.get_route_profile_offline(start_coords, end_coords)
        except CircuitBreakerError:
            logger.warning(
                "OpenRouteService circuit breaker open, falling back to offline."
            )
            return self.get_route_profile_offline(start_coords, end_coords)
        except Exception as e:
            logger.error(f"OpenRouteService exception: {e}, falling back to offline.")
            return self.get_route_profile_offline(start_coords, end_coords)

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Adres -> Koordinat dönüşümü (Async).
        """
        if not self.is_configured():
            return self.geocode_offline(address)

        try:
            client = await self._get_client()
            url = f"{self.base_url}/geocode/search"
            params: Dict[str, Any] = {
                "api_key": self.api_key,
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

    async def close(self):
        """Graceful shutdown - HTTP client'ı kapat"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("OpenRouteService HTTP client closed.")


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
