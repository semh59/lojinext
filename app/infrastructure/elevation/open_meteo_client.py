"""Open-Meteo Elevation API client (SRTM 30m DEM).

Phase 0.2 sonucu (docs/.../mapbox-samples/_tilequery_elevation.md): Mapbox
mapbox-terrain-v2 contour tilequery Türkiye için yetersiz (sahil -10m, dağ
zirveleri 200-270m hatalı); Open-Meteo SRTM 9/10 nokta ±100m altında.

API:
    GET https://api.open-meteo.com/v1/elevation
        ?latitude=lat1,lat2,...&longitude=lon1,lon2,...
    Response: { "elevation": [m1, m2, ...] }

Sınırlar:
    - Free tier: 10k çağrı/gün, 600/dakika
    - Batch limit: pratikte ~100 koord/istek (URL query length güvenli alt sınır)
    - Latency: ~50ms

Cache:
    - Redis backed CacheManager (singleton)
    - Key: "elev:{lon:.4f}:{lat:.4f}" — 4 decimal ~ 11m hassasiyet (SRTM
      granularitesi 30m olduğu için fazla)
    - TTL: 30 gün (relief stabil, sadece tileset güncellemesi için reset)
"""

from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional, Sequence, Tuple

import httpx

from app.config import settings
from app.infrastructure.cache.cache_manager import CacheManager, get_cache_manager
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.retry import with_async_retry

logger = get_logger(__name__)

# Open-Meteo /v1/elevation single-request batch cap. Resmi limit yok; URL
# uzunluğu güvenli kalsın diye 100. Daha büyükse chunk'la.
_MAX_BATCH = 100
# 30 gün — relief sabit.
_CACHE_TTL_S = 30 * 24 * 3600
# Coordinate rounding precision (decimal places). 4 ≈ 11m; 5 ≈ 1.1m.
# SRTM granularitesi ~30m, dolayısıyla 4 yeterli — daha hassası cache miss
# oranını artırır.
_COORD_PRECISION = 4


