"""
Weather service for forecast lookups and fuel-impact analysis.

Production rule: if live weather data is unavailable, the service must surface
that fact instead of returning seasonal synthetic values as if they were real.
"""

import threading
from dataclasses import dataclass
from datetime import date as dt_date
from datetime import datetime as dt_datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.infrastructure.logging.logger import get_logger
from v2.modules.route_simulation.infrastructure.external_service import ExternalService

logger = get_logger(__name__)


@dataclass
class WeatherSample:
    """Phase 4.1 — tek koordinat için anlık hava verisi.

    Adjustment factors (P4.2) bu shape'i tüketir.
    """

    temperature_2m: Optional[float] = None  # °C
    wind_speed_10m: Optional[float] = None  # km/h
    wind_direction_10m: Optional[float] = None  # 0-360° (geldiği yön)
    precipitation: Optional[float] = None  # mm (current)
    snowfall: Optional[float] = None  # cm (current)


class WeatherService:
    """Weather-driven analysis service."""

    # Phase 4.1 — Redis cache key prefix, TTL 1 saat
    _WEATHER_CACHE_KEY_FMT = "weather:current:{lon:.2f}:{lat:.2f}"
    _WEATHER_CACHE_TTL_S = 3600  # 1 saat (hava saatlik güncellenir)

    def __init__(self, external_service: Optional[ExternalService] = None):
        self.external_service = external_service or ExternalService()
        # Daily forecast için eski in-memory cache (3h TTL korunur — legacy)
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 10800

    async def _get_cached_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        import time

        key = f"{round(lat, 2)}_{round(lon, 2)}"
        now = time.time()

        if key in self._cache:
            entry = self._cache[key]
            if now - entry["timestamp"] < self._cache_ttl:
                return entry["data"]

        result = await self.external_service.get_weather_forecast(lat, lon)
        if "error" not in result:
            self._cache[key] = {"timestamp": now, "data": result}

        return result

    # ── Phase 4.1 — Route-level current weather (batch, Redis cache) ─────

    async def get_route_weather_samples(
        self, midpoints: Sequence[Tuple[float, float]]
    ) -> List[Optional[WeatherSample]]:
        """Segment midpoint'leri için anlık hava verisi (batch, Redis cached).

        Cache miss olanlar tek batch HTTP çağrısıyla çekilir. Sırayı korur;
        provider hatası halinde miss'ler None döner (cache hit'ler korunur).
        """
        if not midpoints:
            return []

        from v2.modules.platform_infra.cache.cache_manager import get_cache_manager

        cache = get_cache_manager()
        result: List[Optional[WeatherSample]] = [None] * len(midpoints)
        miss_indices: List[int] = []
        miss_coords: List[Tuple[float, float]] = []

        # 1) Cache lookup
        for i, (lon, lat) in enumerate(midpoints):
            r_lon, r_lat = round(lon, 2), round(lat, 2)
            key = self._WEATHER_CACHE_KEY_FMT.format(lon=r_lon, lat=r_lat)
            try:
                cached = cache.get(key)
            except Exception as exc:
                logger.debug("Weather cache get failed (non-fatal): %s", exc)
                cached = None
            if isinstance(cached, WeatherSample):
                result[i] = cached
            else:
                miss_indices.append(i)
                miss_coords.append((r_lon, r_lat))

        if not miss_coords:
            return result

        # 2) Deduplicate (aynı round-coord birden fazlaysa tek API çağrısı)
        unique: List[Tuple[float, float]] = []
        seen: Dict[Tuple[float, float], int] = {}
        for pair in miss_coords:
            if pair not in seen:
                seen[pair] = len(unique)
                unique.append(pair)

        # 3) Batch fetch
        response = await self.external_service.get_weather_current_batch(unique)
        if "error" in response:
            logger.warning(
                "Weather batch unavailable; %d misses returned None",
                len(miss_indices),
            )
            return result

        # 4) Parse + cache + dağıt
        items = response.get("data") or []
        samples_by_pair: Dict[Tuple[float, float], WeatherSample] = {}
        for pair, item in zip(unique, items):
            current = (item or {}).get("current") or {}
            sample = WeatherSample(
                temperature_2m=current.get("temperature_2m"),
                wind_speed_10m=current.get("wind_speed_10m"),
                wind_direction_10m=current.get("wind_direction_10m"),
                precipitation=current.get("precipitation"),
                snowfall=current.get("snowfall"),
            )
            samples_by_pair[pair] = sample
            key = self._WEATHER_CACHE_KEY_FMT.format(lon=pair[0], lat=pair[1])
            try:
                cache.set(key, sample, ttl_seconds=self._WEATHER_CACHE_TTL_S)
            except Exception as exc:
                logger.debug("Weather cache set failed (non-fatal): %s", exc)

        for idx, pair in zip(miss_indices, miss_coords):
            result[idx] = samples_by_pair.get(pair)
        return result

    async def get_forecast_analysis(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch forecast data and derive a fuel-impact summary."""
        result = await self._get_cached_forecast(lat, lon)

        if "error" in result:
            logger.warning("Weather forecast unavailable: %s", result["error"])
            return self.get_forecast_analysis_offline(error=result)

        daily_data = result.get("daily", {})
        dates = daily_data.get("time", [])
        temps = daily_data.get("temperature_2m_max", [])
        precips = daily_data.get("precipitation_sum", [])
        winds = daily_data.get("wind_speed_10m_max", [])

        forecasts = []
        total_impact = 0.0

        for index, current_date in enumerate(dates[:7]):
            temp = temps[index] if index < len(temps) else 15.0
            precip = precips[index] if index < len(precips) else 0.0
            wind = winds[index] if index < len(winds) else 10.0

            impact = self.calculate_weather_fuel_impact(temp, precip, wind)
            total_impact += impact

            forecasts.append(
                {
                    "date": current_date,
                    "temperature_max": temp,
                    "precipitation_sum": precip,
                    "wind_speed_max": wind,
                    "impact_factor": round(impact, 3),
                }
            )

        avg_impact = total_impact / len(forecasts) if forecasts else 1.0
        recommendation = self.generate_weather_recommendation(avg_impact)

        return {
            "success": True,
            "daily": forecasts,
            "fuel_impact_factor": round(avg_impact, 3),
            "recommendation": recommendation,
            "offline": False,
        }

    def get_forecast_analysis_offline(
        self, error: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Return a truthful unavailable payload.

        The method name is preserved for compatibility, but it no longer fabricates
        seasonal forecast outputs.
        """
        return {
            "success": False,
            "daily": [],
            "fuel_impact_factor": None,
            "recommendation": "Canlı hava durumu verisi şu anda alınamıyor.",
            "offline": True,
            "error": (error or {}).get(
                "error", "Weather data is currently unavailable."
            ),
            "error_code": (error or {}).get("error_code", "SERVICE_UNAVAILABLE"),
        }

    async def get_trip_impact_analysis(
        self, cikis_lat: float, cikis_lon: float, varis_lat: float, varis_lon: float
    ) -> Dict[str, Any]:
        """Analyze live weather impact for a trip corridor."""
        import asyncio

        start_task = self._get_cached_forecast(cikis_lat, cikis_lon)
        end_task = self._get_cached_forecast(varis_lat, varis_lon)

        start_weather, end_weather = await asyncio.gather(start_task, end_task)

        if "error" in start_weather or "error" in end_weather:
            error_payload = start_weather if "error" in start_weather else end_weather
            logger.warning(
                "Trip weather impact unavailable because provider data is missing."
            )
            return {
                "success": False,
                "error": error_payload.get(
                    "error", "Weather data is currently unavailable."
                ),
                "error_code": error_payload.get("error_code", "SERVICE_UNAVAILABLE"),
            }

        start_daily = start_weather.get("daily", {})
        end_daily = end_weather.get("daily", {})

        avg_temp = (
            (start_daily.get("temperature_2m_max") or [20])[0]
            + (end_daily.get("temperature_2m_max") or [20])[0]
        ) / 2
        avg_precip = (
            (start_daily.get("precipitation_sum") or [0])[0]
            + (end_daily.get("precipitation_sum") or [0])[0]
        ) / 2
        avg_wind = (
            (start_daily.get("wind_speed_10m_max") or [10])[0]
            + (end_daily.get("wind_speed_10m_max") or [10])[0]
        ) / 2

        impact_factor = self.calculate_weather_fuel_impact(
            avg_temp, avg_precip, avg_wind
        )
        conditions = self._get_condition_warnings(avg_temp, avg_precip, avg_wind)

        return {
            "success": True,
            "weather_summary": {
                "avg_temperature": round(avg_temp, 1),
                "avg_precipitation": round(avg_precip, 1),
                "avg_wind_speed": round(avg_wind, 1),
            },
            "fuel_impact_factor": round(impact_factor, 3),
            "fuel_impact_percent": round((impact_factor - 1) * 100, 1),
            "conditions": conditions,
            "recommendation": self.generate_weather_recommendation(impact_factor),
        }

    def calculate_weather_fuel_impact(
        self, temp: float, precip: float, wind: float
    ) -> float:
        """Calculate a weather impact factor for fuel consumption."""
        impact = 1.0

        if temp < 0:
            impact += 0.08
        elif temp < 10:
            impact += 0.04
        elif temp > settings.WEATHER_TEMP_HIGH_THRESHOLD:
            impact += 0.05
        elif temp > 30:
            impact += 0.03

        if precip > 20:
            impact += 0.08
        elif precip > 10:
            impact += 0.05
        elif precip > 2:
            impact += 0.02

        if wind > settings.WEATHER_WIND_HIGH_THRESHOLD:
            impact += 0.15
        elif wind > 40:
            impact += 0.10
        elif wind > 25:
            impact += 0.05
        elif wind > 15:
            impact += 0.02

        return impact

    def generate_weather_recommendation(self, impact_factor: float) -> str:
        """Generate a user-facing Turkish recommendation for the impact factor."""
        if impact_factor < settings.WEATHER_IMPACT_MEDIUM:
            return "Hava koşulları normal. Standart plan uygulanabilir."
        if impact_factor < settings.WEATHER_IMPACT_HIGH:
            return "Orta seviye hava etkisi var. %5-10 esneklik payı önerilir."
        return "Olumsuz hava koşulları bekleniyor. Yakıt ve süre planını genişletin."

    def _get_condition_warnings(
        self, temp: float, precip: float, wind: float
    ) -> List[str]:
        """Return condition-specific warnings."""
        warnings = []
        if temp < 5:
            warnings.append(
                "Soğuk hava nedeniyle motor ısınma süresi ve rölanti tüketimi artabilir."
            )
        if precip > 5:
            warnings.append(
                "Yağışlı yol nedeniyle sürtünme direnci artabilir ve güvenlik riski oluşabilir."
            )
        if wind > 30:
            warnings.append(
                "Şiddetli rüzgar aerodinamik direnci belirgin şekilde artırabilir."
            )
        return warnings

    def get_seasonal_factor(self, target_date: Any) -> float:
        """
        Return a seasonal factor for model training and planning.

        This factor is a deterministic seasonal adjustment and is not presented
        to users as live weather truth.
        """
        target = target_date
        if isinstance(target, str):
            try:
                target = dt_date.fromisoformat(target)
            except ValueError:
                target = dt_date.today()
        elif not isinstance(target, (dt_date, dt_datetime)):
            target = dt_date.today()

        month = target.month
        if month in (12, 1, 2):
            raw = 1.10
        elif month in (3, 4, 10, 11):
            raw = 1.03
        elif month in (6, 7, 8):
            raw = 1.05
        else:
            raw = 1.0
        # Faz 7 — seasonal bir FALLBACK; gerçek soğuk weather_temperature
        # (<=1.20) ile yakalanır → fallback fiziksel cap (overfit'siz).
        return min(raw, settings.SEASONAL_FACTOR_MAX)


_weather_service: Optional[WeatherService] = None
_weather_service_lock = threading.Lock()


def get_weather_service() -> WeatherService:
    """Thread-safe singleton getter."""
    global _weather_service
    if _weather_service is None:
        with _weather_service_lock:
            if _weather_service is None:
                _weather_service = WeatherService()
    return _weather_service
