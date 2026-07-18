"""Segment-mode fuel simulator (Phase 0.4 prototype).

Plan: docs/superpowers/plans/2026-05-29-route-segment-simulation-plan.md

Mevcut ``PhysicsBasedFuelPredictor``'ın fizik motorunu segment-level
input/output ile sarar — sefer-aggregate `predict()` arayüzü dokunulmaz
(paralel pipeline, mevcut tüm caller'lar etkilenmez).

Phase 0.4 kapsamı:
- Veri sınıfları: SegmentInput / SegmentOutput / SegmentSummary
- ``simulate_segment(seg, vehicle, ton, arac_yasi) → SegmentOutput``
- ``simulate_route(segments, vehicle, ton, arac_yasi) → SegmentSummary``

NOT (DB/endpoint yok): bu modül in-memory, salt fonksiyonel.

NOT (cross-module): ``PhysicsBasedFuelPredictor`` prediction_ml modülüne
ait — ``v2.modules.prediction_ml.public`` üzerinden import edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from v2.modules.prediction_ml.public import (
    FuelPrediction,
    PhysicsBasedFuelPredictor,
    VehicleSpecs,
)

# TIR güvenlik/yasal hız tavanları (Türkiye, road_class bazında).
# Phase 0.1 canlı sample'larda Mapbox `maxspeed` bazen "unknown" döner —
# bu durumda road_class cap'ini kullan.
_TIR_SPEED_CAPS_KMH: dict[str, float] = {
    "motorway": 90.0,
    "trunk": 85.0,
    "primary": 80.0,
    "secondary": 70.0,
    "tertiary": 60.0,
    "residential": 50.0,
    "street": 50.0,
    "service": 30.0,
    "": 60.0,  # fallback
}

# Mapbox congestion (low/moderate/heavy/severe) → speed multiplier.
# congestion_numeric daha granular ama bu wrapper basit kalsın; Phase 1'de
# numeric'e geçebilir.
_CONGESTION_SPEED_MULT: dict[str, float] = {
    "low": 1.00,
    "unknown": 1.00,
    "moderate": 0.80,
    "heavy": 0.55,
    "severe": 0.35,
}


@dataclass
class SegmentInput:
    """Tek segment için ham route + traffic + relief verisi.

    Tipik kaynak: Mapbox Directions annotation (distance/speed/maxspeed/
    congestion) + Open-Meteo elevation + reconcile'lı road_class.
    """

    length_km: float
    grade_pct: float  # -25..+25 typical
    road_class: str = ""  # motorway/trunk/primary/secondary/...
    maxspeed_kmh: Optional[float] = None  # None → unknown
    traffic_speed_kmh: Optional[float] = None  # Mapbox annotation.speed
    congestion: str = "low"  # low/moderate/heavy/severe/unknown


@dataclass
class SegmentOutput:
    """Bir segment'in simülasyon sonucu."""

    length_km: float
    sim_speed_kmh: float
    sim_l_per_100km: float
    sim_l_total: float
    eta_sec: float
    grade_pct: float
    road_class: str
    # Hız annotation'ları — persist + coverage gözlemi için taşınır.
    maxspeed_kmh: Optional[float] = None
    traffic_speed_kmh: Optional[float] = None
    congestion: str = "low"
    speed_source: str = "road_class"  # traffic | maxspeed | road_class


@dataclass
class SegmentSummary:
    """Bir route'un tüm segment toplamı."""

    total_km: float
    total_l: float
    avg_l_per_100km: float
    total_eta_sec: float
    total_ascent_m: float
    total_descent_m: float
    segments: List[SegmentOutput]


def _speed_source(seg: SegmentInput) -> str:
    """Hangi veri kaynağı sürüş hızını belirledi (coverage gözlemi)."""
    if seg.traffic_speed_kmh and seg.traffic_speed_kmh > 0:
        return "traffic"
    if seg.maxspeed_kmh and seg.maxspeed_kmh > 0:
        return "maxspeed"
    return "road_class"


def _effective_speed_kmh(seg: SegmentInput) -> float:
    """Segment için sürülecek pratik hız.

    Sıra:
      1. Mapbox `speed` annotation'ı (traffic-aware) — varsa
      2. maxspeed (yol kuralı) — varsa
      3. road_class cap'i (TIR tavanı, Türkiye)
      4. Congestion multiplier'ı (low/moderate/heavy/severe)

    Tüm bunların min'i alınır. Sonuç en az 5 km/h (dur-kalk'da bile bu
    floor; equilibrium hesabı zaten 18 km/h floor uyguluyor).
    """
    cap = _TIR_SPEED_CAPS_KMH.get(seg.road_class, _TIR_SPEED_CAPS_KMH[""])
    candidates: list[float] = [cap]
    if seg.maxspeed_kmh and seg.maxspeed_kmh > 0:
        # TIR maxspeed'i şehir/devlet yolu hız limitiyle eşle (otomobile
        # özel limit varsa TIR cap'ini geç).
        candidates.append(min(seg.maxspeed_kmh, cap))
    if seg.traffic_speed_kmh and seg.traffic_speed_kmh > 0:
        # Traffic speed Mapbox'ın gerçek hesaplaması — auto-includes congestion
        candidates.append(seg.traffic_speed_kmh)

    base = min(candidates)
    mult = _CONGESTION_SPEED_MULT.get(seg.congestion, 1.0)
    # Eğer traffic_speed zaten congestion'ı içeriyorsa (Mapbox driving-traffic
    # öyle yapar), congestion multiplier'ını tekrar uygulamak çift hesap olur.
    # Pratik kural: traffic_speed VARSA congestion multiplier'ını es geç.
    if seg.traffic_speed_kmh is None:
        base *= mult
    return max(5.0, base)