class OpenMeteoElevationClient:
    """Batch elevation fetcher with Redis-backed cache."""

    def __init__(
        self,
        cache: Optional[CacheManager] = None,
        timeout_s: float = 15.0,
    ) -> None:
        self._cache = cache if cache is not None else get_cache_manager()
        self._timeout_s = timeout_s
        self.base_url = settings.OPEN_METEO_API_BASE_URL

    @staticmethod
    def _cache_key(lon: float, lat: float) -> str:
        return f"elev:{lon:.{_COORD_PRECISION}f}:{lat:.{_COORD_PRECISION}f}"

    @staticmethod
    def _round_coord(lon: float, lat: float) -> Tuple[float, float]:
        return round(lon, _COORD_PRECISION), round(lat, _COORD_PRECISION)

    async def get_elevations(
        self, coords: Sequence[Tuple[float, float]]
    ) -> List[Optional[float]]:
        """Verilen (lon, lat) listesine elevation (m).

        Sırayı korur. Cache hit'leri network'ten geçmez. Cache miss'ler tek
        veya birkaç batch HTTP request'le çekilir. API hatası halinde:
        cache'deki değerler korunur, miss olanlar None döner.
        """
        if not coords:
            return []

        # 1) Cache lookup pass — sıralı sonuç slot'larını dolduralım.
        result: List[Optional[float]] = [None] * len(coords)
        miss_indices: List[int] = []
        miss_coords: List[Tuple[float, float]] = []
        for i, (lon, lat) in enumerate(coords):
            r_lon, r_lat = self._round_coord(lon, lat)
            cached = self._cache.get(self._cache_key(r_lon, r_lat))
            if cached is not None:
                result[i] = float(cached)
            else:
                miss_indices.append(i)
                miss_coords.append((r_lon, r_lat))

        if not miss_coords:
            return result

        # 2) Miss'leri batch'le fetch et. Aynı koord birden fazla geliyorsa
        # tekilleştir → fewer API requests.
        unique_pairs: List[Tuple[float, float]] = []
        seen: dict[Tuple[float, float], int] = {}  # (lon, lat) → unique_pairs index
        for pair in miss_coords:
            if pair not in seen:
                seen[pair] = len(unique_pairs)
                unique_pairs.append(pair)

        try:
            fetched = await self._fetch_batched(unique_pairs)
        except Exception as exc:
            logger.warning("Open-Meteo elevation fetch failed: %s", exc)
            return result

        # 3) Cache'e yaz + result slot'larını doldur
        for pair, elev in zip(unique_pairs, fetched):
            if elev is None:
                continue
            try:
                self._cache.set(
                    self._cache_key(pair[0], pair[1]), elev, ttl_seconds=_CACHE_TTL_S
                )
            except Exception as cache_exc:
                logger.debug("Cache set failed (non-fatal): %s", cache_exc)

        for idx, pair in zip(miss_indices, miss_coords):
            uniq_idx = seen[pair]
            result[idx] = fetched[uniq_idx]
        return result

    async def _fetch_batched(
        self, pairs: Iterable[Tuple[float, float]]
    ) -> List[Optional[float]]:
        """Open-Meteo'ya 100'erli chunk'larda istek atıp tüm değerleri döner."""
        pairs_list = list(pairs)
        if not pairs_list:
            return []

        out: List[Optional[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            for chunk_start in range(0, len(pairs_list), _MAX_BATCH):
                chunk = pairs_list[chunk_start : chunk_start + _MAX_BATCH]
                lats = ",".join(f"{lat}" for _, lat in chunk)
                lons = ",".join(f"{lon}" for lon, _ in chunk)

                async def _request_once() -> List[Optional[float]]:
                    resp = await client.get(
                        self.base_url,
                        params={"latitude": lats, "longitude": lons},
                    )
                    # 429 → dakikalık limit. Retry-After (saniye) varsa onu
                    # kullan, yoksa 1.5s; bir kez bekleyip tekrar dene.
                    # Free tier 600/dakika ama saturated minute'da hızla biter.
                    if resp.status_code == 429:
                        retry_after_hdr = resp.headers.get("Retry-After")
                        try:
                            delay = float(retry_after_hdr) if retry_after_hdr else 1.5
                        except ValueError:
                            delay = 1.5
                        delay = min(max(delay, 0.5), 5.0)
                        logger.warning(
                            "Open-Meteo elevation 429, retrying once after %.1fs (chunk=%d)",
                            delay,
                            len(chunk),
                        )
                        await asyncio.sleep(delay)
                        resp = await client.get(
                            self.base_url,
                            params={"latitude": lats, "longitude": lons},
                        )
                    if resp.status_code >= 500:
                        # Transient: retry tetikle
                        raise httpx.HTTPStatusError(
                            f"Open-Meteo 5xx: {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    if resp.status_code != 200:
                        # 4xx (429 sonrası hala fail veya başka bir 4xx) — retry boşa
                        logger.warning(
                            "Open-Meteo non-200 (%d): %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        from app.infrastructure.monitoring.silent_fallback_probe import (
                            record_silent_fallback,
                        )

                        record_silent_fallback(
                            "open_meteo_elevation_failed",
                            status_code=resp.status_code,
                        )
                        return [None] * len(chunk)

                    body = resp.json()
                    elev = body.get("elevation") or []
                    if not isinstance(elev, list) or len(elev) != len(chunk):
                        logger.warning(
                            "Open-Meteo unexpected shape: expected %d, got %d",
                            len(chunk),
                            len(elev) if isinstance(elev, list) else -1,
                        )
                        return [None] * len(chunk)

                    parsed: List[Optional[float]] = []
                    for e in elev:
                        try:
                            parsed.append(float(e) if e is not None else None)
                        except (TypeError, ValueError):
                            parsed.append(None)
                    return parsed

                try:
                    # Phase 2.4: 3 deneme exponential backoff
                    chunk_result = await with_async_retry(
                        _request_once,
                        max_attempts=3,
                        base_delay_s=0.5,
                        backoff_factor=2.0,
                        retry_on=(
                            httpx.RequestError,
                            httpx.HTTPStatusError,
                            ConnectionError,
                        ),
                        label="open_meteo.elevation",
                    )
                    out.extend(chunk_result)
                except Exception as exc:
                    logger.warning(
                        "Open-Meteo HTTP error (chunk %d) after retries: %s",
                        chunk_start,
                        exc,
                    )
                    out.extend([None] * len(chunk))
        return out


_default_client: Optional[OpenMeteoElevationClient] = None


def get_elevation_client() -> OpenMeteoElevationClient:
    """Singleton client (lazy)."""
    global _default_client
    if _default_client is None:
        _default_client = OpenMeteoElevationClient()
    return _default_client


__all__ = ["OpenMeteoElevationClient", "get_elevation_client"]
