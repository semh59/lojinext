"""
TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: ML ensemble yakıt tahmini — model dosyaları başlangıçta bir kez yüklenir.
CREATED_BY: v2/modules/platform_infra/container.py (lazy property)
"""

import asyncio
import logging
from datetime import date
from typing import Any, Dict, Optional

from app.config import settings
from app.core.services.weather_service import WeatherService
from v2.modules.prediction_ml.application.ensemble_orchestration import (
    process_ensemble_result,
    run_ensemble_prediction,
)
from v2.modules.prediction_ml.application.ensemble_service import get_ensemble_service
from v2.modules.prediction_ml.application.response_builder import (
    build_explanation_summary,
    build_prediction_response,
)
from v2.modules.prediction_ml.domain.physics_model import (
    build_base_factors,
    build_vehicle_specs,
    run_physics_model,
)
from v2.modules.prediction_ml.domain.route_ratios import normalize_route_analysis
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

_bg_tasks: set[asyncio.Task] = set()


class PredictionService:
    """
    Yakıt Tahmin Servisi.
    Fizik motoru ve ML modellerini (Ensemble) orkestra eder.
    """

    def __init__(self):
        self.weather_service = WeatherService()
        self.ensemble_service = get_ensemble_service()

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

        Kept in application/ (not domain/physics_model.py, despite the task
        file's original clustering) because it calls into
        ``response_builder`` — domain/ must not depend on application/.
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
        fallback_summary = build_explanation_summary(
            model_used=fallback_model,
            model_version=fallback_version,
            confidence_score=fallback_confidence,
            load_ton=float(sefer_dict.get("ton", 0.0)),
            ascent_m=float(sefer_dict.get("ascent_m") or 0.0),
            weather_factor=float(sefer_dict.get("weather_factor") or 1.0),
        )
        return build_prediction_response(
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

        normalized_route = normalize_route_analysis(route_analysis)

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
                        from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
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
                from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
                    compute_maintenance_factor,
                )

                h_res = compute_maintenance_factor(arac["_health_input"])
                maintenance_factor = h_res.factor
                maintenance_reason = h_res.reason
            except Exception as exc:
                logger.warning("D.4 compute_maintenance_factor failed: %s", exc)

        # ── 2. Vehicle specs + age degradation ───────────────────────────────
        # Runtime config resolved ONCE per request here (async boundary) —
        # never inside the sync build_vehicle_specs helper, and never
        # per-segment (there is no per-segment fan-out for this factor).
        from v2.modules.admin_platform.public import (
            get_runtime_float,
        )

        age_degradation_rate = await get_runtime_float(
            "VEHICLE_AGE_DEGRADATION_RATE", settings.VEHICLE_AGE_DEGRADATION_RATE
        )
        specs, age = build_vehicle_specs(arac, dorse, age_degradation_rate)

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
        physics_result = await run_physics_model(
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
        base_factors = build_base_factors(
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
            ensemble_result = await run_ensemble_prediction(
                self.ensemble_service, arac_id, sefer_dict, target_date
            )

            if ensemble_result and ensemble_result.get("success"):
                ensemble_payload = process_ensemble_result(
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
                from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
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
        from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
            apply_maintenance_factor,
        )

        return apply_maintenance_factor(
            fallback_payload, maintenance_factor, maintenance_reason
        )

    async def _log_prediction_to_ai(
        self, arac_id: int, mesafe_km: float, consumption: float
    ):
        """Background task: AI'a tahmin bilgisi gönder"""
        try:
            from v2.modules.ai_assistant.public import get_smart_ai

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
            from v2.modules.driver.public import get_driver_stats

            stats = await get_driver_stats(sofor_id, include_elite_score=False)
            if stats:
                s_score = 1.0 - (stats[0].filo_karsilastirma / 100) * 0.1

        normalized_route_analysis = normalize_route_analysis(route_analysis)

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
        from v2.modules.platform_infra.audit.audit_logger import log_audit_event

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


def get_prediction_service() -> PredictionService:
    """Delegates to the DI container for the singleton PredictionService instance."""
    from v2.modules.platform_infra.container import get_container

    return get_container().prediction_service
