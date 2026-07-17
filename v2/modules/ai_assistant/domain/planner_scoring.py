"""Feature C — sefer planlama sihirbazının saf skorlama kuralları.

DB/HTTP çağrısı yok — tamamen test edilebilir aritmetik + dataclass'lar.
`application/plan_trip.py::TripPlannerEngine` bu modülü orkestre eder.
Fonksiyon adları bilerek `_` önekli bırakıldı (orijinal
`app/core/ai/trip_planner.py`'deki private-helper adlarıyla birebir aynı —
`test_trip_planner_scoring.py`/`test_trip_planner_more.py` bu adları
doğrudan import ediyor, mekanik import-path taşıması dışında değişiklik
gerekmesin diye isimler korundu).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ── Sabitler ────────────────────────────────────────────────────────────
ARAC_WEIGHTS: Dict[str, float] = {
    "fuel": 0.40,
    "route_history": 0.25,
    "vehicle_health": 0.20,
    "availability": 0.15,
}
SOFOR_WEIGHTS: Dict[str, float] = {
    "route_type_perf": 0.50,
    "overall_hybrid": 0.30,
    "availability": 0.20,
}
SHORTLIST_SIZE = 10  # hard filter sonrası top-N aday
DEFAULT_TOP_N = 3  # UI'a dönen öneri sayısı
MAX_TOP_N = 5
DRIVER_PROFILE_DEV_NORM = 30  # |dev_pct| <= 30 → 0..1 normalize
VEHICLE_AGE_CAP = 25
AVAILABILITY_WINDOW_DAYS = 7
SIMILAR_ROUTE_PEAK = 5  # 5+ benzer sefer → route_history_score=1.0


# ── Veri sınıfları ──────────────────────────────────────────────────────
@dataclass
class PlanInput:
    """Wizard'a verilen kullanıcı girdisi."""

    cikis_yeri: str
    varis_yeri: str
    mesafe_km: float
    tarih: date
    ascent_m: float = 0.0
    descent_m: float = 0.0
    flat_distance_km: float = 0.0
    route_analysis: Optional[Dict[str, Any]] = None
    weight_kg: float = 0.0
    guzergah_id: Optional[int] = None


@dataclass
class VehicleCandidate:
    arac_id: int
    plaka: str
    yas: int
    score: float
    predicted_liters: float
    fuel_score: float
    route_history_score: float
    vehicle_health_score: float
    availability_score: float
    similar_trip_count: int
    cold_start: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class DriverCandidate:
    sofor_id: int
    ad_soyad: str
    score: float
    route_type_perf: float
    overall_hybrid: float
    availability_score: float
    route_type: str
    deviation_pct: float
    cold_start: bool
    reasons: List[str] = field(default_factory=list)


@dataclass
class PlanResult:
    weather_impact: float
    risk_label: str
    route_type: str
    vehicles: List[VehicleCandidate]
    drivers: List[DriverCandidate]
    generated_at: datetime
    cache_hit: bool = False


# ── Saf yardımcılar (test edilebilir, DB yok) ──────────────────────────
def _risk_label(impact: float) -> str:
    """Hava etki faktörünü etiketle. 1.0 = unknown (veri yok)."""
    if impact == 1.0:
        return "unknown"
    if impact > 1.10:
        return "high"
    if impact > 1.02:
        return "medium"
    return "low"


def _availability_score(recent_trips: int) -> float:
    """Son 7 günde N sefer → (7-N)/7. Az kullanıma öncelik."""
    if recent_trips < 0:
        recent_trips = 0
    ratio = (AVAILABILITY_WINDOW_DAYS - recent_trips) / AVAILABILITY_WINDOW_DAYS
    return max(0.0, min(1.0, ratio))


def _vehicle_age_years(v: Dict[str, Any]) -> int:
    """`yil` modelden okunur; eksikse 0."""
    yil = v.get("yil") or 0
    if yil <= 0:
        return 0
    return max(0, date.today().year - int(yil))


def _vehicle_health_score(age_years: int, has_open_alert: bool) -> float:
    """Yaş + bakım uyarısı kompoziti. Yaş cap=25."""
    age_part = 1.0 - min(age_years / VEHICLE_AGE_CAP, 1.0)
    alert_part = 0.5 if has_open_alert else 1.0
    return round(age_part * alert_part, 3)


def _route_type_perf(deviation_pct: float, trip_count: int) -> float:
    """Şoförün güzergah tipi performansı.

    Az veri (<5 sefer) → 0.5 nötr; aksi takdirde |sapma|/30 normalize.
    """
    if trip_count < 5:
        return 0.5
    return round(
        max(0.0, 1.0 - min(abs(deviation_pct) / DRIVER_PROFILE_DEV_NORM, 1.0)),
        3,
    )


def _vehicle_reasons(
    *,
    fuel_score: float,
    similar_trip_count: int,
    age_years: int,
    has_open_alert: bool,
    availability_score: float,
) -> List[str]:
    """C.5 — PII'siz, sayısal gerekçeler. Top-5 ile sınırlı."""
    out: List[str] = []
    if fuel_score >= 0.95:
        out.append("Aday seti içinde en düşük tahmini tüketim")
    elif fuel_score >= 0.7:
        out.append("Aday seti içinde düşük tahmini tüketim")
    if similar_trip_count >= 3:
        out.append(f"Bu güzergahta son 90 günde {similar_trip_count} benzer sefer")
    if age_years <= 3 and age_years > 0:
        out.append(f"Yeni araç ({age_years} yaş)")
    elif age_years >= 12:
        out.append(f"Eski araç ({age_years} yaş) — verim düşebilir")
    if has_open_alert:
        out.append("⚠ Açık bakım kaydı var")
    if availability_score < 0.3:
        out.append("⚠ Son haftada yoğun kullanım")
    elif availability_score >= 0.85:
        out.append("Müsait — son haftada az kullanım")
    return out[:5]


def _driver_reasons(
    *,
    route_type: str,
    deviation_pct: float,
    route_type_perf: float,
    overall_hybrid: float,
    availability_score: float,
    cold_start: bool,
) -> List[str]:
    """C.5 — şoför gerekçeleri. PII yok."""
    out: List[str] = []
    if cold_start:
        out.append("Yeni şoför — performans verisi yok")
    else:
        if route_type_perf >= 0.85 and deviation_pct < 0:
            out.append(f"Bu güzergah tipinde %{abs(deviation_pct):.1f} tasarruflu")
        elif route_type_perf >= 0.7:
            out.append("Bu güzergah tipinde tutarlı performans")
        elif route_type_perf < 0.4:
            out.append(f"Bu güzergah tipinde %{abs(deviation_pct):.1f} sapma — riskli")
        if overall_hybrid >= 0.8:
            out.append("Yüksek hibrit skor")
        elif overall_hybrid <= 0.4:
            out.append("⚠ Düşük hibrit skor")
    if availability_score < 0.3:
        out.append("⚠ Son haftada yoğun kullanım")
    elif availability_score >= 0.85:
        out.append("Müsait — son haftada az sefer")
    # route_type bilgisini görselleştirmek istersek UI yapsın; reasons salt sayısal
    return out[:5]
