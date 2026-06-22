import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, Tuple

import httpx

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.external_api_probe import get_monitored_client

logger = get_logger(__name__)


class ExternalService:
    """
    Runtime integrations for third-party services.

    Production rule: upstream failures must surface as failures. This class does
    not fabricate seasonal fallback payloads that could be mistaken for live
    weather data.
    """

    OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
    OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
    CB_FAILURE_THRESHOLD = 5
    CB_RECOVERY_TIMEOUT = 60

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cb_failure_count = 0
        self._cb_last_failure_time: Optional[datetime] = None
        self._cb_is_open = False
        self._cb_lock = asyncio.Lock()

    async def _check_circuit_breaker(self) -> bool:
        async with self._cb_lock:
            if not self._cb_is_open:
                return True

            if self._cb_last_failure_time:
                elapsed = (
                    datetime.now(timezone.utc) - self._cb_last_failure_time
                ).total_seconds()
                if elapsed >= self.CB_RECOVERY_TIMEOUT:
                    logger.info("Weather circuit breaker moved to half-open state.")
                    self._cb_is_open = False
                    self._cb_failure_count = 0
                    return True

            return False

    async def _record_success(self):
        async with self._cb_lock:
            self._cb_failure_count = 0
            self._cb_is_open = False

    async def _record_failure(self):
        async with self._cb_lock:
            self._cb_failure_count += 1
            self._cb_last_failure_time = datetime.now(timezone.utc)

            if self._cb_failure_count >= self.CB_FAILURE_THRESHOLD:
                self._cb_is_open = True
                logger.warning(
                    "Weather circuit breaker opened after %s consecutive failures.",
                    self.CB_FAILURE_THRESHOLD,
                )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = get_monitored_client(timeout=10.0)
        return self._client

    async def get_weather_forecast(self, lat: float, lon: float) -> Dict:
        """
        Fetch weather forecast data from Open-Meteo.

        Returns an error payload instead of a fabricated fallback when the
        provider is unavailable.
        """
        if not await self._check_circuit_breaker():
            logger.debug("Weather circuit breaker is open.")
            return {
                "error": "Weather provider is temporarily unavailable.",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo",
                "source": "circuit_breaker",
            }

        params: Dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
            "timezone": "auto",
        }

        try:
            client = await self._get_client()
            response = await client.get(self.OPENMETEO_URL, params=params)
            response.raise_for_status()
            await self._record_success()
            return response.json()
        except Exception as exc:
            await self._record_failure()
            logger.error("Weather forecast request failed: %s", exc)
            return {
                "error": "Weather provider request failed.",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo",
                "source": "provider_error",
            }

    # ── Phase 4.1 — Genişletilmiş hava sorguları ──────────────────────────

    async def get_weather_current_batch(
        self, coords: Sequence[Tuple[float, float]]
    ) -> Dict:
        """Birden çok koordinat için **current** hava + ``wind_direction_10m``.

        Open-Meteo batch desteği: ``latitude=lat1,lat2,...`` virgülle ayrılır.
        Response list döner (N koord için N item) veya tek koord için dict.

        Returns:
            { "data": [ {lat, lon, current: {...}}, ... ] } veya error payload.
        """
        if not coords:
            return {"data": []}

        if not await self._check_circuit_breaker():
            return {
                "error": "Weather provider is temporarily unavailable.",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo",
                "source": "circuit_breaker",
            }

        lats = ",".join(f"{lat}" for _, lat in coords)
        lons = ",".join(f"{lon}" for lon, _ in coords)
        params = {
            "latitude": lats,
            "longitude": lons,
            "current": (
                "temperature_2m,wind_speed_10m,wind_direction_10m,"
                "precipitation,snowfall"
            ),
            "timezone": "auto",
        }

        try:
            client = await self._get_client()
            response = await client.get(self.OPENMETEO_URL, params=params)
            # 429 → Retry-After header'ı varsa onu kullan, yoksa 1.5 sn bekle,
            # bir kez tekrar dene. Open-Meteo free-tier rate limit dar.
            if response.status_code == 429:
                retry_after_hdr = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after_hdr) if retry_after_hdr else 1.5
                except ValueError:
                    delay = 1.5
                delay = min(max(delay, 0.5), 5.0)
                logger.warning(
                    "Weather batch 429, retrying once after %.1fs (n_coords=%d)",
                    delay,
                    len(coords),
                )
                await asyncio.sleep(delay)
                response = await client.get(self.OPENMETEO_URL, params=params)
            response.raise_for_status()
            await self._record_success()
            body = response.json()
            # Open-Meteo batch endpoint birden fazla koord için **list** döner;
            # tek koord için dict. Normalize edip her zaman list döndürelim.
            items = body if isinstance(body, list) else [body]
            return {"data": items}
        except Exception as exc:
            await self._record_failure()
            logger.error("Weather current batch failed: %s", exc)
            return {
                "error": "Weather provider request failed.",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo",
                "source": "provider_error",
            }

    async def get_weather_archive(
        self, lat: float, lon: float, start_date: str, end_date: str
    ) -> Dict:
        """Geçmiş tarih için saatlik hava — archive-api endpoint.

        Args:
            start_date, end_date: ISO format ``YYYY-MM-DD``.

        Returns:
            { "hourly": {time, temperature_2m, wind_speed_10m,
                         wind_direction_10m, precipitation} } veya error.
        """
        if not await self._check_circuit_breaker():
            return {
                "error": "Weather archive unavailable (circuit open).",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo-archive",
            }

        params: Dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": (
                "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation"
            ),
            "timezone": "auto",
        }

        try:
            client = await self._get_client()
            response = await client.get(self.OPENMETEO_ARCHIVE_URL, params=params)
            response.raise_for_status()
            await self._record_success()
            return response.json()
        except Exception as exc:
            await self._record_failure()
            logger.error("Weather archive request failed: %s", exc)
            return {
                "error": "Weather archive request failed.",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider": "open-meteo-archive",
            }

    async def close(self):
        """Close the shared HTTP client during app shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("ExternalService client closed.")


_external_service: Optional[ExternalService] = None
_external_service_lock = threading.Lock()


def get_external_service() -> ExternalService:
    """Thread-safe singleton getter."""
    global _external_service
    if _external_service is None:
        with _external_service_lock:
            if _external_service is None:
                _external_service = ExternalService()
    return _external_service
