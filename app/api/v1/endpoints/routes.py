from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep, get_current_active_user
from app.core.services.route_simulator import (
    RouteSimulator,
    get_route_simulator,
)
from app.database.models import Kullanici, Lokasyon, RouteSegment, RouteSimulation
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.api_responses import RouteAnalysisResponse
from app.services.route_service import RouteService

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
    service = RouteService()

    start_coords = (request.start_lon, request.start_lat)
    end_coords = (request.end_lon, request.end_lat)
    result = await service.get_route_details(start_coords, end_coords)

    if "error" in result:
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Route provider is currently unavailable."),
        )

    result["difficulty"] = service.analyze_route_difficulty(
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
    cikis_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Çıkış enlemi (lokasyon_id yoksa zorunlu)"
    )
    cikis_lon: Optional[float] = Field(None, ge=-180, le=180)
    varis_lat: Optional[float] = Field(None, ge=-90, le=90)
    varis_lon: Optional[float] = Field(None, ge=-180, le=180)
    ton: float = Field(15.0, ge=0, le=60, description="Yük (ton); 0 boş sefer")
    arac_yasi: int = Field(5, ge=0, le=40, description="Araç yaşı (gravity recovery)")
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
    # Phase 3.5 — lokasyon_id verildiyse SADECE koordinatlar lokasyondan
    # alınır; simülasyon HER ZAMAN simulate() üzerinden gider. Mapbox 24h
    # cache + Open-Meteo 30 gün cache zaten ucuz; her sefer GÜNCEL trafik.
    if request.lokasyon_id is not None:
        lokasyon = (
            await db.execute(select(Lokasyon).where(Lokasyon.id == request.lokasyon_id))
        ).scalar_one_or_none()
        if lokasyon is None:
            raise HTTPException(status_code=404, detail="Güzergah bulunamadı")
        if (
            lokasyon.cikis_lat is None
            or lokasyon.cikis_lon is None
            or lokasyon.varis_lat is None
            or lokasyon.varis_lon is None
        ):
            raise HTTPException(
                status_code=422,
                detail="Güzergah koordinatları eksik (cikis/varis lat-lon)",
            )
        used_cikis_lon = lokasyon.cikis_lon
        used_cikis_lat = lokasyon.cikis_lat
        used_varis_lon = lokasyon.varis_lon
        used_varis_lat = lokasyon.varis_lat
    else:
        if (
            request.cikis_lon is None
            or request.cikis_lat is None
            or request.varis_lon is None
            or request.varis_lat is None
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "cikis_lon/lat ve varis_lon/lat zorunlu (lokasyon_id verilmediyse)."
                ),
            )
        used_cikis_lon = request.cikis_lon
        used_cikis_lat = request.cikis_lat
        used_varis_lon = request.varis_lon
        used_varis_lat = request.varis_lat

    used_target_km = request.segment_length_m / 1000.0
    result = await simulator.simulate(
        cikis_lon=used_cikis_lon,
        cikis_lat=used_cikis_lat,
        varis_lon=used_varis_lon,
        varis_lat=used_varis_lat,
        ton=request.ton,
        arac_yasi=request.arac_yasi,
        target_length_km=used_target_km,
    )

    if result is None:
        raise HTTPException(
            status_code=502, detail="Routing provider (Mapbox) unavailable"
        )

    summary = result.summary

    # Persist
    sim = RouteSimulation(
        kullanici_id=getattr(current_user, "id", None) or None,
        lokasyon_id=request.lokasyon_id,
        cikis_lon=used_cikis_lon,
        cikis_lat=used_cikis_lat,
        varis_lon=used_varis_lon,
        varis_lat=used_varis_lat,
        ton=request.ton,
        arac_yasi=request.arac_yasi,
        target_length_km=used_target_km,
        raw_segment_count=result.raw_segment_count,
        resampled_segment_count=result.resampled_segment_count,
        elevation_coverage_pct=result.elevation_coverage_pct,
        total_km=summary.total_km,
        total_l=summary.total_l,
        avg_l_per_100km=summary.avg_l_per_100km,
        total_eta_sec=summary.total_eta_sec,
        total_ascent_m=summary.total_ascent_m,
        total_descent_m=summary.total_descent_m,
    )
    boundary = result.boundary_coords
    for i, s in enumerate(summary.segments):
        # bucket midpoint: boundary[i] ile boundary[i+1] ortası
        mid_lon: Optional[float] = None
        mid_lat: Optional[float] = None
        if i + 1 < len(boundary):
            mid_lon = (boundary[i][0] + boundary[i + 1][0]) / 2.0
            mid_lat = (boundary[i][1] + boundary[i + 1][1]) / 2.0
        sim.segments.append(
            RouteSegment(
                seq=i,
                length_km=s.length_km,
                grade_pct=s.grade_pct,
                road_class=s.road_class or None,
                maxspeed_kmh=s.maxspeed_kmh,
                traffic_speed_kmh=s.traffic_speed_kmh,
                congestion=s.congestion,
                sim_speed_kmh=s.sim_speed_kmh,
                sim_l_per_100km=s.sim_l_per_100km,
                sim_l_total=s.sim_l_total,
                eta_sec=s.eta_sec,
                mid_lon=mid_lon,
                mid_lat=mid_lat,
            )
        )
    # maxspeed/traffic/congestion artık SegmentOutput'tan persist ediliyor
    # (2026-06-14 Task 6; eski "kayboluyor" durumu giderildi).

    db.add(sim)
    await db.commit()
    await db.refresh(sim)
    # Re-load with segments EAGERLY (selectinload): a lazy relationship access
    # like `sim.segments` raises sqlalchemy MissingGreenlet under the async
    # engine (IO outside the greenlet) → was 500 on every simulation.
    sim = (
        await db.execute(
            select(RouteSimulation)
            .where(RouteSimulation.id == sim.id)
            .options(selectinload(RouteSimulation.segments))
        )
    ).scalar_one()
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
    sim = (
        await db.execute(
            select(RouteSimulation)
            .where(RouteSimulation.id == simulation_id)
            .options(selectinload(RouteSimulation.segments))
        )
    ).scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return _serialize_simulation(sim, list(sim.segments))
