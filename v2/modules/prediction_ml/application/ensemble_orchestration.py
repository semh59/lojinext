"""Ensemble tahmin çağrısı + güven-skoru gating (predict_consumption'dan ayrıldı, dalga 13).

Task dosyası (prediction-ml.md §5) bu kümeyi `domain/ensemble.py`ye
atıyordu; ancak `run_ensemble_prediction` gerçek DB I/O yapıyor
(`UnitOfWork` açıp `EnsemblePredictorService.predict_consumption`'ı
çağırıyor) ve `process_ensemble_result` `response_builder` (application
katmanı) fonksiyonlarını çağırıyor — ikisi de kök CLAUDE.md'nin domain
saflık kuralını (I/O-suz + application'a bağımlı olmama) ihlal eder.
Bu yüzden bu iki fonksiyon `application/`de kaldı.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from app.config import settings
from v2.modules.prediction_ml.application.response_builder import (
    build_explanation_summary,
    build_prediction_response,
    extract_confidence_score,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


async def run_ensemble_prediction(
    ensemble_service: Any,
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
            result = await ensemble_service.predict_consumption(
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


def process_ensemble_result(
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
    confidence = extract_confidence_score(ensemble_result)

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
            "Ensemble response missing confidence_score. Physics fallback triggered."
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
    model_version = str(ensemble_result.get("model_version", "ensemble-v2.0-champion"))
    factors = {
        **base_factors,
        "ml_correction": round(float(ensemble_result.get("ml_correction", 0.0)), 2)
        if not fallback_triggered
        else 0.0,
        "champion_model": ensemble_result.get("champion", "ensemble"),
        "challenger_model": ensemble_result.get("challenger", "physics"),
    }
    explanation_summary = build_explanation_summary(
        model_used=used_model,
        model_version=model_version,
        confidence_score=float(confidence),
        load_ton=float(0.0 if bos_sefer else ton),
        ascent_m=float(ascent_m or 0.0),
        weather_factor=float(weather_factor),
    )
    guven_araligi = ensemble_result.get("guven_araligi")
    _ga_ok = isinstance(guven_araligi, (list, tuple)) and len(guven_araligi) >= 2
    return build_prediction_response(
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


__all__ = ["run_ensemble_prediction", "process_ensemble_result"]
