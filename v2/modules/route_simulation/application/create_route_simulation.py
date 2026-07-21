"""Use-case: 500m segment çözünürlüğünde rota simülasyonu + persist (Plan §6.1/6.2).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/route_routes.py::simulate_route``/
``get_route_simulation`` `application/` katmanını atlayıp ~90 satırlık ORM
persist/query mantığını doğrudan route içinde çalıştırıyordu. Mekanik
taşıma, davranış değişikliği yok — aynı sıra (lokasyon/araç çözümü →
simulate() → persist → eager-reload), aynı hata kodları (404/422/502).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Lokasyon, RouteSegment, RouteSimulation
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.prediction_ml.public import VehicleSpecs
from v2.modules.route_simulation.application.simulate_route import RouteSimulator
from v2.modules.route_simulation.infrastructure.simulation_repository import (
    SimulationRepository,
)


async def create_route_simulation(
    db: AsyncSession,
    simulator: RouteSimulator,
    *,
    lokasyon_id: Optional[int],
    arac_id: Optional[int],
    cikis_lon: Optional[float],
    cikis_lat: Optional[float],
    varis_lon: Optional[float],
    varis_lat: Optional[float],
    ton: float,
    arac_yasi: int,
    segment_length_m: int,
    current_user_id: Optional[int],
) -> RouteSimulation:
    """500m segment çözünürlüğünde rota simülasyonu (fizik + traffic).

    İki akış:
    1. lokasyon_id verilirse: hidrate edilmiş güzergahtan segment'ler
       yüklenir → simulate_route → Mapbox/Open-Meteo'ya HİÇ çağrı yok.
    2. lokasyon_id YOKSA: ad-hoc koordinatlarla Mapbox Directions →
       500m resample → Open-Meteo SRTM → simulate_route.

    Raises: 404 (lokasyon/araç bulunamadı), 422 (koordinat eksik),
    502 (Mapbox erişilemez).
    """
    # Phase 3.5 — lokasyon_id verildiyse SADECE koordinatlar lokasyondan
    # alınır; simülasyon HER ZAMAN simulate() üzerinden gider. Mapbox 24h
    # cache + Open-Meteo 30 gün cache zaten ucuz; her sefer GÜNCEL trafik.
    if lokasyon_id is not None:
        lokasyon = (
            await db.execute(select(Lokasyon).where(Lokasyon.id == lokasyon_id))
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
            cikis_lon is None
            or cikis_lat is None
            or varis_lon is None
            or varis_lat is None
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "cikis_lon/lat ve varis_lon/lat zorunlu (lokasyon_id verilmediyse)."
                ),
            )
        used_cikis_lon = cikis_lon
        used_cikis_lat = cikis_lat
        used_varis_lon = varis_lon
        used_varis_lat = varis_lat

    # Araç seçildiyse VehicleSpecs + arac_yasi araçtan türet
    vehicle: Optional[VehicleSpecs] = None
    used_arac_yasi = arac_yasi
    if arac_id is not None:
        arac = await db.get(Arac, arac_id)
        if arac is None:
            raise HTTPException(status_code=404, detail="Araç bulunamadı")
        vehicle = VehicleSpecs(
            empty_weight_kg=arac.bos_agirlik_kg,
            drag_coefficient=arac.hava_direnc_katsayisi,
            frontal_area_m2=arac.on_kesit_alani_m2,
            rolling_resistance=arac.lastik_direnc_katsayisi,
            engine_efficiency=arac.motor_verimliligi,
        )
        if arac.yil is not None:
            used_arac_yasi = date.today().year - arac.yil

    used_target_km = segment_length_m / 1000.0
    result = await simulator.simulate(
        cikis_lon=used_cikis_lon,
        cikis_lat=used_cikis_lat,
        varis_lon=used_varis_lon,
        varis_lat=used_varis_lat,
        ton=ton,
        arac_yasi=used_arac_yasi,
        target_length_km=used_target_km,
        vehicle=vehicle,
    )

    if result is None:
        raise HTTPException(
            status_code=502, detail="Routing provider (Mapbox) unavailable"
        )

    summary = result.summary

    sim = RouteSimulation(
        kullanici_id=current_user_id,
        lokasyon_id=lokasyon_id,
        arac_id=arac_id,
        cikis_lon=used_cikis_lon,
        cikis_lat=used_cikis_lat,
        varis_lon=used_varis_lon,
        varis_lat=used_varis_lat,
        ton=ton,
        arac_yasi=used_arac_yasi,
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
    segments = []
    for i, s in enumerate(summary.segments):
        # bucket midpoint: boundary[i] ile boundary[i+1] ortası
        mid_lon: Optional[float] = None
        mid_lat: Optional[float] = None
        if i + 1 < len(boundary):
            mid_lon = (boundary[i][0] + boundary[i + 1][0]) / 2.0
            mid_lat = (boundary[i][1] + boundary[i + 1][1]) / 2.0
        segments.append(
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

    repo = SimulationRepository(session=db)
    return await repo.create_with_segments(sim, segments)


async def get_route_simulation_by_id(
    db: AsyncSession, simulation_id: int
) -> RouteSimulation:
    """Persist edilmiş simülasyonu getirir (Plan §6.2). Raises 404."""
    repo = SimulationRepository(session=db)
    sim = await repo.get_by_id_with_segments(simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim
