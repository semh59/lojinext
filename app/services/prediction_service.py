"""
TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: ML ensemble yakıt tahmini — model dosyaları başlangıçta bir kez yüklenir.
CREATED_BY: app/core/container.py (lazy property)
"""

import asyncio
import logging
from datetime import date
from typing import Any, Dict, Optional

from app.config import settings
from app.core.ml.ensemble_predictor import get_ensemble_service
from app.core.ml.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)
from app.core.services.weather_service import WeatherService
from app.core.services.yakit_tahmin_service import YakitTahminService
from app.core.utils.type_helpers import safe_float
from app.database.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

_bg_tasks: set[asyncio.Task] = set()


class PredictionService:
    """
    Yakıt Tahmin Servisi.
    Fizik motoru ve ML modellerini (Ensemble) orkestra eder.
    """

    def __init__(self):
        self.weather_service = WeatherService()
        self.yakit_tahmin_service = YakitTahminService()
        self.ensemble_service = get_ensemble_service()

    @staticmethod
    def _build_explanation_summary(
        model_used: str,
        model_version: str,
        confidence_score: float,
        load_ton: float,
        ascent_m: float,
        weather_factor: float,
    ) -> str:
        return (
            f"{model_used}/{model_version} ile tahmin yapildi. "
            f"Guven skoru: {confidence_score:.2f}. "
            f"Yuk: {load_ton:.1f} ton, tirmanis: {ascent_m:.0f} m, "
            f"hava etkisi: {weather_factor:.2f}."
        )

    @staticmethod
    def _normalize_confidence_band(
        base_value: float,
        confidence_score: float,
        confidence_low: Optional[float] = None,
        confidence_high: Optional[float] = None,
    ) -> tuple[float, float]:
        if confidence_low is not None and confidence_high is not None:
            return round(float(confidence_low), 2), round(float(confidence_high), 2)

        spread_ratio = max(0.06, min(0.30, 0.30 - (confidence_score * 0.2)))
        low = max(0.0, base_value * (1 - spread_ratio))
        high = base_value * (1 + spread_ratio)
        return round(low, 2), round(high, 2)

    @classmethod
    def _sum_segment_km(cls, segment: Any) -> float:
        if not isinstance(segment, dict):
            return 0.0
        total = 0.0
        for key in ("flat", "up", "down"):
            total += safe_float(segment.get(key)) or 0.0
        return total

    @classmethod
    def _derive_route_ratios(
        cls, route_analysis: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, float]]:
        if not isinstance(route_analysis, dict):
            return None

        existing = route_analysis.get("ratios")
        if isinstance(existing, dict):
            return {
                "otoyol": round(float(existing.get("otoyol", 0.0) or 0.0), 3),
                "devlet_yolu": round(float(existing.get("devlet_yolu", 0.0) or 0.0), 3),
                "sehir_ici": round(float(existing.get("sehir_ici", 0.0) or 0.0), 3),
            }

        motorway_km = cls._sum_segment_km(route_analysis.get("motorway"))
        trunk_km = cls._sum_segment_km(route_analysis.get("trunk"))
        primary_km = cls._sum_segment_km(route_analysis.get("primary"))
        residential_km = cls._sum_segment_km(route_analysis.get("residential"))
        unclassified_km = cls._sum_segment_km(route_analysis.get("unclassified"))
        other_km = cls._sum_segment_km(route_analysis.get("other"))
        highway_km = cls._sum_segment_km(route_analysis.get("highway"))

        if highway_km > 0 and (trunk_km + primary_km) == 0:
            trunk_km = highway_km

        total_km = (
            motorway_km
            + trunk_km
            + primary_km
            + residential_km
            + unclassified_km
            + other_km
        )
        if total_km <= 0:
            return None

        return {
            "otoyol": round(motorway_km / total_km, 3),
            "devlet_yolu": round((trunk_km + primary_km) / total_km, 3),
            "sehir_ici": round(
                (residential_km + unclassified_km + other_km) / total_km, 3
            ),
        }

    @classmethod
    def _normalize_route_analysis(
        cls, route_analysis: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(route_analysis, dict):
            return None

        normalized: Dict[str, Any] = {}
        nested = route_analysis.get("route_analysis")
        if isinstance(nested, dict):
            normalized.update(nested)

        for key in (
            "ratios",
            "weather_factor",
            "historical_stats",
            "granular_nodes",
            "distributions",
            "motorway",
            "trunk",
            "primary",
            "residential",
            "unclassified",
            "highway",
            "other",
        ):
            value = route_analysis.get(key)
            if value is not None and key not in normalized:
                normalized[key] = value

        ratios = cls._derive_route_ratios(normalized)
        if ratios is not None:
            normalized["ratios"] = ratios

        return normalized or None

    @classmethod
    def _extract_confidence_score(
        cls, ensemble_result: Optional[Dict[str, Any]]
    ) -> Optional[float]:
        if not isinstance(ensemble_result, dict):
            return None
        confidence = safe_float(ensemble_result.get("confidence_score"))
        if confidence is None:
            return None
        return max(0.0, min(1.0, confidence))

    async def _build_sefer_dict(
        self,
        *,
        arac: Dict[str, Any],
        sofor: Optional[Dict[str, Any]],
        dorse: Optional[Dict[str, Any]],
        mesafe_km: float,
        ton: float,
        ascent_m: float,
        descent_m: float,
        flat_distance_km: float,
        target_date: date,
        bos_sefer: bool,
        route_analysis: Optional[Dict[str, Any]],
        weather_factor: Optional[float],
    ) -> Dict[str, Any]:
        """
        Build the sefer feature dict from vehicle / driver / route data.

        Incorporates vehicle metadata, trailer info, driver coefficients, and
        all route/weather factors needed by the ensemble predictor.
        """
        return {
            "mesafe_km": mesafe_km,
            "ton": 0.0 if bos_sefer else ton,
            "ascent_m": ascent_m,
            "descent_m": descent_m,
            "flat_distance_km": flat_distance_km,
            "target_date": target_date,
            "bos_sefer": bos_sefer,
            "route_analysis": route_analysis,
            "weather_factor": weather_factor,
            # Vehicle metadata
            "marka": arac.get("marka"),
            "model": arac.get("model"),
            "yil": arac.get("yil"),
            "motor_hacmi": arac.get("motor_hacmi"),
            "euro_norm": arac.get("euro_norm"),
            # Driver / trailer IDs for ensemble feature engineering
            "sofor_id": sofor.get("id") if sofor else None,
            "sofor_katsayi": sofor.get("score", 1.0) if sofor else 1.0,
            "dorse_id": dorse.get("id") if dorse else None,
        }

    async def _run_ensemble_prediction(
        self,
        arac_id: int,
        sefer_dict: Dict[str, Any],
        target_date: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Call the ensemble service and return its raw result dict, or None on error.

        The caller is responsible for interpreting the success flag and confidence
        score. Exceptions are caught and logged so the caller can fall back safely.
        """
        try:
            async with UnitOfWork() as uow_ensemble:
                result = await self.ensemble_service.predict_consumption(
                    arac_id=arac_id,
                    mesafe_km=sefer_dict["mesafe_km"],
                    ton=sefer_dict["ton"],
                    sofor_id=sefer_dict.get("sofor_id"),
                    dorse_id=sefer_dict.get("dorse_id"),
                    ascent_m=sefer_dict.get("ascent_m", 0.0),
                    descent_m=sefer_dict.get("descent_m", 0.0),
                    target_date=target_date,
                    is_empty_trip=sefer_dict.get("bos_sefer", False),
                    uow=uow_ensemble,
                    route_analysis=sefer_dict.get("route_analysis"),
                )
            return result
        except Exception as e:
            logger.warning(f"Ensemble prediction failed: {e}")
            return None

    def _run_physics_fallback(
        self,
        arac: Dict[str, Any],
        sefer_dict: Dict[str, Any],
        mesafe_km: float,
    ) -> Dict[str, Any]:
        """
        Build and return the full prediction response for the physics-only fallback.

        Called when ensemble is disabled or its result was not successful.
        ``sefer_dict`` must contain ``_fallback_l_100km``, ``_use_ensemble``,
        ``_base_factors``, ``_physics_insight``, and route/load scalars used
        for the explanation summary.
        """
        use_ensemble: bool = sefer_dict.get("_use_ensemble", True)
        fallback_l_100km: float = sefer_dict["_fallback_l_100km"]
        base_factors: Dict[str, Any] = sefer_dict["_base_factors"]
        physics_insight: Optional[str] = sefer_dict.get("_physics_insight")

        fallback_confidence = 0.72 if not use_ensemble else 0.55
        fallback_warning = "GREEN" if fallback_confidence >= 0.60 else "YELLOW"
        fallback_model = "physics" if use_ensemble else "linear"
        fallback_version = "physics-v2.0"
        fallback_factors = {
            **base_factors,
            "ml_correction": 0.0,
            "fallback_reason": (
                "ensemble_unavailable_or_disabled"
                if use_ensemble
                else "physics_mode_selected"
            ),
        }
        fallback_summary = self._build_explanation_summary(
            model_used=fallback_model,
            model_version=fallback_version,
            confidence_score=fallback_confidence,
            load_ton=float(sefer_dict.get("ton", 0.0)),
            ascent_m=float(sefer_dict.get("ascent_m") or 0.0),
            weather_factor=float(sefer_dict.get("weather_factor") or 1.0),
        )
        return self._build_prediction_response(
            mesafe_km=mesafe_km,
            tahmini_tuketim=fallback_l_100km,
            model_used=fallback_model,
            model_version=fallback_version,
            confidence_score=fallback_confidence,
            warning_level=fallback_warning,
            fallback_triggered=bool(use_ensemble),
            faktorler=fallback_factors,
            insight=physics_insight,
            explanation_summary=fallback_summary,
        )

    @staticmethod
    def _build_base_factors(
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

    @staticmethod
    def _build_vehicle_specs(
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

    async def _run_physics_model(
        self,
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
    ) -> Any:
        """
        Run physics-based fuel prediction (granular P2P or summary-route path).

        Returns the raw ``PhysicsResult`` object from the predictor.
        """
        predictor = PhysicsBasedFuelPredictor(specs)
        historical_stats = (
            normalized_route.get("historical_stats") if normalized_route else None
        )
        granular_nodes = (
            normalized_route.get("granular_nodes") if normalized_route else None
        )
        if granular_nodes:
            logger.info(
                f"Using High-Fidelity P2P Physics ({len(granular_nodes)} nodes)"
            )
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

    def _process_ensemble_result(
        self,
        *,
        ensemble_result: Dict[str, Any],
        fallback_l_100km: float,
        mesafe_km: float,
        ton: float,
        ascent_m: float,
        bos_sefer: bool,
        weather_factor: float,
        base_factors: Dict[str, Any],
        physics_insight: Optional[str],
    ) -> Dict[str, Any]:
        """
        Evaluate ensemble confidence and return the final prediction response.

        Applies RED/YELLOW/GREEN confidence gating. If confidence is below the
        RED threshold the physics fallback value is used instead of the ML
        prediction, with ``fallback_triggered=True`` reflected in the response.
        """
        tahmin_l_100km: float = ensemble_result["tahmin_l_100km"]
        confidence = self._extract_confidence_score(ensemble_result)

        warning_level = "GREEN"
        fallback_triggered = False

        threshold_red = getattr(settings, "AI_CONFIDENCE_THRESHOLD_RED", 0.40)
        threshold_yellow = getattr(settings, "AI_CONFIDENCE_THRESHOLD_YELLOW", 0.60)

        if confidence is None:
            warning_level, confidence, tahmin_l_100km, fallback_triggered = (
                "RED",
                0.0,
                fallback_l_100km,
                True,
            )
            logger.warning(
                "Ensemble response missing confidence_score."
                " Physics fallback triggered."
            )
        elif confidence < threshold_red:
            warning_level, tahmin_l_100km, fallback_triggered = (
                "RED",
                fallback_l_100km,
                True,
            )
            logger.warning(
                f"AI Confidence RED ({confidence:.2f}). Physics fallback triggered."
            )
        elif confidence < threshold_yellow:
            warning_level = "YELLOW"
            logger.info(
                f"AI Confidence YELLOW ({confidence:.2f}). Proceeding with caution."
            )

        used_model = "ensemble" if not fallback_triggered else "physics_fallback"
        model_version = str(
            ensemble_result.get("model_version", "ensemble-v2.0-champion")
        )
        factors = {
            **base_factors,
            "ml_correction": round(float(ensemble_result.get("ml_correction", 0.0)), 2)
            if not fallback_triggered
            else 0.0,
            "champion_model": ensemble_result.get("champion", "ensemble"),
            "challenger_model": ensemble_result.get("challenger", "physics"),
        }
        explanation_summary = self._build_explanation_summary(
            model_used=used_model,
            model_version=model_version,
            confidence_score=float(confidence),
            load_ton=float(0.0 if bos_sefer else ton),
            ascent_m=float(ascent_m or 0.0),
            weather_factor=float(weather_factor),
        )
        guven_araligi = ensemble_result.get("guven_araligi")
        _ga_ok = isinstance(guven_araligi, (list, tuple)) and len(guven_araligi) >= 2
        return self._build_prediction_response(
            mesafe_km=mesafe_km,
            tahmini_tuketim=tahmin_l_100km,
            model_used=used_model,
            model_version=model_version,
            confidence_score=float(confidence),
            warning_level=warning_level,
            fallback_triggered=fallback_triggered,
            confidence_low=guven_araligi[0] if _ga_ok else None,
            confidence_high=guven_araligi[1] if _ga_ok else None,
            faktorler=factors,
            insight=physics_insight,
            explanation_summary=explanation_summary,
        )

    def _build_prediction_response(
        self,
        *,
        mesafe_km: float,
        tahmini_tuketim: float,
        model_used: str,
        model_version: str,
        confidence_score: float,
        warning_level: str,
        fallback_triggered: bool,
        faktorler: Dict[str, Any],
        insight: Optional[str] = None,
        confidence_low: Optional[float] = None,
        confidence_high: Optional[float] = None,
        explanation_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        tahmini_tuketim = round(float(tahmini_tuketim), 2)
        tahmini_litre = round(float(mesafe_km) * tahmini_tuketim / 100, 1)
        confidence_score = round(float(confidence_score), 2)
        c_low, c_high = self._normalize_confidence_band(
            base_value=tahmini_tuketim,
            confidence_score=confidence_score,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
        )

        payload = {
            "tahmini_tuketim": tahmini_tuketim,
            "tahmini_litre": tahmini_litre,
            # Deprecated alias for transition period.
            "prediction_liters": tahmini_litre,
            "model_used": model_used,
            "model_version": model_version,
            "status": "success",
            "confidence_score": confidence_score,
            "confidence_low": c_low,
            "confidence_high": c_high,
            "warning_level": warning_level,
            "fallback_triggered": bool(fallback_triggered),
            "faktorler": faktorler,
            "explanation_summary": explanation_summary
            or "Tahmin tamamlandi, teknik detaylar faktorlerde listelendi.",
            "insight": insight,
        }
        return payload

    async def predict_consumption(
        self,
        arac_id: int,
        mesafe_km: float,
        ton: float = 0.0,
        ascent_m: float = 0.0,
        descent_m: float = 0.0,
        flat_distance_km: float = 0.0,
        sofor_id: Optional[int] = None,
        dorse_id: Optional[int] = None,
        sofor_score: Optional[float] = None,
        ramp_pct: Optional[float] = None,
        target_date: Optional[date] = None,
        zorluk: str = "Normal",
        use_ensemble: bool = True,
        bos_sefer: bool = False,
        route_analysis: Optional[Dict] = None,
        _arac_obj: Optional[Any] = None,
        _sofor_obj: Optional[Any] = None,
        _dorse_obj: Optional[Any] = None,
    ) -> Dict:
        """
        Gelişmiş yakıt tahmini.
        1. Araç specs ve yaş düzeltmesi.
        2. Hava durumu faktörü.
        3. Fizik motoru (Physics-based).
        4. ML Ensemble düzeltmesi (XGBoost + GB + RF + LightGBM).
        5. Şoför bazlı ince ayar.

        Args:
            _arac_obj, _sofor_obj, _dorse_obj: Pre-fetched ORM objects (N+1 optimization)
        """
        if not target_date:
            target_date = date.today()

        # Nullable Sefer columns (ascent_m / descent_m / flat_distance_km) can
        # arrive as None even though the signature declares ``float`` — e.g. a
        # manually-entered trip with no route analysis. Coalesce at the boundary
        # so downstream physics/ensemble arithmetic (physics_fuel_predictor:
        # ``ascent_m + descent_m``, ensemble ``net_elevation``) never hits
        # ``None + None``. Without this the elite-score path silently swallows
        # the TypeError and returns no score for such drivers.
        ascent_m = float(ascent_m or 0.0)
        descent_m = float(descent_m or 0.0)
        flat_distance_km = float(flat_distance_km or 0.0)

        normalized_route = self._normalize_route_analysis(route_analysis)

        # ── 1. Fetch entities ─────────────────────────────────────────────────
        arac: Optional[Dict[str, Any]] = None
        sofor: Optional[Dict[str, Any]] = None
        dorse: Optional[Dict[str, Any]] = None

        # N+1 optimization: use pre-fetched objects if provided
        if _arac_obj:
            arac = _arac_obj.__dict__ if hasattr(_arac_obj, "__dict__") else _arac_obj
        if _sofor_obj:
            sofor = (
                _sofor_obj.__dict__ if hasattr(_sofor_obj, "__dict__") else _sofor_obj
            )
        if _dorse_obj:
            dorse = (
                _dorse_obj.__dict__ if hasattr(_dorse_obj, "__dict__") else _dorse_obj
            )

        # Only fetch from DB if not already provided
        if not arac or not sofor or not dorse:
            async with UnitOfWork() as uow:
                if arac_id > 0 and not arac:
                    raw = await uow.arac_repo.get_by_id(arac_id)
                    if raw:
                        arac = raw.__dict__ if hasattr(raw, "__dict__") else raw
                if sofor_id and not sofor:
                    raw = await uow.sofor_repo.get_by_id(sofor_id)
                    if raw:
                        sofor = raw.__dict__ if hasattr(raw, "__dict__") else raw
                if dorse_id and not dorse:
                    raw = await uow.dorse_repo.get_by_id(dorse_id)
                    if raw:
                        dorse = raw.__dict__ if hasattr(raw, "__dict__") else raw
                # D.4 — bakım metadata'sını aynı UoW içinde inject et
                # (nested UoW açma; downstream factor hesabı için)
                if arac and settings.MAINTENANCE_FACTOR_ENABLED:
                    try:
                        from app.core.ml.vehicle_health_factor import (
                            fetch_health_input,
                        )

                        arac["_health_input"] = await fetch_health_input(uow, arac_id)
                    except Exception as exc:
                        logger.warning(
                            "D.4 fetch_health_input failed for arac %s: %s",
                            arac_id,
                            exc,
                        )

        # D.4 — bakım çarpanını şimdi (ensemble/physics çağırılmadan önce)
        # hesapla; payload post-process'te tek noktadan uygulanır.
        maintenance_factor = 1.0
        maintenance_reason: Optional[str] = None
        if (
            settings.MAINTENANCE_FACTOR_ENABLED
            and arac
            and arac.get("_health_input") is not None
        ):
            try:
                from app.core.ml.vehicle_health_factor import (
                    compute_maintenance_factor,
                )

                h_res = compute_maintenance_factor(arac["_health_input"])
                maintenance_factor = h_res.factor
                maintenance_reason = h_res.reason
            except Exception as exc:
                logger.warning("D.4 compute_maintenance_factor failed: %s", exc)

        # ── 2. Vehicle specs + age degradation ───────────────────────────────
        # Runtime config resolved ONCE per request here (async boundary) —
        # never inside the sync _build_vehicle_specs helper, and never
        # per-segment (there is no per-segment fan-out for this factor).
        from app.core.services.runtime_config import get_runtime_float

        age_degradation_rate = await get_runtime_float(
            "VEHICLE_AGE_DEGRADATION_RATE", settings.VEHICLE_AGE_DEGRADATION_RATE
        )
        specs, age = self._build_vehicle_specs(arac, dorse, age_degradation_rate)

        # ── 3. Route ratios & weather ─────────────────────────────────────────
        otoyol_ratio, devlet_yolu_ratio, sehir_ici_ratio = 0.6, 0.3, 0.1
        if normalized_route and "ratios" in normalized_route:
            r = normalized_route["ratios"]
            otoyol_ratio = r.get("otoyol", 0.6)
            devlet_yolu_ratio = r.get("devlet_yolu", 0.3)
            sehir_ici_ratio = r.get("sehir_ici", 0.1)

        if normalized_route and "weather_factor" in normalized_route:
            weather_factor = float(normalized_route["weather_factor"])
        else:
            weather_factor = await asyncio.to_thread(
                self.weather_service.get_seasonal_factor, target_date
            )

        # ── 4. Physics prediction ─────────────────────────────────────────────
        physics_result = await self._run_physics_model(
            specs=specs,
            age=age,
            mesafe_km=mesafe_km,
            ton=ton,
            ascent_m=ascent_m,
            descent_m=descent_m,
            flat_distance_km=flat_distance_km,
            bos_sefer=bos_sefer,
            weather_factor=weather_factor,
            otoyol_ratio=otoyol_ratio,
            devlet_yolu_ratio=devlet_yolu_ratio,
            sehir_ici_ratio=sehir_ici_ratio,
            normalized_route=normalized_route,
        )

        physics_l_100km = physics_result.consumption_l_100km
        await self._log_prediction_to_ai(arac_id, mesafe_km, physics_l_100km)

        # ── 5. Driver / ramp adjustments → physics fallback value ─────────────
        s_score = sofor_score or (sofor.get("score", 1.0) if sofor else None)
        sofor_influence = (
            max(0.8, min(1.2, 1.0 + (1.0 - s_score) * 0.2))
            if s_score is not None
            else 1.0
        )
        ramp_factor = (
            1.0 + (ramp_pct / 100) * 0.2
            if ramp_pct is not None and not (ascent_m and ascent_m > 0)
            else 1.0
        )
        fallback_l_100km = physics_l_100km * sofor_influence * ramp_factor
        base_factors = self._build_base_factors(
            physics_l_100km=physics_l_100km,
            weather_factor=weather_factor,
            s_score=s_score,
            sofor_influence=sofor_influence,
            ramp_factor=ramp_factor,
            ton=ton,
            ascent_m=ascent_m,
            descent_m=descent_m,
            flat_distance_km=flat_distance_km,
            otoyol_ratio=otoyol_ratio,
            devlet_yolu_ratio=devlet_yolu_ratio,
            sehir_ici_ratio=sehir_ici_ratio,
            age=age,
            dorse_id=dorse_id,
            zorluk=zorluk,
            bos_sefer=bos_sefer,
        )

        # ── 6. Ensemble (ML) prediction ───────────────────────────────────────
        if use_ensemble and arac_id > 0:
            sefer_dict = await self._build_sefer_dict(
                arac=arac or {},
                sofor=sofor,
                dorse=dorse,
                mesafe_km=mesafe_km,
                ton=ton,
                ascent_m=ascent_m,
                descent_m=descent_m,
                flat_distance_km=flat_distance_km,
                target_date=target_date,
                bos_sefer=bos_sefer,
                route_analysis=normalized_route,
                weather_factor=weather_factor,
            )
            ensemble_result = await self._run_ensemble_prediction(
                arac_id, sefer_dict, target_date
            )

            if ensemble_result and ensemble_result.get("success"):
                ensemble_payload = self._process_ensemble_result(
                    ensemble_result=ensemble_result,
                    fallback_l_100km=fallback_l_100km,
                    mesafe_km=mesafe_km,
                    ton=ton,
                    ascent_m=ascent_m,
                    bos_sefer=bos_sefer,
                    weather_factor=weather_factor,
                    base_factors=base_factors,
                    physics_insight=physics_result.insight,
                )
                # D.4 — bakım çarpanı her iki path'e de uygulanır
                from app.core.ml.vehicle_health_factor import (
                    apply_maintenance_factor,
                )

                return apply_maintenance_factor(
                    ensemble_payload,
                    maintenance_factor,
                    maintenance_reason,
                )

        # ── 7. Physics-only fallback ──────────────────────────────────────────
        fallback_ctx: Dict[str, Any] = {
            "_use_ensemble": use_ensemble,
            "_fallback_l_100km": fallback_l_100km,
            "_base_factors": base_factors,
            "_physics_insight": physics_result.insight,
            "ton": 0.0 if bos_sefer else ton,
            "ascent_m": ascent_m,
            "weather_factor": weather_factor,
        }
        fallback_payload = self._run_physics_fallback(
            arac or {}, fallback_ctx, mesafe_km
        )
        # D.4 — bakım çarpanı physics fallback path'inde de uygulanır
        from app.core.ml.vehicle_health_factor import apply_maintenance_factor

        return apply_maintenance_factor(
            fallback_payload, maintenance_factor, maintenance_reason
        )

    async def _log_prediction_to_ai(
        self, arac_id: int, mesafe_km: float, consumption: float
    ):
        """Background task: AI'a tahmin bilgisi gönder"""
        try:
            from app.services.smart_ai_service import get_smart_ai

            smart_ai = get_smart_ai()

            async def _safe_teach():
                try:
                    msg = (
                        f"Tahmin: Araç {arac_id}, {mesafe_km} km,"
                        f" {consumption:.2f} L/100km"
                    )
                    await smart_ai.teach(msg, category="tahmin_izleme")
                except Exception as e:
                    logger.debug(f"AI teach task failed: {e}")

            task = asyncio.create_task(_safe_teach())
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)
        except Exception:
            pass

    async def explain_consumption(
        self,
        arac_id: int,
        mesafe_km: float,
        ton: float = 0.0,
        ascent_m: float = 0.0,
        descent_m: float = 0.0,
        flat_distance_km: float = 0.0,
        sofor_id: Optional[int] = None,
        sofor_score: Optional[float] = None,
        zorluk: str = "Normal",
        route_analysis: Optional[Dict] = None,
    ) -> Dict:
        """
        Tahmin sonucunun nedenlerini açıklar (XAI).
        """
        # Feature setini hazırla (predict ile uyumlu)
        s_score = sofor_score
        if s_score is None and sofor_id:
            from app.core.services.sofor_analiz_service import get_sofor_analiz_service

            sofor_service = get_sofor_analiz_service()
            stats = await sofor_service.get_driver_stats(
                sofor_id, include_elite_score=False
            )
            if stats:
                s_score = 1.0 - (stats[0].filo_karsilastirma / 100) * 0.1

        normalized_route_analysis = self._normalize_route_analysis(route_analysis)

        sefer = {
            "mesafe_km": mesafe_km,
            "ton": ton,
            "ascent_m": ascent_m,
            "descent_m": descent_m,
            "flat_distance_km": flat_distance_km,
            "zorluk": zorluk,
            "sofor_id": sofor_id,
            "sofor_katsayi": s_score or 1.0,
            "route_analysis": normalized_route_analysis,
        }

        # Predictor al ve açıkla
        predictor = self.ensemble_service.get_predictor(arac_id)
        if not predictor.is_trained and arac_id != 0:
            predictor = self.ensemble_service.get_predictor(0)

        return await asyncio.to_thread(predictor.explain_prediction, sefer)

    async def train_xgboost_model(
        self, arac_id: int, user_id: int | None = None
    ) -> Dict:
        """Belirli bir araç için tüm modelleri eğitir.

        user_id audit log'a yazılır (kim tetiklediyse).
        """
        from app.infrastructure.audit.audit_logger import log_audit_event

        # ensemble_service uses train_for_vehicle method
        res = await self.ensemble_service.train_for_vehicle(arac_id)
        try:
            await log_audit_event(
                action="ml_train",
                module="prediction",
                entity_id=str(arac_id),
                user_id=user_id,
                new_value={
                    "success": bool(res.get("success")),
                    "r2": float(res.get("ensemble_r2", 0.0)),
                    "samples": int(res.get("sample_count", 0)),
                },
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("ML train audit log failed: %s", exc)
        return {
            "status": "success" if res.get("success") else "failure",
            "model_type": "ensemble",
            "r2_score": res.get("ensemble_r2", 0.0),
            "sample_count": res.get("sample_count", 0),
            "metrics": res.get("metrics", {}),
        }


# Singleton accessor
_prediction_service = None


def get_prediction_service() -> PredictionService:
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService()
    return _prediction_service
