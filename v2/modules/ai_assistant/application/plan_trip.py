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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from v2.modules.ai_assistant.domain.planner_scoring import (
    ARAC_WEIGHTS,
    DEFAULT_TOP_N,
    MAX_TOP_N,
    SHORTLIST_SIZE,
    SIMILAR_ROUTE_PEAK,
    SOFOR_WEIGHTS,
    DriverCandidate,
    PlanInput,
    PlanResult,
    VehicleCandidate,
    _availability_score,
    _driver_reasons,
    _risk_label,
    _route_type_perf,
    _vehicle_age_years,
    _vehicle_health_score,
    _vehicle_reasons,
)
from v2.modules.driver.public import classify_route
from v2.modules.prediction_ml.public import find_similar_trips

logger = logging.getLogger(__name__)


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
        from v2.modules.driver.public import (
            get_route_profile_sofor,
            get_score_breakdown_sofor,
        )

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
                # get_score_breakdown_sofor().total → 0..100 (toplam manuel+auto)
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
