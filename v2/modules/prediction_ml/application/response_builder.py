"""Tahmin yanıtı/açıklama saf yardımcıları (predict_consumption'dan ayrıldı, dalga 13).

I/O yok — `PredictionService.predict_consumption`/`_run_physics_fallback` ve
`ensemble_orchestration.process_ensemble_result` bu fonksiyonları çağırarak
son API yanıt payload'unu birleştirir.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from v2.modules.shared_kernel.utils.type_helpers import safe_float


def build_explanation_summary(
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


def normalize_confidence_band(
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


def extract_confidence_score(
    ensemble_result: Optional[Dict[str, Any]],
) -> Optional[float]:
    if not isinstance(ensemble_result, dict):
        return None
    confidence = safe_float(ensemble_result.get("confidence_score"))
    if confidence is None:
        return None
    return max(0.0, min(1.0, confidence))


def build_prediction_response(
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
    c_low, c_high = normalize_confidence_band(
        base_value=tahmini_tuketim,
        confidence_score=confidence_score,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
    )

    return {
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


__all__ = [
    "build_explanation_summary",
    "normalize_confidence_band",
    "extract_confidence_score",
    "build_prediction_response",
]
