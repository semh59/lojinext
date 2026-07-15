from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, get_current_active_user
from app.database.models import Kullanici, RouteSegment, RouteSimulation
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.api_responses import RouteAnalysisResponse
from v2.modules.route_simulation.application.create_route_simulation import (
    create_route_simulation,
    get_route_simulation_by_id,
)
from v2.modules.route_simulation.application.get_route_details import (
    get_route_details,
)
from v2.modules.route_simulation.application.get_route_difficulty import (
    get_route_difficulty,
)
from v2.modules.route_simulation.application.simulate_route import (
    RouteSimulator,
    get_route_simulator,
)

router = APIRouter()


class RouteAnalysisRequest(BaseModel):
    start_lat: float = Field(..., ge=-90, le=90)
    start_lon: float = Field(..., ge=-180, le=180)
    end_lat: float = Field(..., ge=-90, le=90)
    end_lon: float = Field(..., ge=-180, le=180)


@router.post("/analyze", response_model=RouteAnalysisResponse)
async def analyze_route(
    request: RouteAnalysisRequest,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> RouteAnalysisResponse:
    start_coords = (request.start_lon, request.start_lat)
    end_coords = (request.end_lon, request.end_lat)
    result = await get_route_details(start_coords, end_coords)

    if "error" in result:
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Route provider is currently unavailable."),
        )

    result["difficulty"] = get_route_difficulty(
        result.get("ascent_m", 0),
        result.get("descent_m", 0),
        result.get("distance_km", 0),
    )
    return RouteAnalysisResponse.model_validate(result)


# -------------------------------------------------------------------------
# Route Segment Simulation (Phase 1.5)
# Plan: docs/superpowers/plans/2026-05-29-route-segment-simulation-plan.md
# Mapbox segments → 500m resample → Open-Meteo elevation → physics fuel
# simulation. In-memory; persist Phase 2'de.
# -------------------------------------------------------------------------


class RouteSimulateRequest(BaseModel):
    """Plan §6.1 request shape.

    Phase 3.3'ten itibaren: lokasyon_id verilirse koordinatlar opsiyonel
    (lokasyondan alınır + hidrate segment'ler kullanılır). Verilmezse
    mevcut ad-hoc akış — cikis/varis koordinatları zorunlu.
    """

    lokasyon_id: Optional[int] = Field(
        None,
        description="Kayıtlı güzergah ID. Verilirse cikis/varis koord opsiyonel.",
    )
    arac_id: Optional[int] = Field(
        None,
        description=(
            "Araç ID. Verilirse VehicleSpecs araç teknik değerlerinden türetilir;"
            " arac_yasi arac.yil'dan hesaplanır."
        ),
    )
    cikis_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Çıkış enlemi (lokasyon_id yoksa zorunlu)"
    )
    cikis_lon: Optional[float] = Field(None, ge=-180, le=180)
    varis_lat: Optional[float] = Field(None, ge=-90, le=90)
    varis_lon: Optional[float] = Field(None, ge=-180, le=180)
    ton: float = Field(15.0, ge=0, le=60, description="Yük (ton); 0 boş sefer")
    arac_yasi: int = Field(
        5,
        ge=0,
        le=40,
        description="Araç yaşı (gravity recovery); arac_id verilirse araç.yil'dan hesaplanır",
    )
    segment_length_m: int = Field(500, ge=100, le=5000, description="Bucket boyutu (m)")


class SegmentSimResponse(BaseModel):
    """Tek bucket simülasyon sonucu."""

    seq: int
    length_km: float
    grade_pct: float
    road_class: str
    sim_speed_kmh: float
    sim_l_per_100km: float
    sim_l_total: float
    eta_sec: float
    # Coğrafi konum (SVG heatmap için) + hız annotation kaynakları.
    mid_lon: Optional[float] = None
    mid_lat: Optional[float] = None
    maxspeed_kmh: Optional[float] = None
    traffic_speed_kmh: Optional[float] = None
    congestion: str = "low"
    speed_source: str = "road_class"


class SimulationSummaryResponse(BaseModel):
    """Plan §6.1 response summary."""

    distance_km: float
    duration_min: float
    total_l: float
    avg_l_per_100km: float
    total_ascent_m: float
    total_descent_m: float


