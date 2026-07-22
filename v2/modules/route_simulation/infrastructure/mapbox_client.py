"""
Mapbox Routing Client (Primary Provider)
Provides accurate routing data with road type classification via maxspeed annotations.
"""

from typing import Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.infrastructure.logging.logger import get_logger
from v2.modules.platform_infra.cache.cache_manager import (
    CacheManager,
    get_cache_manager,
)
from v2.modules.platform_infra.monitoring.external_api_probe import get_monitored_client
from v2.modules.route_simulation.domain.segment_simulator import SegmentInput
from v2.modules.route_simulation.infrastructure.retry import with_async_retry

# Phase 2.3: Mapbox Directions response cache TTL.
# Plan §9 Phase 2: "Directions response cache (1-gün TTL — traffic değişir)".
# Yapısal veri stabil, traffic 24h içinde anlamlı şekilde değişebilir.
_MAPBOX_DIRECTIONS_CACHE_TTL_S = 24 * 3600
_MAPBOX_COORD_PRECISION = 4  # ~11m hassasiyet (Open-Meteo ile uyumlu)

logger = get_logger(__name__)


class MapboxClient:
    """
    Mapbox Directions API Client.
    Profile: driving-traffic (Real-time traffic)
    Uses maxspeed annotations for road type classification.
    """

    def __init__(self, cache: Optional[CacheManager] = None) -> None:
        # CRITICAL FIX (Phase 5.0): settings.MAPBOX_API_KEY is SecretStr;
        # passing it directly to httpx URL params produces "**********"
        # (str(SecretStr) → masked value). Mapbox returned 401 silently.
        # Resolve to plain string here once.
        raw_key = settings.MAPBOX_API_KEY
        # Hem SecretStr (normal config) hem de plain str (test monkeypatch /
        # alternatif config) güvenli — aksi halde str'e .get_secret_value()
        # AttributeError veriyordu.
        if raw_key is None:
            self.api_key: Optional[str] = None
        elif hasattr(raw_key, "get_secret_value"):
            self.api_key = raw_key.get_secret_value()
        else:
            self.api_key = str(raw_key)
        self.base_url = settings.MAPBOX_API_BASE_URL
        # self.api_key above is the .env-sourced fallback; _resolve_api_key()
        # checks the admin-configurable entegrasyon_ayarlari row first (see
        # v2.modules.admin_platform.public) so a key entered via the
        # admin UI takes effect immediately, without a restart.
        # Phase 2.3: Redis-backed cache. None geçilirse singleton CacheManager.
        # Sync API (get/set) async handler içinden de güvenli — Redis çağrıları
        # non-blocking IO açısından ms ölçeğinde.
        self._cache = cache if cache is not None else get_cache_manager()

    async def _resolve_api_key(self) -> Optional[str]:
        from v2.modules.admin_platform.public import (
            get_integration_secret,
        )

        return await get_integration_secret("mapbox", self.api_key)

    async def get_route(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
    ) -> Optional[Dict]:
        """
        Fetch route from Mapbox with road type classification.

        Args:
            start_coords: (lon, lat)
            end_coords: (lon, lat)

        Returns:
            Dict with standardized route structure including road analysis, or None if failed.
        """
        api_key = await self._resolve_api_key()
        if not api_key:
            logger.warning("Mapbox API Key missing. Skipping fallback.")
            return None

        lon1, lat1 = start_coords
        lon2, lat2 = end_coords

        # Format: {lon},{lat};{lon},{lat}
        coordinates_str = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{self.base_url}/{coordinates_str}"

        # NOT (Phase 0, 2026-05-29 canlı API teyidi): Mapbox Directions
        # geçerli annotation listesi: duration, distance, speed, congestion,
        # congestion_numeric, closure, state_of_charge, energy_levels,
        # maxspeed. `road_class` listede YOK — eklenirse API 422 InvalidInput
        # döner. Road class yine bize lazım (sefer aggregate'in 3-bucket
        # otoyol/devlet_yolu/sehir_ici sınıflandırması için) → step.
        # intersections[*].mapbox_streets_v8.class'tan reconcile ediliyor
        # (~99.9% doluluk, bkz. docs/.../mapbox-samples/_summary.md).
        # `steps=true` o veriyi getirir.
        params = {
            "access_token": api_key,
            "geometries": "geojson",
            "overview": "full",
            "steps": "true",
            "annotations": "distance,duration,speed,maxspeed,congestion,congestion_numeric",
        }

        try:
            async with get_monitored_client() as client:
                response = await client.get(url, params=params, timeout=15.0)

                if response.status_code != 200:
                    logger.error(f"Mapbox API Error: {response.text}")
                    return None

                data = response.json()
                if not data.get("routes"):
                    logger.warning("Mapbox returned no routes.")
                    return None

                route = data["routes"][0]
                geometry = route["geometry"]

                # Standardize Result
                dist_km = round(route["distance"] / 1000.0, 2)
                duration_min = round(route["duration"] / 60.0, 0)

                # Road Classification from maxspeed annotations
                road_analysis = self._classify_road_segments(route)
                otoban_km = road_analysis.get("otoban_km", 0.0)
                sehir_ici_km = road_analysis.get("sehir_ici_km", 0.0)
                trunk_km = road_analysis.get("trunk_km", 0.0)
                detailed_analysis = road_analysis.get("detailed")
                normalized_route_analysis = dict(detailed_analysis or {})
                if road_analysis.get("ratios"):
                    normalized_route_analysis["ratios"] = dict(road_analysis["ratios"])

                result = {
                    "distance_km": dist_km,
                    "duration_min": duration_min,
                    "ascent_m": 0.0,  # Mapbox Directions API doesn't provide elevation
                    "descent_m": 0.0,
                    "otoban_mesafe_km": round(otoban_km, 2),
                    "sehir_ici_mesafe_km": round(sehir_ici_km, 2),
                    "flat_distance_km": round(dist_km, 2),
                    "geometry": geometry,
                    "source": "mapbox",
                    "route_analysis": normalized_route_analysis or None,
                }

                logger.info(
                    f"Mapbox Route: {dist_km}km "
                    f"(otoban: {otoban_km:.1f}km, şehir içi: {sehir_ici_km:.1f}km, "
                    f"trunk: {trunk_km:.1f}km)"
                )
                return result

        except httpx.RequestError as exc:
            # Do NOT log exc directly — httpx.RequestError includes the full request
            # URL in its message, which contains the access_token query param.
            from v2.modules.platform_infra.monitoring.external_api_probe import (
                _sanitize_url,
            )

            # httpx'te exc.request property'si request set EDİLMEMİŞSE RuntimeError
            # fırlatır (None dönmez) → güvenli erişim için _request attribute'u kullan,
            # aksi halde hata-işleyici kendisi çöker.
            _req = getattr(exc, "_request", None)
            safe_url = _sanitize_url(
                str(_req.url) if _req is not None else self.base_url
            )
            logger.error("Mapbox network error: %s — %s", type(exc).__name__, safe_url)
            return None
        except Exception as e:
            logger.exception(f"Mapbox Async Error: {e}")
            return None

    @staticmethod
    def _reconcile_segment_road_classes(route: Dict) -> List[str]:
        """Annotation segment'leri için road_class dizisi türet.

        Mapbox Directions response'unda `road_class` annotation YOK; bunun
        yerine `step.intersections[*]` listesinde:
          - `geometry_index`: annotation array'indeki başlangıç index
          - `mapbox_streets_v8.class`: motorway/trunk/primary/secondary/
            tertiary/street/residential/service + `_link` variant

        Reconcile mantığı: geometry_index'lere göre sıralı intersection
        listesini gez; her annotation segment'i, kendinden önceki son
        intersection'ın class'ını miras alır.

        Returns:
            Tüm leg'lerin annotation segment sayısı kadar string list
            (dolduralamayan segmentler için "" string).
        """
        legs = route.get("legs", []) or []
        seg_count = sum(
            len((leg.get("annotation") or {}).get("distance", [])) for leg in legs
        )
        if not seg_count:
            return []

        # (geometry_index, class) çiftleri — leg ofsetli
        points: List[Tuple[int, str]] = []
        offset = 0
        for leg in legs:
            leg_seg_count = len((leg.get("annotation") or {}).get("distance", []))
            for step in leg.get("steps", []) or []:
                for inter in step.get("intersections", []) or []:
                    gi = inter.get("geometry_index")
                    streets = inter.get("mapbox_streets_v8") or {}
                    cls = streets.get("class")
                    if gi is None or not cls:
                        continue
                    points.append((offset + int(gi), cls))
            offset += leg_seg_count

        if not points:
            return [""] * seg_count

        points.sort(key=lambda p: p[0])

        result: List[str] = [""] * seg_count
        next_idx = 0
        current_class = points[0][1]
        for seg_i in range(seg_count):
            while next_idx < len(points) and points[next_idx][0] <= seg_i:
                current_class = points[next_idx][1]
                next_idx += 1
            result[seg_i] = current_class
        return result

    def _classify_road_segments(self, route: Dict) -> Dict:
        """
        Classify road segments using maxspeed annotations from Mapbox.

        Speed thresholds (Turkey):
            >= 110 km/h → Motorway/Otoyol
            >= 80 km/h  → Trunk/Primary (high-speed rural)
            >= 50 km/h  → Secondary/Urban arterial
            < 50 km/h   → City/Residential

        Returns:
            Dict with otoban_km, trunk_km, sehir_ici_km, and detailed analysis.
        """
        legs = route.get("legs", [])
        if not legs:
            dist_km = route.get("distance", 0) / 1000.0
            return {
                "otoban_km": 0.0,
                "trunk_km": 0.0,
                "sehir_ici_km": dist_km,
                "detailed": None,
            }

        motorway_m = 0.0
        trunk_m = 0.0
        primary_m = 0.0
        secondary_m = 0.0
        city_m = 0.0

        # Reconcile: road_class annotation YOK; step.intersections'tan üret.
        # Tüm leg'leri kapsayan flat dizi (leg ofsetli).
        global_classes = self._reconcile_segment_road_classes(route)
        global_idx = 0

        for leg in legs:
            annotation = leg.get("annotation", {})
            distances: List[float] = annotation.get("distance", [])
            maxspeeds: List[Dict] = annotation.get("maxspeed", [])

            if not distances:
                # No granular data — fallback to average speed
                leg_dist = leg.get("distance", 0)
                leg_dur = leg.get("duration", 1)
                avg_speed_kmh = (leg_dist / leg_dur) * 3.6 if leg_dur > 0 else 0

                if avg_speed_kmh >= 100:
                    motorway_m += leg_dist
                elif avg_speed_kmh >= 70:
                    trunk_m += leg_dist
                elif avg_speed_kmh >= 45:
                    primary_m += leg_dist
                else:
                    city_m += leg_dist
                continue

            for i, seg_dist in enumerate(distances):
                if global_idx < len(global_classes):
                    r_class = global_classes[global_idx]
                else:
                    r_class = ""
                global_idx += 1

                # _link variant'larını ana sınıfa indir (motorway_link → motorway)
                if r_class.endswith("_link"):
                    r_class = r_class[: -len("_link")]

                # Primary Classification via Road Class
                if r_class == "motorway":
                    motorway_m += seg_dist
                elif r_class in ("trunk", "primary"):
                    # Turkey: Trunk roads are usually high-speed D-roads
                    trunk_m += seg_dist
                elif r_class in ("secondary", "tertiary"):
                    primary_m += seg_dist
                elif r_class in ("street", "residential", "service"):
                    city_m += seg_dist
                else:
                    # Class boş veya tanımsız — maxspeed bucket fallback
                    speed_info = maxspeeds[i] if i < len(maxspeeds) else None
                    speed_kmh = self._extract_speed_kmh(speed_info)

                    if speed_kmh and speed_kmh >= 110:
                        motorway_m += seg_dist
                    elif speed_kmh and speed_kmh >= 80:
                        trunk_m += seg_dist
                    elif speed_kmh and speed_kmh >= 50:
                        primary_m += seg_dist
                    else:
                        city_m += seg_dist

        # Convert to km
        motorway_km = motorway_m / 1000.0
        trunk_km = trunk_m / 1000.0
        primary_km = primary_m / 1000.0
        secondary_km = secondary_m / 1000.0
        city_km = city_m / 1000.0

        total_km = motorway_km + trunk_km + primary_km + secondary_km + city_km

        # User requested 3 categories: Otoyol, Devlet Yolu, Şehir İçi
        otoyol_ratio = motorway_km / total_km if total_km > 0 else 0
        devlet_ratio = (trunk_km + primary_km) / total_km if total_km > 0 else 0
        sehir_ratio = (secondary_km + city_km) / total_km if total_km > 0 else 1.0

        detailed = {
            "motorway": {"flat": round(motorway_km, 3), "up": 0, "down": 0},
            "trunk": {"flat": round(trunk_km, 3), "up": 0, "down": 0},
            "primary": {"flat": round(primary_km, 3), "up": 0, "down": 0},
            "secondary": {"flat": round(secondary_km, 3), "up": 0, "down": 0},
            "residential": {"flat": round(city_km, 3), "up": 0, "down": 0},
        }

        return {
            "otoban_km": round(
                (motorway_km + trunk_km + primary_km), 2
            ),  # Keep for legacy
            "sehir_ici_km": round(city_km + secondary_km, 2),  # Keep for legacy
            "ratios": {
                "otoyol": round(otoyol_ratio, 2),
                "devlet_yolu": round(devlet_ratio, 2),
                "sehir_ici": round(sehir_ratio, 2),
            },
            "detailed": detailed,
        }

    @staticmethod
    def _extract_speed_kmh(speed_info: Dict) -> Optional[float]:
        """
        Extract speed in km/h from Mapbox maxspeed annotation.

        Formats:
            {"speed": 120, "unit": "km/h"}
            {"speed": 55, "unit": "mph"}
            {"unknown": true}
            {"none": true}
        """
        if not isinstance(speed_info, dict):
            return None

        if speed_info.get("unknown") or speed_info.get("none"):
            return None

        speed = speed_info.get("speed")
        if speed is None:
            return None

        unit = speed_info.get("unit", "km/h")
        if unit == "mph":
            return speed * 1.60934
        return float(speed)

    # ------------------------------------------------------------------
    # Segment-mode extraction (Phase 1.2)
    # ------------------------------------------------------------------

    @classmethod
    def extract_segments(
        cls, route: Dict
    ) -> Tuple[List[SegmentInput], List[Tuple[float, float]]]:
        """Mapbox route response → (SegmentInput[], geometry coords).

        Her annotation segment'i:
          - length_km: distance / 1000
          - road_class: _reconcile_segment_road_classes (_link variant'lar
            ana sınıfa indirilir)
          - maxspeed_kmh: _extract_speed_kmh (unknown/none → None)
          - traffic_speed_kmh: annotation.speed (m/s) × 3.6
          - congestion: annotation.congestion (low/moderate/heavy/severe/unknown)
          - grade_pct: 0.0 — elevation enrichment Phase 1.4'te RouteSimulator'da
            geometry coord'larından doldurulur.

        Geometry coordinates: N+1 nokta (N segment için), Open-Meteo elevation
        enrichment input'u.
        """
        legs = route.get("legs") or []
        coords = (route.get("geometry") or {}).get("coordinates") or []

        if not legs:
            return [], list(coords)

        # Reconcile road_class (Phase 0.3'te yapıldı)
        global_classes = cls._reconcile_segment_road_classes(route)

        segments: List[SegmentInput] = []
        global_idx = 0
        for leg in legs:
            ann = leg.get("annotation") or {}
            distances = ann.get("distance") or []
            speeds = ann.get("speed") or []
            maxspeeds = ann.get("maxspeed") or []
            congestions = ann.get("congestion") or []

            for i, dist_m in enumerate(distances):
                rc = (
                    global_classes[global_idx]
                    if global_idx < len(global_classes)
                    else ""
                )
                if rc.endswith("_link"):
                    rc = rc[: -len("_link")]

                # traffic speed (m/s → km/h)
                tspeed_kmh: Optional[float] = None
                if i < len(speeds) and speeds[i] is not None:
                    try:
                        tspeed_kmh = float(speeds[i]) * 3.6
                    except (TypeError, ValueError):
                        tspeed_kmh = None

                # maxspeed
                ms_kmh: Optional[float] = None
                if i < len(maxspeeds):
                    ms_kmh = cls._extract_speed_kmh(maxspeeds[i])

                cg = congestions[i] if i < len(congestions) else "low"
                cg_str = cg if isinstance(cg, str) else "low"

                segments.append(
                    SegmentInput(
                        length_km=dist_m / 1000.0,
                        grade_pct=0.0,
                        road_class=rc,
                        maxspeed_kmh=ms_kmh,
                        traffic_speed_kmh=tspeed_kmh,
                        congestion=cg_str,
                    )
                )
                global_idx += 1

        return segments, [(float(c[0]), float(c[1])) for c in coords]

    @staticmethod
    def _segments_cache_key(
        start_coords: Tuple[float, float], end_coords: Tuple[float, float]
    ) -> str:
        """Cache key — koordinatları 4 decimal'e yuvarla.

        Plan §9: Directions cache 24h TTL. Coord round 4 decimal (~11m)
        aynı rotayı küçük GPS noise altında tek key'e map'ler.
        """
        lon1, lat1 = start_coords
        lon2, lat2 = end_coords
        p = _MAPBOX_COORD_PRECISION
        return f"mb:dir:{lon1:.{p}f},{lat1:.{p}f}:{lon2:.{p}f},{lat2:.{p}f}"

    async def get_segments(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
    ) -> Optional[Tuple[List[SegmentInput], List[Tuple[float, float]]]]:
        """Mapbox Directions çağrısı + SegmentInput'lara dönüştür.

        Cache-aware: 24h TTL Redis cache (Plan §9). Cache hit → HTTP yok.
        HTTP error veya boş route → None döner, cache'e yazılmaz.
        """
        cache_key = self._segments_cache_key(start_coords, end_coords)
        try:
            cached = self._cache.get(cache_key)
        except Exception as cache_exc:
            logger.debug("Mapbox cache get failed (non-fatal): %s", cache_exc)
            cached = None
        if cached is not None:
            logger.debug("Mapbox segments cache hit: %s", cache_key)
            return cached

        result = await self._fetch_segments(start_coords, end_coords)
        if result is not None:
            try:
                self._cache.set(
                    cache_key, result, ttl_seconds=_MAPBOX_DIRECTIONS_CACHE_TTL_S
                )
            except Exception as cache_exc:
                logger.debug("Mapbox cache set failed (non-fatal): %s", cache_exc)
        return result

    async def _fetch_segments(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
    ) -> Optional[Tuple[List[SegmentInput], List[Tuple[float, float]]]]:
        """Cache'siz network çağrısı — get_segments tarafından kullanılır."""
        api_key = await self._resolve_api_key()
        if not api_key:
            logger.warning("Mapbox API Key missing. fetch_segments aborted.")
            return None

        lon1, lat1 = start_coords
        lon2, lat2 = end_coords
        coordinates_str = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{self.base_url}/{coordinates_str}"

        # get_route() ile aynı params: steps=true (intersections için),
        # road_class YOK (Phase 0.1 422 bug'ı), traffic-aware annotation'lar.
        params = {
            "access_token": api_key,
            "geometries": "geojson",
            "overview": "full",
            "steps": "true",
            "annotations": "distance,duration,speed,maxspeed,congestion,congestion_numeric",
        }

        async def _request_once() -> Optional[
            Tuple[List[SegmentInput], List[Tuple[float, float]]]
        ]:
            async with get_monitored_client() as client:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code >= 500:
                    # Transient — retry tetikleyici exception olarak yükselt
                    raise httpx.HTTPStatusError(
                        f"Mapbox 5xx: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if response.status_code != 200:
                    # 4xx (401/403/422/429) — retry boşa, instant return None
                    logger.error(
                        "Mapbox get_segments HTTP %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None

                data = response.json()
                routes = data.get("routes") or []
                if not routes:
                    logger.warning("Mapbox get_segments: no routes")
                    return None

                segments, coords = self.extract_segments(routes[0])
                logger.info(
                    "Mapbox segments extracted: %d segments, %d coords",
                    len(segments),
                    len(coords),
                )
                return segments, coords

        try:
            # Phase 2.4: 3 deneme exponential backoff (0.5s, 1s, 2s).
            # Transient 5xx + network/timeout → retry; 4xx ANINDA None.
            return await with_async_retry(
                _request_once,
                max_attempts=3,
                base_delay_s=0.5,
                backoff_factor=2.0,
                retry_on=(
                    httpx.RequestError,
                    httpx.HTTPStatusError,
                    ConnectionError,
                ),
                label="mapbox.get_segments",
            )
        except Exception as exc:
            logger.exception("Mapbox get_segments error: %s", exc)
            return None


# Singleton instance
_client_instance: Optional[MapboxClient] = None


def get_mapbox_client() -> MapboxClient:
    """Lazy singleton getter."""
    global _client_instance
    if _client_instance is None:
        _client_instance = MapboxClient()
    return _client_instance
