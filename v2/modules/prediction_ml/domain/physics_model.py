"""Fizik motoru yardımcıları (predict_consumption'dan ayrıldı, dalga 13).

`_run_physics_fallback` bu kümeye dahil DEĞİL — task dosyası (prediction-ml.md
§5) onu buraya atıyordu ama gerçekte `response_builder`'daki
`build_prediction_response`/`build_explanation_summary`'yi çağırıyor;
domain/ katmanının application/'a bağımlı olması kök CLAUDE.md'nin katman
sırasını ihlal eder (domain saf/I/O-suz VE application'a bağımlı olmamalı).
Bu yüzden `_run_physics_fallback` `application/prediction_service.py`'de
kaldı — sadece gerçekten saf/I/O-suz 3 fonksiyon (`build_vehicle_specs`,
`run_physics_model`, `build_base_factors`) buraya taşındı.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Dict, Optional

from app.config import settings
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    FuelPrediction,
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)

logger = logging.getLogger(__name__)


def build_vehicle_specs(
    arac: Optional[Dict[str, Any]],
    dorse: Optional[Dict[str, Any]],
    age_degradation_rate: float,
) -> tuple[VehicleSpecs, int]:
    """
    Build VehicleSpecs and compute vehicle age from arac/dorse dicts.

    Returns ``(specs, age_years)``. Applies engine-efficiency degradation
    for vehicles older than 5 years, using ``age_degradation_rate``
    (resolved once per request at the async boundary by the caller —
    runtime_config.get_runtime_float("VEHICLE_AGE_DEGRADATION_RATE", ...)
    — never read from settings directly here, and never fetched per
    segment/call in this sync helper).
    """
    if not arac:
        return VehicleSpecs(), 0

    specs = VehicleSpecs(
        empty_weight_kg=arac.get("bos_agirlik_kg", 8000.0),
        drag_coefficient=arac.get("hava_direnc_katsayisi", 0.52),
        frontal_area_m2=arac.get("on_kesit_alani_m2", 8.5),
        engine_efficiency=arac.get("motor_verimliligi", 0.38),
        rolling_resistance=arac.get("lastik_direnc_katsayisi", 0.007),
    )
    if dorse:
        specs.trailer_empty_weight_kg = dorse.get("bos_agirlik_kg", 6500.0)
        specs.trailer_rolling_resistance = dorse.get(
            "dorse_lastik_direnc_katsayisi", 0.006
        )
        specs.trailer_drag_contribution = dorse.get("dorse_hava_direnci", 0.13)

    age = max(0, date.today().year - (arac.get("yil") or 2020))
    if age > 5:
        age_factor = max(
            1.0 - settings.MAX_AGE_DEGRADATION,
            1.0 - age * age_degradation_rate,
        )
        specs.engine_efficiency *= age_factor
    return specs, age


async def run_physics_model(
    specs: VehicleSpecs,
    age: int,
    mesafe_km: float,
    ton: float,
    ascent_m: float,
    descent_m: float,
    flat_distance_km: float,
    bos_sefer: bool,
    weather_factor: float,
    otoyol_ratio: float,
    devlet_yolu_ratio: float,
    sehir_ici_ratio: float,
    normalized_route: Optional[Dict[str, Any]],
) -> FuelPrediction:
    """
    Run physics-based fuel prediction (granular P2P or summary-route path).

    Returns the raw ``FuelPrediction`` object from the predictor.
    """
    predictor = PhysicsBasedFuelPredictor(specs)
    historical_stats = (
        normalized_route.get("historical_stats") if normalized_route else None
    )
    granular_nodes = normalized_route.get("granular_nodes") if normalized_route else None
    if granular_nodes:
        logger.info(f"Using High-Fidelity P2P Physics ({len(granular_nodes)} nodes)")
        return await asyncio.to_thread(
            predictor.predict_granular,
            granular_nodes,
            ton,
            bos_sefer,
            historical_stats=historical_stats,
            arac_yasi=age,
        )
    route = RouteConditions(
        distance_km=mesafe_km,
        load_ton=0.0 if bos_sefer else ton,
        is_empty_trip=bos_sefer,
        ascent_m=ascent_m,
        descent_m=descent_m,
        flat_distance_km=flat_distance_km,
        weather_factor=weather_factor,
        otoyol_ratio=otoyol_ratio,
        devlet_yolu_ratio=devlet_yolu_ratio,
        sehir_ici_ratio=sehir_ici_ratio,
        arac_yasi=age,
    )
    return await asyncio.to_thread(
        predictor.predict, route, historical_stats=historical_stats
    )


def build_base_factors(
    physics_l_100km: float,
    weather_factor: float,
    s_score: Optional[float],
    sofor_influence: float,
    ramp_factor: float,
    ton: float,
    ascent_m: float,
    descent_m: float,
    flat_distance_km: float,
    otoyol_ratio: float,
    devlet_yolu_ratio: float,
    sehir_ici_ratio: float,
    age: int,
    dorse_id: Optional[int],
    zorluk: str,
    bos_sefer: bool,
) -> Dict[str, Any]:
    """Assemble the base faktorler dict shared by all response paths."""
    return {
        "physics_base": round(physics_l_100km, 2),
        "weather_factor": round(weather_factor, 2),
        "sofor_score": round(float(s_score or 1.0), 2),
        "driver_factor": round(sofor_influence, 3),
        "ramp_factor": round(ramp_factor, 3),
        "load_ton": round(float(0.0 if bos_sefer else ton), 2),
        "ascent_m": round(float(ascent_m or 0.0), 1),
        "descent_m": round(float(descent_m or 0.0), 1),
        "flat_distance_km": round(float(flat_distance_km or 0.0), 2),
        "otoyol_ratio": round(float(otoyol_ratio), 3),
        "devlet_yolu_ratio": round(float(devlet_yolu_ratio), 3),
        "sehir_ici_ratio": round(float(sehir_ici_ratio), 3),
        "vehicle_age": age,
        "has_trailer": 1.0 if dorse_id else 0.0,
        "difficulty_level": zorluk,
    }


__all__ = ["build_vehicle_specs", "run_physics_model", "build_base_factors"]
