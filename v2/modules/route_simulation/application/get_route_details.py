"""Use-case: fetch route details from cache or provider (ORS, Mapbox hybrid fallback).

Production rule: provider failures must surface as provider failures. The
service must not fabricate route geometry, road-class breakdowns, or segment
analysis when live routing is unavailable.

NOT (cross-module, geçici): ``RouteValidator`` (route_validator.py) henüz
v2'ye taşınmadı — eski yoldan import ediliyor, dokümante edilmiş geçici
bağımlılık. ``get_prediction_service`` (prediction_ml) 2026-07-18'de
``v2.modules.prediction_ml.public`` üzerinden erişecek şekilde güncellendi.
"""

import os
from typing import Dict, Optional, Tuple

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.circuit_breaker import (
    CircuitBreakerError,
    CircuitBreakerRegistry,
)
from v2.modules.route_simulation.application.get_route_difficulty import (
    get_route_difficulty,
)
from v2.modules.route_simulation.domain.route_analyzer import route_analyzer
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient
from v2.modules.shared_kernel.infrastructure.unit_of_work import unit_of_work as get_uow

logger = get_logger(__name__)


class _ORSProviderError(Exception):
    """ORS 5xx — circuit breaker'ın failure sayması için fırlatılır; dış handler'da
    'internal_error' yerine 'provider_error' olarak etiketlenmesini sağlar."""

    def __init__(self, status: int):
        self.status = status
        super().__init__(f"ORS server error {status}")


def _env_api_key() -> Optional[str]:
    return (
        os.getenv("OPENROUTESERVICE_API_KEY")
        or settings.OPENROUTESERVICE_API_KEY
        or os.getenv("OPENROUTE_API_KEY")
    )


async def _resolve_api_key() -> Optional[str]:
    """DB-configured key (admin UI) takes priority over the .env fallback —
    see v2.modules.admin_platform.public. Re-resolved on every call so
    an admin-entered key takes effect without a restart."""
    from v2.modules.admin_platform.public import (
        get_integration_secret,
    )

    return await get_integration_secret("openroute", _env_api_key())


