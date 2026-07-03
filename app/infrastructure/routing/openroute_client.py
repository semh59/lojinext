import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv

from app.config import settings
from app.core.utils.polyline import PolylineDecoder
from app.domain.services.route_analyzer import route_analyzer
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreakerError,
    CircuitBreakerRegistry,
)

# Load environment
load_dotenv()

logger = get_logger(__name__)


class OpenRouteClient:
    """
    OpenRouteService API Client

    Kullanım:
        client = OpenRouteClient()
        result = client.get_distance(
            origin=(40.7669, 29.4319),    # Gebze (lat, lon)
            destination=(39.9334, 32.8597) # Ankara
        )
        print(result)
        # {'distance_km': 452.3, 'duration_hours': 5.5, 'source': 'api'}
    """

    PROFILE = "driving-hgv"  # Heavy Goods Vehicle (TIR)

    # Rate limiting (class-level async lock for all instances)
    _last_request_time = 0.0
    _rate_limit_lock: Optional[asyncio.Lock] = None
    MIN_REQUEST_INTERVAL = 1.0  # 1 saniye minimum aralık

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: OpenRouteService API key. None ise .env dosyasından okunur.
        """
        self.api_key = (
            api_key
            or os.getenv("OPENROUTESERVICE_API_KEY")
            or settings.OPENROUTESERVICE_API_KEY
            or os.getenv("OPENROUTE_API_KEY")
        )

        if not self.api_key:
            logger.warning(
                "OPENROUTESERVICE_API_KEY tanımlanmamış (legacy OPENROUTE_API_KEY de "
                "yok)! API çağrıları başarısız olacak."
            )

        self.base_url = settings.OPENROUTE_API_BASE_URL
        # Geocode lives at the same host's root, not under /v2 — derive from
        # the base_url's origin so a test-stub override (Kategori B) points
        # both endpoints at the same server.
        _origin = urlsplit(self.base_url)
        self.geocode_url = urlunsplit(
            (_origin.scheme, _origin.netloc, "/geocode/search", "", "")
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._db = None  # Lazy loading

    @property
    def db(self):
        """Deprecated: Use get_sync_session directly"""
        return None

    async def get_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        use_cache: bool = True,
        include_details: bool = True,
    ) -> Optional[Dict]:
        """
        İki koordinat arası mesafe hesapla (async).

        Args:
            origin: (latitude, longitude) başlangıç
            destination: (latitude, longitude) varış
            use_cache: Veritabanı cache kullan (önerilir)
            include_details: Yol tipi ve eğim analizi detaylarını getir

        Returns:
            {
                'distance_km': float,
                'duration_hours': float,
                'ascent_m': float,      # Toplam bayır çıkış (metre)
                'descent_m': float,     # Toplam bayır iniş (metre)
                'source': 'cache' | 'api' | 'error',
                'details': { ... }      # include_details=True ise detaylı analiz
            }
            veya hata durumunda None
        """
        # Input validation
        if not self._validate_coordinates(origin, destination):
            logger.error(f"Geçersiz koordinatlar: {origin} -> {destination}")
            return None

        # 1. Cache kontrolü
        if use_cache:
            cached = await self._get_from_cache(origin, destination)
            if cached:
                # Sanity Check for Cached Data
                from app.core.services.route_validator import RouteValidator

                result = RouteValidator.validate_and_correct(cached)

                logger.debug(f"Cache hit: {origin} -> {destination}")
                return {**result, "source": "cache"}

        if not self.api_key:
            logger.error("API key eksik, mesafe hesaplanamadı")
            return None

        # Phase 3: Centralized Circuit Breaker
        breaker = CircuitBreakerRegistry.get_sync("openroute")

        try:
            result = await breaker.call(
                self._call_api, origin, destination, include_details=include_details
            )

            if result:
                # Sanity Check for New API Data
                from app.core.services.route_validator import RouteValidator

                result = RouteValidator.validate_and_correct(result)

                # 3. Cache'e kaydet
                await self._save_to_cache(origin, destination, result)
                return {**result, "source": "api"}
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker 'openroute' is OPEN. Falling back to None (physics-only skip)."
            )
        except Exception as e:
            logger.error(f"ORS API Call unexpected error: {e}")

        return None

    async def geocode(self, text: str) -> Optional[Tuple[float, float]]:
        """
        Adresi koordinata (lat, lon) dönüştürür (async).

        Args:
            text: Adres veya şehir ismi (örn: 'Ankara, Türkiye')

        Returns:
            (latitude, longitude) veya hata durumunda None
        """
        if not text or not self.api_key:
            return None

        # Circuit Breaker kontrolü
        breaker = CircuitBreakerRegistry.get_sync("openroute_geo")

        try:
            return await breaker.call(self._call_geocode_api, text)
        except CircuitBreakerError:
            logger.warning("Geocode circuit breaker is OPEN.")
        except Exception as e:
            logger.error(f"Geocoding error: {e}")

        return None

    async def _call_geocode_api(self, text: str) -> Optional[Tuple[float, float]]:
        """ORS Geocoding API çağrısı (async)"""
        params: Dict[str, Any] = {
            "text": text,
            "size": 1,
            "boundary.country": "TUR",  # Türkiye dışı aramaları kısıtla
        }
        headers = {"Authorization": f"api-key {self.api_key}"}

        try:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=20.0)

            response = await self._client.get(
                self.geocode_url, params=params, headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                if "features" in data and len(data["features"]) > 0:
                    # ORS [lon, lat] döner
                    coords = data["features"][0]["geometry"]["coordinates"]
                    return (float(coords[1]), float(coords[0]))  # Convert to [lat, lon]
            else:
                logger.error(
                    f"Geocode API error: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Geocode request failed: {e}")

        return None

    def _validate_coordinates(
        self, origin: Tuple[float, float], destination: Tuple[float, float]
    ) -> bool:
        """Koordinatların geçerli ve Türkiye sınırları içinde olduğunu doğrula"""
        try:
            for coord in [origin, destination]:
                if not isinstance(coord, (list, tuple)) or len(coord) != 2:
                    return False
                lat, lon = coord
                # Türkiye yaklaşık sınırları
                if not (35.0 <= lat <= 43.0 and 25.0 <= lon <= 46.0):
                    return False
            return True
        except Exception:
            return False

    async def _call_api(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        include_details: bool = True,
    ) -> Optional[Dict]:
        """Gerçek API çağrısını yap (async)"""
        if not self.api_key:
            return None

        # Rate limiting (async-safe)
        if self._rate_limit_lock is None:
            self._rate_limit_lock = asyncio.Lock()

        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                await asyncio.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

        # JSON endpoint for better extra_info support
        url = f"{self.base_url}/directions/{self.PROFILE}/json"

        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        # ORS [lon, lat] bekler
        payload = {
            "coordinates": [[origin[1], origin[0]], [destination[1], destination[0]]],
            "preference": "fastest",
        }

        if include_details:
            payload["extra_info"] = ["steepness", "waycategory", "waytype", "surface"]
            payload["elevation"] = "true"
            payload["geometry"] = "true"

        try:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=20.0)

            response = await self._client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                route = data["routes"][0]
                summary = route["summary"]

                result = {
                    "distance_km": round(summary["distance"] / 1000.0, 1),
                    "duration_hours": round(summary["duration"] / 3600.0, 1),
                    "ascent_m": summary.get("ascent", 0),
                    "descent_m": summary.get("descent", 0),
                }

                if include_details and "extras" in route and "geometry" in route:
                    # Geometry is usually encoded polyline
                    geometry = route["geometry"]
                    points = []

                    if isinstance(geometry, str):
                        try:
                            # Use our local decoder (returns [(lat, lon)])
                            decoded_points = PolylineDecoder.decode(geometry)
                            points = [[p[1], p[0]] for p in decoded_points]

                        except Exception as e:
                            logger.error(f"Polyline decode error: {e}", exc_info=True)
                            points = []
                    elif isinstance(geometry, list):
                        points = (
                            geometry  # Already decoded (e.g. if GeoJSON was requested)
                        )

                    if points:
                        try:
                            details = route_analyzer.analyze_segments(
                                points,
                                route["extras"],
                                reference_distance_m=summary.get("distance", 0),
                            )
                            result["details"] = details
                            result["extras"] = route["extras"]  # Add raw extras
                        except Exception as e:
                            logger.error(f"Route analysis error: {e}", exc_info=True)
                    else:
                        logger.warning("No points to analyze!")

                return result
            else:
                from app.core.exceptions import RouteProcessingError

                if response.status_code == 403:
                    raise RouteProcessingError(
                        "Routing provider forbidden (403). Quota exceeded or API key invalid.",
                        provider_status=403,
                    )
                elif response.status_code == 404:
                    raise RouteProcessingError(
                        "Route not found (404).",
                        provider_status=404,
                    )
                elif response.status_code == 429:
                    raise RouteProcessingError(
                        "Rate limited (429). Too many requests to routing provider.",
                        provider_status=429,
                    )
                else:
                    logger.error(
                        f"API Hatası: {response.status_code} - {response.text}"
                    )
                    raise RouteProcessingError(
                        f"Routing API error: {response.status_code}",
                        provider_status=response.status_code,
                    )
        except Exception as e:
            from app.core.exceptions import RouteProcessingError

            if isinstance(e, RouteProcessingError):
                raise
            logger.error(f"API Çağrı Hatası: {e}")
            raise RouteProcessingError(f"Routing API call failed: {str(e)}")

    async def _get_from_cache(
        self, origin: Tuple[float, float], destination: Tuple[float, float]
    ) -> Optional[Dict]:
        """Veritabanından cache'lenmiş mesafe ve elevation verileri al (async)"""
        lat1, lon1 = origin
        lat2, lon2 = destination

        # Koordinat toleransı (yaklaşık 100m)
        tolerance = 0.001

        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(
                        text("""
                        SELECT api_mesafe_km, api_sure_saat, ascent_m, descent_m, route_analysis
                        FROM lokasyonlar
                        WHERE ABS(cikis_lat - :lat1) < :tol
                          AND ABS(cikis_lon - :lon1) < :tol
                          AND ABS(varis_lat - :lat2) < :tol
                          AND ABS(varis_lon - :lon2) < :tol
                          AND api_mesafe_km IS NOT NULL
                        LIMIT 1
                    """),
                        {
                            "lat1": lat1,
                            "lon1": lon1,
                            "lat2": lat2,
                            "lon2": lon2,
                            "tol": tolerance,
                        },
                    )
                ).fetchone()

                if row:
                    # The `extras` field is not directly stored in `lokasyonlar` table,
                    # but `route_analysis` (details) is.
                    # We can include `details` if available.
                    cached_result = {
                        "distance_km": row.api_mesafe_km,
                        "duration_hours": row.api_sure_saat or 0,
                        "ascent_m": row.ascent_m or 0,
                        "descent_m": row.descent_m or 0,
                    }
                    if row.route_analysis:
                        cached_result["details"] = row.route_analysis
                    return cached_result
        except Exception as e:
            logger.error(f"Cache okuma hatası: {e}")

        # lokasyonlar'da bulunamadı — Redis'te ad-hoc rota cache kontrol et.
        try:
            from app.infrastructure.cache.redis_pubsub import get_redis_val

            _rkey = (
                f"ors:route:{round(lat1, 4)},{round(lon1, 4)}"
                f"-{round(lat2, 4)},{round(lon2, 4)}"
            )
            cached_r = await get_redis_val(_rkey)
            if cached_r:
                logger.debug("Redis ad-hoc cache hit: %s -> %s", origin, destination)
                return cached_r
        except Exception as _re:
            logger.debug("Redis route cache okuma hatası: %s", _re)

        return None

    async def _save_to_cache(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        result: Dict,
    ):
        """Mesafe ve elevation sonucunu veritabanına kaydet (async)"""
        lat1, lon1 = origin
        lat2, lon2 = destination

        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                # Mevcut kayıt var mı kontrol et
                existing = (
                    await session.execute(
                        text("""
                        SELECT id FROM lokasyonlar
                        WHERE ABS(cikis_lat - :lat1) < 0.001
                          AND ABS(cikis_lon - :lon1) < 0.001
                          AND ABS(varis_lat - :lat2) < 0.001
                          AND ABS(varis_lon - :lon2) < 0.001
                        LIMIT 1
                    """),
                        {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2},
                    )
                ).fetchone()

                if existing:
                    # Güncelle - elevation dahil
                    await session.execute(
                        text("""
                        UPDATE lokasyonlar
                        SET api_mesafe_km = :dist,
                            api_sure_saat = :dur,
                            ascent_m = :asc,
                            descent_m = :desc,
                            last_api_call = :now
                        WHERE id = :id
                    """),
                        {
                            "dist": result["distance_km"],
                            "dur": result["duration_hours"],
                            "asc": result.get("ascent_m", 0),
                            "desc": result.get("descent_m", 0),
                            "now": datetime.now(timezone.utc).isoformat(),
                            "id": existing.id,
                        },
                    )
                    await session.commit()
                    logger.debug(f"Cache güncellendi: ID {existing.id}")
                else:
                    # Eşleşen lokasyonlar satırı yok — Redis'e ad-hoc cache yaz.
                    try:
                        from app.infrastructure.cache.redis_pubsub import set_redis_val

                        _rkey = (
                            f"ors:route:{round(lat1, 4)},{round(lon1, 4)}"
                            f"-{round(lat2, 4)},{round(lon2, 4)}"
                        )
                        await set_redis_val(_rkey, result, expire=7 * 24 * 3600)
                        logger.debug("Ad-hoc rota Redis cache'e alındı: %s", _rkey)
                    except Exception as _re:
                        logger.debug("Redis route cache yazma hatası: %s", _re)

        except Exception as e:
            logger.error(f"Cache kayıt hatası: {e}")

    async def update_route_distance(self, lokasyon_id: int) -> Optional[Dict]:
        """
        Mevcut bir güzergahın mesafesini API'den güncelle (async).
        """
        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(
                        text("""
                        SELECT cikis_lat, cikis_lon, varis_lat, varis_lon
                        FROM lokasyonlar WHERE id = :id
                    """),
                        {"id": lokasyon_id},
                    )
                ).fetchone()

                if not row or not all(
                    [row.cikis_lat, row.cikis_lon, row.varis_lat, row.varis_lon]
                ):
                    logger.warning(f"Lokasyon {lokasyon_id} koordinat bilgisi eksik")
                    return None

                origin = (row.cikis_lat, row.cikis_lon)
                destination = (row.varis_lat, row.varis_lon)

            # API çağrısı
            result = await self.get_distance(
                origin, destination, use_cache=False, include_details=True
            )

            if not result:
                logger.error(f"Güzergah {lokasyon_id} için API sonucu alınamadı.")
                return None

            # Extract detailed breakdown
            details = result.get("details", {})
            otoban_km = 0.0
            sehir_ici_km = 0.0

            if details:
                if "highway" in details:
                    otoban_km = sum(details["highway"].values())
                    # Convert stats to KM if they are in meters?
                    # route_analyzer returns in KM already (lines 138-141)
                if "other" in details:
                    sehir_ici_km = sum(details["other"].values())

            if result:
                now = datetime.now(timezone.utc)
                # details is already a dict from analyze_segments

                from app.database.connection import AsyncSessionLocal

                async with AsyncSessionLocal() as session:
                    query = text("""
                        UPDATE lokasyonlar
                        SET api_mesafe_km = :dist,
                            api_sure_saat = :dur,
                            ascent_m = :asc,
                            descent_m = :desc,
                            mesafe_km = :dist_km,
                            tahmini_sure_saat = :dur_h,
                            last_api_call = :now,
                            route_analysis = :details,
                            otoban_mesafe_km = :otoban,
                            sehir_ici_mesafe_km = :sehir
                        WHERE id = :id
                    """)

                    import json

                    await session.execute(
                        query,
                        {
                            "dist": result["distance_km"],
                            "dur": result["duration_hours"],
                            "asc": result.get("ascent_m", 0),
                            "desc": result.get("descent_m", 0),
                            "dist_km": result["distance_km"],  # Sync user-visible field
                            "dur_h": result[
                                "duration_hours"
                            ],  # Sync user-visible field
                            "now": now,
                            "details": json.dumps(
                                details
                            ),  # Serialize dict to JSON string
                            "otoban": otoban_km,
                            "sehir": sehir_ici_km,  # Corrected from sehir_km to sehir_ici_km
                            "id": lokasyon_id,
                        },
                    )
                    await session.commit()

                    logger.info(
                        f"Güzergah {lokasyon_id} güncellendi: {result['distance_km']} km, "
                        f"Otoban: {otoban_km} km, Şehiriçi: {sehir_ici_km} km, "
                        f"↑{result.get('ascent_m', 0)}m ↓{result.get('descent_m', 0)}m"
                    )
                    return result

        except Exception as e:
            logger.error(f"Güzergah güncelleme hatası: {e}", exc_info=True)

        return None


# Singleton instance
_client_instance: Optional[OpenRouteClient] = None
_client_lock = asyncio.Lock()


async def get_route_client() -> OpenRouteClient:
    """Async-safe singleton getter"""
    global _client_instance
    if _client_instance is None:
        async with _client_lock:
            if _client_instance is None:
                _client_instance = OpenRouteClient()
    return _client_instance
