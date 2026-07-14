"""Feature C — Akıllı sefer planlama motoru.

Verilen güzergah + tarih + yük için top-N araç ve şoför adayı önerir.
Mevcut motorları (PredictionService.predict_consumption, route_similarity,
driver_route_profile, WeatherService.get_trip_impact_analysis) birleştirir;
yeni ML modeli eğitmez.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-c-trip-planner-wizard-v3.md
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.ml.route_similarity import find_similar_trips
from v2.modules.driver.domain.route_profile import classify_route

logger = logging.getLogger(__name__)


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


# ── Engine ─────────────────────────────────────────────────────────────
class TripPlannerEngine:
    """Stateless engine. Endpoint her istekte yeniden oluşturur."""

    def __init__(self, prediction_service) -> None:
        self.predictor = prediction_service

    async def plan(self, inp: PlanInput, top_n: int = DEFAULT_TOP_N) -> PlanResult:
        top_n = max(1, min(top_n, MAX_TOP_N))

        # Endpoint route_analysis vermediyse engine fetch eder (architecture
        # guard: endpoint katmanı DB'ye direkt erişmesin).
        if inp.route_analysis is None and inp.guzergah_id is not None:
            await self._fetch_route_analysis(inp)

        route_type = self._classify(inp)

        weather_task = asyncio.create_task(self._weather_impact(inp))
        vehicles_raw, drivers_raw = await self._shortlist(inp)
        weather_impact = await weather_task

        vehicles = await self._score_vehicles(vehicles_raw, inp)
        drivers = await self._score_drivers(drivers_raw, inp, route_type)

        vehicles.sort(key=lambda v: v.score, reverse=True)
        drivers.sort(key=lambda d: d.score, reverse=True)

        return PlanResult(
            weather_impact=weather_impact,
            risk_label=_risk_label(weather_impact),
            route_type=route_type,
            vehicles=vehicles[:top_n],
            drivers=drivers[:top_n],
            generated_at=datetime.now(timezone.utc),
        )

    async def _fetch_route_analysis(self, inp: PlanInput) -> None:
        """guzergah_id'den Lokasyon.route_analysis'i çek; inp'i in-place günceller."""
        from app.database.unit_of_work import UnitOfWork

        try:
            async with UnitOfWork() as uow:
                lok = await uow.lokasyon_repo.get_by_id(int(inp.guzergah_id))
            if lok and lok.get("route_analysis"):
                inp.route_analysis = lok["route_analysis"]
        except Exception as exc:
            logger.warning(
                "route_analysis fetch failed for guzergah %s: %s",
                inp.guzergah_id,
                exc,
            )

    # ── Aşama 1: route classification ──
    def _classify(self, inp: PlanInput) -> str:
        ra = inp.route_analysis or {
            "motorway": {"flat": inp.flat_distance_km},
            "ascent_m": inp.ascent_m,
            "descent_m": inp.descent_m,
        }
        try:
            return classify_route(ra)
        except Exception as exc:
            logger.warning("classify_route failed in planner: %s", exc)
            return "mixed"

    # ── Aşama 2: weather ──
    async def _weather_impact(self, inp: PlanInput) -> float:
        if not inp.guzergah_id:
            return 1.0
        try:
            from app.core.container import get_container
            from app.database.unit_of_work import UnitOfWork
        except Exception:  # pragma: no cover
            return 1.0
        try:
            async with UnitOfWork() as uow:
                route = await uow.lokasyon_repo.get_by_id(inp.guzergah_id)
            if not route:
                return 1.0
            cikis_lat = route.get("cikis_lat")
            cikis_lon = route.get("cikis_lon")
            varis_lat = route.get("varis_lat")
            varis_lon = route.get("varis_lon")
            if None in (cikis_lat, cikis_lon, varis_lat, varis_lon):
                return 1.0
            svc = get_container().weather_service
            result = await svc.get_trip_impact_analysis(
                cikis_lat, cikis_lon, varis_lat, varis_lon
            )
            if not result.get("success"):
                return 1.0
            return float(result.get("fuel_impact_factor") or 1.0)
        except Exception as exc:
            logger.warning("Weather fetch failed for planner: %s", exc)
            return 1.0

    # ── Aşama 3: aday shortlist ──
    async def _shortlist(self, inp: PlanInput):
        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            vehicles = await uow.arac_repo.get_eligible_for_planning(
                trip_date=inp.tarih, limit=SHORTLIST_SIZE
            )
            drivers = await uow.sofor_repo.get_eligible_for_planning(
                trip_date=inp.tarih, limit=SHORTLIST_SIZE
            )
        return vehicles, drivers

    # ── Aşama 4a: araç skorlama ──
    async def _score_vehicles(
        self,
        vehicles: List[Dict[str, Any]],
        inp: PlanInput,
    ) -> List[VehicleCandidate]:
        if not vehicles:
            return []

        async def _predict(v: Dict[str, Any]) -> Dict[str, Any]:
            try:
                return await self.predictor.predict_consumption(
                    arac_id=int(v["id"]),
                    mesafe_km=inp.mesafe_km,
                    ton=inp.weight_kg / 1000.0,
                    ascent_m=inp.ascent_m,
                    descent_m=inp.descent_m,
                    flat_distance_km=inp.flat_distance_km,
                    route_analysis=inp.route_analysis,
                    target_date=inp.tarih,
                    use_ensemble=True,
                )
            except Exception as exc:
                logger.warning(
                    "predict_consumption failed for arac %s: %s", v.get("id"), exc
                )
                return {"tahmini_litre": 0.0, "fallback_triggered": True}

        # Paralel tahmin + benzer sefer sayımı
        preds, sim_counts = await asyncio.gather(
            asyncio.gather(*[_predict(v) for v in vehicles]),
            asyncio.gather(*[self._count_similar(inp) for _ in vehicles]),
        )

        liters = [float(p.get("tahmini_litre") or 0.0) for p in preds]
        # NB: 0 değerleri normalize'ı bozmasın — yine de en az 1'lik spread garanti
        positive_liters = [v for v in liters if v > 0]
        if positive_liters:
            min_l = min(positive_liters)
            max_l = max(positive_liters)
        else:
            min_l = 0.0
            max_l = 0.0
        spread = (max_l - min_l) or 1.0

        out: List[VehicleCandidate] = []
        for v, pred, sim_count in zip(vehicles, preds, sim_counts):
            litres = float(pred.get("tahmini_litre") or 0.0)
            if litres <= 0:
                fuel_score = 0.0
            else:
                fuel_score = max(0.0, min(1.0, 1.0 - (litres - min_l) / spread))
            route_history_score = min(sim_count / SIMILAR_ROUTE_PEAK, 1.0)
            age = _vehicle_age_years(v)
            has_open_alert = bool(v.get("has_open_maintenance_alert"))
            health_score = _vehicle_health_score(age, has_open_alert)
            avail_score = _availability_score(int(v.get("recent_trip_count") or 0))

            score = (
                ARAC_WEIGHTS["fuel"] * fuel_score
                + ARAC_WEIGHTS["route_history"] * route_history_score
                + ARAC_WEIGHTS["vehicle_health"] * health_score
                + ARAC_WEIGHTS["availability"] * avail_score
            )

            reasons = _vehicle_reasons(
                fuel_score=fuel_score,
                similar_trip_count=sim_count,
                age_years=age,
                has_open_alert=has_open_alert,
                availability_score=avail_score,
            )

            out.append(
                VehicleCandidate(
                    arac_id=int(v["id"]),
                    plaka=str(v.get("plaka") or ""),
                    yas=age,
                    score=round(score, 3),
                    predicted_liters=round(litres, 1),
                    fuel_score=round(fuel_score, 3),
                    route_history_score=round(route_history_score, 3),
                    vehicle_health_score=health_score,
                    availability_score=round(avail_score, 3),
                    similar_trip_count=int(sim_count),
                    cold_start=(sim_count == 0),
                    reasons=reasons,
                )
            )
        return out

    async def _count_similar(self, inp: PlanInput) -> int:
        if not inp.route_analysis:
            return 0
        try:
            sims = await find_similar_trips(inp.route_analysis, inp.mesafe_km, limit=10)
            return len(sims)
        except Exception as exc:
            logger.warning("find_similar_trips failed: %s", exc)
            return 0

    # ── Aşama 4b: şoför skorlama ──
    async def _score_drivers(
        self,
        drivers: List[Dict[str, Any]],
        inp: PlanInput,
        route_type: str,
    ) -> List[DriverCandidate]:
        if not drivers:
            return []

        from app.database.unit_of_work import UnitOfWork
        from v2.modules.driver.application.get_route_profile import (
            get_route_profile_sofor,
        )
        from v2.modules.driver.application.get_score import get_score_breakdown_sofor

        out: List[DriverCandidate] = []
        async with UnitOfWork() as uow:
            for d in drivers:
                sofor_id = int(d["id"])
                try:
                    score_breakdown = await get_score_breakdown_sofor(sofor_id, uow=uow)
                except Exception as exc:
                    logger.warning(
                        "get_score_breakdown failed for %s: %s", sofor_id, exc
                    )
                    score_breakdown = {"total": 50.0, "has_trips": False}
                try:
                    route_profile = await get_route_profile_sofor(sofor_id, uow=uow)
                except Exception as exc:
                    logger.warning("get_route_profile failed for %s: %s", sofor_id, exc)
                    route_profile = {"profiles": []}

                profile_for_type: Optional[Dict[str, Any]] = next(
                    (
                        p
                        for p in route_profile.get("profiles", [])
                        if p.get("route_type") == route_type
                    ),
                    None,
                )
                cold_start = not bool(score_breakdown.get("has_trips"))
                if not profile_for_type:
                    deviation_pct = 0.0
                    trip_count = 0
                else:
                    deviation_pct = float(profile_for_type.get("deviation_pct", 0))
                    trip_count = int(profile_for_type.get("trip_count", 0))

                route_perf = _route_type_perf(deviation_pct, trip_count)
                # SoforService.get_score_breakdown.total → 0..100 (toplam manuel+auto)
                overall_hybrid = max(
                    0.0, min(1.0, float(score_breakdown.get("total") or 50.0) / 100.0)
                )
                avail_score = _availability_score(int(d.get("recent_trip_count") or 0))

                score = (
                    SOFOR_WEIGHTS["route_type_perf"] * route_perf
                    + SOFOR_WEIGHTS["overall_hybrid"] * overall_hybrid
                    + SOFOR_WEIGHTS["availability"] * avail_score
                )

                reasons = _driver_reasons(
                    route_type=route_type,
                    deviation_pct=deviation_pct,
                    route_type_perf=route_perf,
                    overall_hybrid=overall_hybrid,
                    availability_score=avail_score,
                    cold_start=cold_start,
                )

                out.append(
                    DriverCandidate(
                        sofor_id=sofor_id,
                        ad_soyad=str(d.get("ad_soyad") or ""),
                        score=round(score, 3),
                        route_type_perf=route_perf,
                        overall_hybrid=round(overall_hybrid, 3),
                        availability_score=round(avail_score, 3),
                        route_type=route_type,
                        deviation_pct=round(deviation_pct, 1),
                        cold_start=cold_start,
                        reasons=reasons,
                    )
                )
        return out
