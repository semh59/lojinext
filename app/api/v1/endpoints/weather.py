from datetime import date
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import (
    SessionDep,
    WeatherServiceDep,
    get_current_active_user,
    get_sefer_service,
)
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.route_simulation.schemas import (
    TripWeatherImpactResponse,
    WeatherDashboardResponse,
)
from v2.modules.trip.application.trip_service import SeferService
from v2.modules.trip.sefer_status import SEFER_STATUS_PLANLANDI

router = APIRouter()


class WeatherRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class WeatherForecast(BaseModel):
    date: str
    temperature_max: float
    precipitation_sum: float
    wind_speed_max: float
    impact_factor: float


class WeatherResponse(BaseModel):
    success: bool
    location: dict
    daily: List[WeatherForecast]
    fuel_impact_factor: Optional[float] = Field(
        None,
        description="Fuel consumption impact factor. 1.0 means neutral conditions.",
    )
    recommendation: str


class TripWeatherRequest(BaseModel):
    cikis_lat: float = Field(..., ge=-90, le=90)
    cikis_lon: float = Field(..., ge=-180, le=180)
    varis_lat: float = Field(..., ge=-90, le=90)
    varis_lon: float = Field(..., ge=-180, le=180)
    trip_date: Optional[str] = Field(None, description="Trip date (YYYY-MM-DD)")


@router.post("/forecast", response_model=WeatherResponse)
async def get_weather_forecast(
    request: WeatherRequest,
    service: WeatherServiceDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Return live weather forecast details for a coordinate pair."""
    result = await service.get_forecast_analysis(request.lat, request.lon)

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Weather data is currently unavailable."),
        )

    return WeatherResponse(
        success=True,
        location={"lat": request.lat, "lon": request.lon},
        daily=result["daily"],
        fuel_impact_factor=result["fuel_impact_factor"],
        recommendation=result["recommendation"],
    )


@router.post("/trip-impact", response_model=TripWeatherImpactResponse)
async def get_trip_weather_impact(
    request: TripWeatherRequest,
    service: WeatherServiceDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Return live weather impact for a trip corridor."""
    result = await service.get_trip_impact_analysis(
        request.cikis_lat, request.cikis_lon, request.varis_lat, request.varis_lon
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Weather data is currently unavailable."),
        )

    return result


@router.get("/dashboard-summary", response_model=WeatherDashboardResponse)
async def get_dashboard_weather_summary(
    service: WeatherServiceDep,
    db: SessionDep,
    sefer_service: Annotated[SeferService, Depends(get_sefer_service)],
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> dict[str, Any]:
    """Return dashboard weather risk summary for active trips."""
    import asyncio

    res_open = await sefer_service.get_all_paged(
        current_user=current_user,
        durum=SEFER_STATUS_PLANLANDI,
        baslangic_tarih=date.today().isoformat(),
        bitis_tarih=date.today().isoformat(),
        limit=50,
    )
    all_active = res_open["items"]

    summary: dict[str, Any] = {
        "total_active": len(all_active),
        "high_risk": 0,
        "medium_risk": 0,
        "normal": 0,
        "unavailable": 0,
        "details": [],
    }

    guzergah_ids = {trip.guzergah_id for trip in all_active if trip.guzergah_id}
    routes_map = {}
    if guzergah_ids:
        from v2.modules.location.public import get_lokasyon_repo

        lokasyon_repo = get_lokasyon_repo(db)
        all_routes = await lokasyon_repo.get_all(limit=1000)
        routes_map = {
            route["id"]: route for route in all_routes if route["id"] in guzergah_ids
        }

    async def analyze_trip(trip) -> dict[str, Any]:
        if trip.guzergah_id and trip.guzergah_id in routes_map:
            route = routes_map[trip.guzergah_id]
            c_lat = route.get("cikis_lat")
            v_lat = route.get("varis_lat")
            if c_lat and v_lat:
                return await service.get_trip_impact_analysis(
                    c_lat, route["cikis_lon"], v_lat, route["varis_lon"]
                )
        return {
            "success": False,
            "error_code": "PRECONDITION_NOT_MET",
            "error": "Trip route coordinates are missing.",
        }

    results = await asyncio.gather(
        *[analyze_trip(trip) for trip in all_active], return_exceptions=True
    )
    clean_results: list[dict[str, Any]] = [
        r
        if isinstance(r, dict)
        else {"success": False, "error": str(r), "error_code": "INTERNAL"}
        for r in results
    ]

    for trip, weather_result in zip(all_active, clean_results):
        if not weather_result.get("success"):
            summary["unavailable"] += 1
            summary["details"].append(
                {
                    "trip_id": trip.id,
                    "plaka": getattr(trip, "plaka", "Bilinmiyor"),
                    "risk": "Unavailable",
                    "error_code": weather_result.get("error_code"),
                }
            )
            continue

        impact = weather_result.get("fuel_impact_factor", 1.0)
        if impact > 1.10:
            summary["high_risk"] += 1
            summary["details"].append(
                {
                    "trip_id": trip.id,
                    "plaka": getattr(trip, "plaka", "Bilinmiyor"),
                    "risk": "High",
                    "impact": impact,
                }
            )
        elif impact > 1.02:
            summary["medium_risk"] += 1
        else:
            summary["normal"] += 1

    return summary