def simulate_segment(
    seg: SegmentInput,
    vehicle: Optional[VehicleSpecs] = None,
    ton: float = 15.0,
    arac_yasi: int = 5,
) -> SegmentOutput:
    """Tek bir segment için fiziksel yakıt simülasyonu.

    Args:
        seg: Segment verisi.
        vehicle: VehicleSpecs (None → default TIR).
        ton: Yük (boş sefer için 0).
        arac_yasi: Gravity recovery hesabı için araç yaşı.

    Returns:
        SegmentOutput — sim_speed/L_per_100km/L_total/eta.
    """
    if seg.length_km <= 0:
        return SegmentOutput(
            length_km=0.0,
            sim_speed_kmh=0.0,
            sim_l_per_100km=0.0,
            sim_l_total=0.0,
            eta_sec=0.0,
            grade_pct=seg.grade_pct,
            road_class=seg.road_class,
        )

    sim_speed_kmh = _effective_speed_kmh(seg)
    v_ms = sim_speed_kmh / 3.6
    dist_m = seg.length_km * 1000.0
    # grade_pct → delta_h: m × (grade/100)
    delta_h = dist_m * (seg.grade_pct / 100.0)

    predictor = PhysicsBasedFuelPredictor(vehicle or VehicleSpecs())
    result: FuelPrediction = predictor.predict_granular(
        segments=[(dist_m, v_ms, delta_h)],
        load_ton=ton,
        is_empty_trip=(ton <= 0),
        arac_yasi=arac_yasi,
        silent_outlier_log=True,
    )
    eta_sec = dist_m / v_ms if v_ms > 0 else 0.0
    return SegmentOutput(
        length_km=seg.length_km,
        sim_speed_kmh=sim_speed_kmh,
        sim_l_per_100km=result.consumption_l_100km,
        sim_l_total=result.total_liters,
        eta_sec=eta_sec,
        grade_pct=seg.grade_pct,
        road_class=seg.road_class,
        maxspeed_kmh=seg.maxspeed_kmh,
        traffic_speed_kmh=seg.traffic_speed_kmh,
        congestion=seg.congestion,
        speed_source=_speed_source(seg),
    )


def simulate_route(
    segments: Iterable[SegmentInput],
    vehicle: Optional[VehicleSpecs] = None,
    ton: float = 15.0,
    arac_yasi: int = 5,
) -> SegmentSummary:
    """Bir route'un tüm segmentlerini simüle et + toplam özet.

    NOT: Her segment için ayrı `predict_granular` çağrısı yapılır → tek-
    segment L/100km değeri segment-level UI için ayrı kullanılabilir.
    Performans için Phase 1'de batch versiyonu (tek çağrıda N segment)
    eklenebilir; mevcut `predict_granular` zaten tuple list alıyor.
    """
    segs_in = list(segments)
    if not segs_in:
        return SegmentSummary(
            total_km=0.0,
            total_l=0.0,
            avg_l_per_100km=0.0,
            total_eta_sec=0.0,
            total_ascent_m=0.0,
            total_descent_m=0.0,
            segments=[],
        )

    outputs: list[SegmentOutput] = []
    total_km = 0.0
    total_l = 0.0
    total_eta = 0.0
    total_ascent = 0.0
    total_descent = 0.0

    for s in segs_in:
        out = simulate_segment(s, vehicle=vehicle, ton=ton, arac_yasi=arac_yasi)
        outputs.append(out)
        total_km += out.length_km
        total_l += out.sim_l_total
        total_eta += out.eta_sec
        delta_h = out.length_km * 1000.0 * (out.grade_pct / 100.0)
        if delta_h > 0:
            total_ascent += delta_h
        else:
            total_descent += -delta_h

    avg = (total_l / total_km * 100.0) if total_km > 0 else 0.0
    return SegmentSummary(
        total_km=round(total_km, 3),
        total_l=round(total_l, 2),
        avg_l_per_100km=round(avg, 2),
        total_eta_sec=round(total_eta, 1),
        total_ascent_m=round(total_ascent, 1),
        total_descent_m=round(total_descent, 1),
        segments=outputs,
    )


__all__ = [
    "SegmentInput",
    "SegmentOutput",
    "SegmentSummary",
    "simulate_segment",
    "simulate_route",
]