class RouteSimulateResponse(BaseModel):
    """Plan §6.1 response. Phase 2.2'den itibaren simulation_id ile persist."""

    simulation_id: int
    created_at: datetime
    summary: SimulationSummaryResponse
    segments: List[SegmentSimResponse]
    raw_segment_count: int
    resampled_segment_count: int
    elevation_coverage_pct: float
    meta: dict


def _serialize_simulation(
    sim: RouteSimulation, segments: List[RouteSegment]
) -> RouteSimulateResponse:
    """ORM → response shape ortak helper (POST + GET)."""
    return RouteSimulateResponse(
        simulation_id=sim.id,
        created_at=sim.created_at,
        summary=SimulationSummaryResponse(
            distance_km=sim.total_km,
            duration_min=round(sim.total_eta_sec / 60.0, 1),
            total_l=sim.total_l,
            avg_l_per_100km=sim.avg_l_per_100km,
            total_ascent_m=sim.total_ascent_m,
            total_descent_m=sim.total_descent_m,
        ),
        segments=[
            SegmentSimResponse(
                seq=s.seq,
                length_km=round(s.length_km, 3),
                grade_pct=round(s.grade_pct, 2),
                road_class=s.road_class or "",
                sim_speed_kmh=round(s.sim_speed_kmh, 1),
                sim_l_per_100km=round(s.sim_l_per_100km, 2),
                sim_l_total=round(s.sim_l_total, 3),
                eta_sec=round(s.eta_sec, 1),
                mid_lon=s.mid_lon,
                mid_lat=s.mid_lat,
                maxspeed_kmh=s.maxspeed_kmh,
                traffic_speed_kmh=s.traffic_speed_kmh,
                congestion=s.congestion or "low",
                speed_source=(
                    "traffic"
                    if (s.traffic_speed_kmh or 0) > 0
                    else "maxspeed"
                    if (s.maxspeed_kmh or 0) > 0
                    else "road_class"
                ),
            )
            for s in segments
        ],
        raw_segment_count=sim.raw_segment_count,
        resampled_segment_count=sim.resampled_segment_count,
        elevation_coverage_pct=sim.elevation_coverage_pct,
        meta={
            "ton": sim.ton,
            "arac_yasi": sim.arac_yasi,
            "target_length_km": sim.target_length_km,
        },
    )


@router.post(
    "/simulate",
    response_model=RouteSimulateResponse,
    dependencies=[
        # Mapbox + Open-Meteo cost koruması: 10 req / dakika / IP
        Depends(RateLimiterDependency("route_simulate", rate=10.0, period=60.0)),
    ],
)
async def simulate_route(
    request: RouteSimulateRequest,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    simulator: Annotated[RouteSimulator, Depends(get_route_simulator)],
) -> RouteSimulateResponse:
    """500m segment çözünürlüğünde rota simülasyonu (fizik + traffic).

    İki akış:
    1. lokasyon_id verilirse: hidrate edilmiş güzergahtan segment'ler
       yüklenir → simulate_route → Mapbox/Open-Meteo'ya HİÇ çağrı yok.
    2. lokasyon_id YOKSA: ad-hoc koordinatlarla Mapbox Directions →
       500m resample → Open-Meteo SRTM → simulate_route.
    """
    sim = await create_route_simulation(
        db,
        simulator,
        lokasyon_id=request.lokasyon_id,
        arac_id=request.arac_id,
        cikis_lon=request.cikis_lon,
        cikis_lat=request.cikis_lat,
        varis_lon=request.varis_lon,
        varis_lat=request.varis_lat,
        ton=request.ton,
        arac_yasi=request.arac_yasi,
        segment_length_m=request.segment_length_m,
        current_user_id=getattr(current_user, "id", None) or None,
    )
    return _serialize_simulation(sim, list(sim.segments))


@router.get("/simulate/{simulation_id}", response_model=RouteSimulateResponse)
async def get_route_simulation(
    simulation_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> RouteSimulateResponse:
    """Persist edilmiş simülasyonu getirir (Plan §6.2).

    Cached simulation result — yeni Mapbox/Open-Meteo çağrısı yok.
    """
    sim = await get_route_simulation_by_id(db, simulation_id)
    return _serialize_simulation(sim, list(sim.segments))