async def get_route_details(
    start_coords: Tuple[float, float],
    end_coords: Tuple[float, float],
    use_cache: bool = True,
    include_details: bool = False,
) -> Dict:
    """
    Return route details from cache or provider.

    Returns an error payload with `error_code` when provider access fails.
    """
    from app.core.services.route_validator import RouteValidator

    lon1, lat1 = start_coords
    lon2, lat2 = end_coords
    base_url = settings.OPENROUTE_API_BASE_URL

    if use_cache:
        async with get_uow() as uow:
            cached = await uow.route_repo.get_by_coords(lat1, lon1, lat2, lon2)
            if cached:
                logger.info("Route cache hit.")
                result = {
                    "distance_km": cached["distance_km"],
                    "duration_min": cached["duration_min"],
                    "ascent_m": cached["ascent_m"],
                    "descent_m": cached["descent_m"],
                    "otoban_mesafe_km": cached.get("otoban_mesafe_km", 0.0),
                    "sehir_ici_mesafe_km": cached.get("sehir_ici_mesafe_km", 0.0),
                    "flat_distance_km": cached.get("flat_distance_km", 0.0),
                    "geometry": cached["geometry"],
                    "fuel_estimate": cached.get("fuel_estimate_cache"),
                    "difficulty": cached.get("difficulty"),
                    "source": "cache",
                }
                if include_details:
                    result["route_analysis"] = cached.get("route_analysis")
                return RouteValidator.validate_and_correct(result)

    api_key = await _resolve_api_key()
    if not api_key:
        logger.warning("OpenRouteService API key is missing.")
        return {
            "error": "Routing provider credentials are missing.",
            "error_code": "SERVICE_UNAVAILABLE",
            "source": "configuration",
        }

    try:
        from v2.modules.route_simulation.infrastructure.external_service import (
            get_external_service,
        )

        ext_service = get_external_service()
        client = await ext_service._get_client()

        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        body = {
            "coordinates": [[lon1, lat1], [lon2, lat2]],
            "elevation": True,
            "extra_info": ["waycategory", "waytype", "steepness"],
            "preference": "recommended",
        }

        breaker = CircuitBreakerRegistry.get_sync("openroute")

        async def _fetch_ors():
            _url = f"{base_url}/directions/driving-hgv/geojson"
            r = await client.post(_url, json=body, headers=headers, timeout=15)
            if r.status_code == 403:
                logger.warning(
                    "ORS driving-hgv profile is unavailable, retrying with driving-car."
                )
                _url = f"{base_url}/directions/driving-car/geojson"
                body.pop("options", None)
                r = await client.post(_url, json=body, headers=headers, timeout=15)
            if r.status_code >= 500:
                raise _ORSProviderError(r.status_code)
            return r

        try:
            response = await breaker.call(_fetch_ors)
        except CircuitBreakerError:
            logger.warning(
                "Circuit breaker 'openroute' is OPEN (route_service). "
                "Skipping ORS call to prevent cascade hang."
            )
            return {
                "error": "Routing provider is temporarily unavailable (circuit open).",
                "error_code": "SERVICE_UNAVAILABLE",
                "source": "circuit_breaker",
            }
        except _ORSProviderError as pe:
            # 5xx breaker'ı tetikledi; bu bir sağlayıcı hatası → doğru etiketle.
            logger.error("ORS provider 5xx: status=%s", pe.status)
            return {
                "error": f"Routing provider request failed (HTTP {pe.status}).",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider_status": pe.status,
                "source": "provider_error",
            }

        if response.status_code == 403:
            logger.error(
                "ORS API key forbidden (403). Quota exceeded or key suspended. "
                "Check OPENROUTESERVICE_API_KEY in .env and verify quota at "
                "https://openrouteservice.org/dev/#/home"
            )
            return {
                "error": "Routing provider forbidden (403). Quota exceeded or key suspended.",
                "error_code": "QUOTA_EXCEEDED",
                "provider_status": 403,
                "source": "provider_error",
            }

        if response.status_code == 401:
            logger.error("ORS API key rejected (401). Check OPENROUTESERVICE_API_KEY.")
            return {
                "error": "Routing provider credentials rejected (401). Please check the API key.",
                "error_code": "AUTH_FAILURE",
                "provider_status": 401,
                "source": "provider_error",
            }

        if response.status_code != 200:
            logger.error(
                "Routing API error: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            return {
                "error": f"Routing provider request failed (HTTP {response.status_code}).",
                "error_code": "SERVICE_UNAVAILABLE",
                "provider_status": response.status_code,
                "source": "provider_error",
            }

        data = response.json()
        feature = data["features"][0]
        props = feature["properties"]
        geometry = feature["geometry"]
        summary = props["summary"]

        smoothing_factor = 0.6
        ascent = props.get("ascent", 0.0) * smoothing_factor
        descent = props.get("descent", 0.0) * smoothing_factor

        analysis_result = route_analyzer.analyze_segments(
            geometry["coordinates"],
            props.get("extras", {}),
            reference_distance_m=summary.get("distance", 0),
        )

        otoban_stats = analysis_result.get("highway", {"flat": 0, "up": 0, "down": 0})
        other_stats = analysis_result.get("other", {"flat": 0, "up": 0, "down": 0})

        otoban_km = sum(otoban_stats.values())
        sehir_ici_mesafe_km = sum(other_stats.values())
        flat_km = otoban_stats["flat"] + other_stats["flat"]

        result = {
            "distance_km": round(summary.get("distance", 0) / 1000, 2),
            "duration_min": round(summary.get("duration", 0) / 60, 0),
            "ascent_m": round(ascent, 1),
            "descent_m": round(descent, 1),
            "otoban_mesafe_km": round(otoban_km, 2),
            "sehir_ici_mesafe_km": round(sehir_ici_mesafe_km, 2),
            "flat_distance_km": round(flat_km, 2),
            "geometry": geometry,
            "source": "api",
            "route_analysis": analysis_result,
            "distributions": analysis_result.get("distributions"),
        }

        result = RouteValidator.validate_and_correct(result)

        if result.get("is_corrected") and settings.MAPBOX_API_KEY:
            logger.warning(
                "ORS anomaly detected (%s). Trying Mapbox hybrid fallback.",
                result.get("correction_reason"),
            )
            mapbox_client = MapboxClient()
            mb_result = None
            try:
                mb_result = await mapbox_client.get_route((lon1, lat1), (lon2, lat2))
            except Exception as mapbox_exc:
                logger.warning(
                    "Mapbox fallback failed, using corrected ORS route: %s",
                    mapbox_exc,
                )

            if mb_result:
                dist_delta = (
                    abs(mb_result["distance_km"] - result["distance_km"])
                    / max(result["distance_km"], 1)
                    * 100
                )
                dur_delta = (
                    abs(mb_result["duration_min"] - result["duration_min"])
                    / max(result["duration_min"], 1)
                    * 100
                )
                if (
                    dist_delta > settings.ROUTE_DIST_DELTA_FAIL_PCT
                    or dur_delta > settings.ROUTE_DUR_DELTA_FAIL_PCT
                ):
                    logger.warning(
                        "Mapbox/ORS delta exceeds threshold: dist=%.1f%% dur=%.1f%%",
                        dist_delta,
                        dur_delta,
                    )
                elif (
                    dist_delta > settings.ROUTE_DIST_DELTA_WARN_PCT
                    or dur_delta > settings.ROUTE_DUR_DELTA_WARN_PCT
                ):
                    logger.info(
                        "Mapbox/ORS delta above warning level: dist=%.1f%% dur=%.1f%%",
                        dist_delta,
                        dur_delta,
                    )
                logger.info("Using Mapbox hybrid provider for this route.")
                result["distance_km"] = mb_result["distance_km"]
                result["duration_min"] = mb_result["duration_min"]
                result["otoban_mesafe_km"] = mb_result.get(
                    "otoban_mesafe_km", result.get("otoban_mesafe_km", 0.0)
                )
                result["sehir_ici_mesafe_km"] = mb_result.get(
                    "sehir_ici_mesafe_km", result.get("sehir_ici_mesafe_km", 0.0)
                )
                result["flat_distance_km"] = mb_result.get(
                    "flat_distance_km", result.get("flat_distance_km", 0.0)
                )
                if isinstance(mb_result.get("route_analysis"), dict):
                    result["route_analysis"] = mb_result["route_analysis"]
                result["geometry"] = mb_result["geometry"]
                result["source"] = "mapbox_hybrid"

        result["difficulty"] = get_route_difficulty(
            result["ascent_m"], result["descent_m"], result["distance_km"]
        )

        try:
            from v2.modules.prediction_ml.public import get_prediction_service

            pred_service = get_prediction_service()
            fuel_estimate = await pred_service.predict_consumption(
                arac_id=0,
                mesafe_km=result["distance_km"],
                ton=settings.DEFAULT_LOAD_TON,
                ascent_m=result["ascent_m"],
                flat_distance_km=result["flat_distance_km"],
                descent_m=result["descent_m"],
                route_analysis=result,
            )
            result["fuel_estimate"] = fuel_estimate
        except Exception as exc:
            logger.warning("Fuel estimate could not be attached to route: %s", exc)
            result["fuel_estimate"] = None

        async with get_uow() as uow:
            await uow.route_repo.save_route(
                {
                    "origin_lat": lat1,
                    "origin_lon": lon1,
                    "dest_lat": lat2,
                    "dest_lon": lon2,
                    "distance_km": result["distance_km"],
                    "duration_min": result["duration_min"],
                    "ascent_m": result["ascent_m"],
                    "descent_m": result["descent_m"],
                    "otoban_mesafe_km": result["otoban_mesafe_km"],
                    "sehir_ici_mesafe_km": result["sehir_ici_mesafe_km"],
                    "flat_distance_km": result["flat_distance_km"],
                    "geometry": result["geometry"],
                    "fuel_estimate_cache": result["fuel_estimate"],
                    "difficulty": result.get("difficulty"),
                    "route_analysis": result.get("route_analysis"),
                }
            )
            await uow.commit()

        logger.info("Route calculated via %s.", result["source"])
        return result

    except Exception as exc:
        logger.exception("Routing service error")
        return {
            "error": "Routing service execution failed.",
            "error_code": "SERVICE_UNAVAILABLE",
            "detail": str(exc),
            "source": "internal_error",
        }


__all__ = ["get_route_details"]
