"""Sefer yakıt tahmini zenginleştirme kümesi — prediction_ml'e TEK köprü.

Bu dosya trip modülünün prediction_ml modülüyle konuştuğu tek yer olacak
şekilde tasarlandı (task dosyası madde 5'in "prediction_ml'e TEK köprü"
kararı). ``check_reprediction_needed`` teknik olarak I/O'suz/saf bir
fonksiyon olsa da, bu kümenin geri kalanıyla anlamsal olarak sıkı bağlı
olduğu için (yalnızca ``repredikt_for_update``'in tetiklenip
tetiklenmeyeceğine karar verir) task dosyasının kümelemesine sadık kalınarak
burada tutuldu, ayrı bir dosyaya bölünmedi.
"""

from datetime import date
from typing import Any, Dict, Optional

from app.core.utils.type_helpers import safe_float
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

PREDICTION_TIMEOUT_SECONDS = 2.5


def build_route_details_snapshot(
    source: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(source, dict):
        return None

    route_analysis = source.get("route_analysis")
    if not isinstance(route_analysis, dict):
        route_analysis = source.get("rota_detay")

    snapshot: Dict[str, Any] = {}
    if isinstance(route_analysis, dict):
        snapshot["route_analysis"] = dict(route_analysis)

    for key in ("otoban_mesafe_km", "sehir_ici_mesafe_km"):
        if source.get(key) is not None:
            snapshot[key] = source.get(key)

    return snapshot or None


def build_prediction_quality_flags(
    route_details: Optional[Dict[str, Any]] = None,
    weather_factor: Optional[float] = None,
) -> Dict[str, Any]:
    route_analysis = (
        route_details.get("route_analysis") if isinstance(route_details, dict) else None
    )
    return {
        "canonical_prediction": True,
        "route_available": bool(route_details),
        "route_analysis_available": isinstance(route_analysis, dict),
        "weather_factor_applied": weather_factor is not None,
    }


def build_prediction_route_analysis(
    route_details: Optional[Dict[str, Any]] = None,
    weather_factor: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    analysis: Dict[str, Any] = {}
    if isinstance(route_details, dict):
        route_analysis = route_details.get("route_analysis")
        if isinstance(route_analysis, dict):
            analysis.update(route_analysis)
        # Also carry the standalone distributions column (may differ from
        # route_analysis["distributions"] if route_analysis was never stored)
        distributions = route_details.get("distributions")
        if isinstance(distributions, dict) and "distributions" not in analysis:
            analysis["distributions"] = distributions
    if weather_factor is not None:
        analysis["weather_factor"] = float(weather_factor)
    return analysis or None


def extract_prediction_values(
    prediction: Optional[Dict[str, Any]],
    quality_flags: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[float], Optional[Dict[str, Any]]]:
    if not isinstance(prediction, dict):
        return None, None

    canonical_value = safe_float(prediction.get("tahmini_tuketim"))
    if canonical_value is None:
        return None, None

    meta: Dict[str, Any] = {
        "input_quality": {
            "canonical_prediction": True,
            **(quality_flags or {}),
        }
    }

    tahmini_litre = safe_float(prediction.get("tahmini_litre"))
    if tahmini_litre is None:
        tahmini_litre = safe_float(prediction.get("prediction_liters"))
    if tahmini_litre is not None:
        meta["tahmini_litre"] = round(tahmini_litre, 1)

    for key in (
        "model_used",
        "model_version",
        "status",
        "warning_level",
        "insight",
        "explanation_summary",
    ):
        if prediction.get(key) is not None:
            meta[key] = prediction.get(key)

    for key in ("confidence_score", "confidence_low", "confidence_high"):
        numeric_value = safe_float(prediction.get(key))
        if numeric_value is not None:
            meta[key] = numeric_value

    if prediction.get("fallback_triggered") is not None:
        meta["fallback_triggered"] = bool(prediction.get("fallback_triggered"))

    faktorler = prediction.get("faktorler")
    if isinstance(faktorler, dict):
        meta["faktorler"] = faktorler

    return canonical_value, meta


def check_reprediction_needed(update_data: Dict[str, Any]) -> bool:
    """Tahmin etkileyen alan değişikliği var mı kontrol eder."""
    repredict_fields = {
        "guzergah_id",
        "arac_id",
        "sofor_id",
        "net_kg",
        "ton",
        "tarih",
        "bos_sefer",
        "dorse_id",
    }
    return any(field in update_data for field in repredict_fields)


async def repredikt_for_update(
    uow: Any,
    current_sefer: Dict[str, Any],
    update_data: Dict[str, Any],
) -> None:
    """Update sırasında gerektiğinde tahmini yeniler.

    update_data'yı in-place günceller.
    """
    # Build prediction parameters (merging old and new data)
    pred_arac_id = update_data.get("arac_id", current_sefer.get("arac_id"))
    pred_sofor_id = update_data.get("sofor_id", current_sefer.get("sofor_id"))
    pred_tarih = update_data.get("tarih", current_sefer.get("tarih"))
    pred_bos_sefer = update_data.get("bos_sefer", current_sefer.get("bos_sefer"))
    pred_dorse_id = update_data.get("dorse_id", current_sefer.get("dorse_id"))

    # Tonaj logic (Standardized)
    pred_ton = update_data.get("ton")
    if pred_ton is None:
        pred_net_kg = update_data.get("net_kg", current_sefer.get("net_kg", 0))
        pred_ton = float(pred_net_kg) / 1000.0 if pred_net_kg else 0.0

    # If it's an empty return (bos_sefer), ton is essentially 0
    if pred_bos_sefer:
        pred_ton = 0.0

    # Get route info if available
    pred_mesafe = update_data.get("mesafe_km", current_sefer.get("mesafe_km", 0.0))
    pred_ascent = update_data.get("ascent_m", current_sefer.get("ascent_m", 0.0))
    pred_descent = update_data.get("descent_m", current_sefer.get("descent_m", 0.0))
    pred_flat = update_data.get(
        "flat_distance_km", current_sefer.get("flat_distance_km", 0.0)
    )
    prediction_route_details = build_route_details_snapshot(
        {
            "route_analysis": current_sefer.get("rota_detay"),
            "otoban_mesafe_km": current_sefer.get("otoban_mesafe_km"),
            "sehir_ici_mesafe_km": current_sefer.get("sehir_ici_mesafe_km"),
        }
    )

    # Enrich from NEW route if changed
    if "guzergah_id" in update_data and update_data["guzergah_id"]:
        route_dict = await uow.lokasyon_repo.get_by_id(update_data["guzergah_id"])
        if route_dict:
            prediction_route_details = build_route_details_snapshot(route_dict)
            pred_mesafe = route_dict.get("mesafe_km", pred_mesafe)
            pred_ascent = route_dict.get("ascent_m", pred_ascent)
            pred_descent = route_dict.get("descent_m", pred_descent)
            pred_flat = route_dict.get("flat_distance_km", pred_flat)
            # Actually apply these to update_data as well
            update_data["mesafe_km"] = pred_mesafe
            update_data["ascent_m"] = pred_ascent
            update_data["descent_m"] = pred_descent
            update_data["flat_distance_km"] = pred_flat

            # Enhanced Route Data
            if "route_analysis" in route_dict:
                update_data["rota_detay"] = route_dict["route_analysis"]
            if "otoban_mesafe_km" in route_dict:
                update_data["otoban_mesafe_km"] = route_dict["otoban_mesafe_km"]
            if "sehir_ici_mesafe_km" in route_dict:
                update_data["sehir_ici_mesafe_km"] = route_dict["sehir_ici_mesafe_km"]

    # Trigger Prediction
    try:
        logger.info(
            "Triggering PREDICTION: Arac=%s, Mesafe=%s, Ton=%s, Empty=%s",
            pred_arac_id,
            pred_mesafe,
            pred_ton,
            pred_bos_sefer,
        )
        from v2.modules.prediction_ml.public import get_prediction_service

        pred_service = get_prediction_service()

        prediction = await pred_service.predict_consumption(
            arac_id=pred_arac_id,
            mesafe_km=pred_mesafe,
            ton=pred_ton,
            ascent_m=pred_ascent,
            descent_m=pred_descent,
            flat_distance_km=pred_flat,
            sofor_id=pred_sofor_id,
            target_date=pred_tarih
            if isinstance(pred_tarih, date)
            else date.fromisoformat(str(pred_tarih)),
            bos_sefer=pred_bos_sefer,
            dorse_id=pred_dorse_id,
            route_analysis=build_prediction_route_analysis(
                route_details=prediction_route_details
            ),
        )
        tahmini_tuketim, tahmin_meta = extract_prediction_values(
            prediction,
            quality_flags=build_prediction_quality_flags(
                route_details=prediction_route_details
            ),
        )
        if tahmini_tuketim is not None:
            update_data["tahmini_tuketim"] = tahmini_tuketim
        if tahmin_meta is not None:
            update_data["tahmin_meta"] = tahmin_meta
        if tahmini_tuketim is not None:
            logger.info(
                "Re-prediction SUCCESS: %s L",
                update_data["tahmini_tuketim"],
            )
    except Exception as pe:
        logger.error(f"Re-prediction error: {pe}", exc_info=True)


async def resolve_route(uow: Any, data: Any) -> Optional[Dict[str, Any]]:
    """Güzergah metadata'sını çeker ve data'ya elevation alanlarını yazar."""
    if not data.guzergah_id:
        return None
    route_dict = await uow.lokasyon_repo.get_by_id(data.guzergah_id)
    if not route_dict:
        return None
    if not data.mesafe_km:
        data.mesafe_km = route_dict.get("mesafe_km", 0.0)
    if not data.ascent_m:
        data.ascent_m = route_dict.get("ascent_m", 0.0)
    if not data.descent_m:
        data.descent_m = route_dict.get("descent_m", 0.0)
    return route_dict


async def predict_via_estimator(
    uow: Any,
    data: Any,
    trip_date: date,
    route_dict: Optional[Dict[str, Any]],
) -> tuple:
    """Phase 4.4: SeferFuelEstimator ile yeni tahmin akışı.

    ``settings.USE_SEFER_FUEL_ESTIMATOR=True`` ise ``predict_outbound``
    en başta bunu çağırır. Mapbox + Open-Meteo elevation + weather +
    physics + adjustment factors birleşimi (Phase 4.3).

    Returns:
        (tuketim, meta, simulation_id) — meta dict'ine simulation_id
        de inject edilir (debug için). Mevcut helper'lar uyumlu kalır.
    """
    try:
        from v2.modules.trip.application.sefer_fuel_estimator import (
            SeferFuelInput,
            get_sefer_fuel_estimator,
        )

        estimator = get_sefer_fuel_estimator()
        ton = float(data.ton or (data.net_kg / 1000.0 if data.net_kg else 0.0))

        cikis_lat = cikis_lon = varis_lat = varis_lon = None
        if route_dict:
            cikis_lat = route_dict.get("cikis_lat")
            cikis_lon = route_dict.get("cikis_lon")
            varis_lat = route_dict.get("varis_lat")
            varis_lon = route_dict.get("varis_lon")

        inp = SeferFuelInput(
            arac_id=data.arac_id,
            sofor_id=data.sofor_id,
            dorse_id=data.dorse_id,
            ton=ton,
            target_date=trip_date,
            bos_sefer=bool(data.bos_sefer),
            lokasyon_id=data.guzergah_id,
            cikis_lat=cikis_lat,
            cikis_lon=cikis_lon,
            varis_lat=varis_lat,
            varis_lon=varis_lon,
        )

        import asyncio as _asyncio

        try:
            estimate = await _asyncio.wait_for(
                estimator.predict(inp, persist=True, session=uow.session),
                timeout=PREDICTION_TIMEOUT_SECONDS,
            )
        except _asyncio.TimeoutError:
            logger.warning(
                "SeferFuelEstimator timeout (>%ss) for arac=%s — "
                "sefer kaydı tahmin olmadan kaydedilecek.",
                PREDICTION_TIMEOUT_SECONDS,
                data.arac_id,
            )
            from app.infrastructure.monitoring.silent_fallback_probe import (
                record_silent_fallback,
            )

            record_silent_fallback("sefer_estimator_timeout", arac_id=data.arac_id)
            return None, None, None

        if estimate is None:
            return None, None, None

        legacy = estimate.to_legacy_prediction_dict()
        tuketim, meta = extract_prediction_values(
            legacy,
            quality_flags=build_prediction_quality_flags(route_details=route_dict),
        )
        if meta is not None:
            meta["simulation_id"] = estimate.simulation_id
            meta["estimator_source"] = "SeferFuelEstimator"
        return tuketim, meta, estimate.simulation_id
    except Exception as exc:
        logger.error("SeferFuelEstimator path failed: %s", exc)
        return None, None, None


async def predict_outbound(
    uow: Any,
    data: Any,
    trip_date: date,
    route_dict: Optional[Dict[str, Any]],
) -> tuple:
    """Gidiş seferi için yakıt tahmini çalıştırır.

    Phase 4.4 (USE_SEFER_FUEL_ESTIMATOR feature flag):
    - True: yeni SeferFuelEstimator pipeline kullanılır → tuple-3
      (tuketim, meta, simulation_id) döner
    - False (default): eski predict_consumption akışı → tuple-3'ün
      son elemanı None
    """
    from app.config import settings

    if settings.USE_SEFER_FUEL_ESTIMATOR:
        return await predict_via_estimator(uow, data, trip_date, route_dict)
    try:
        from app.core.services.weather_service import get_weather_service
        from v2.modules.prediction_ml.public import get_prediction_service

        pred_service = get_prediction_service()
        weather_service = get_weather_service()
        weather_factor: Optional[float] = None

        if data.guzergah_id and route_dict:
            try:
                c_lat = route_dict.get("cikis_lat")
                c_lon = route_dict.get("cikis_lon")
                v_lat = route_dict.get("varis_lat")
                v_lon = route_dict.get("varis_lon")
                if c_lat and v_lat:
                    w_res = await weather_service.get_trip_impact_analysis(
                        cikis_lat=c_lat,
                        cikis_lon=c_lon,
                        varis_lat=v_lat,
                        varis_lon=v_lon,
                    )
                    if (
                        w_res.get("success")
                        and w_res.get("fuel_impact_factor") is not None
                    ):
                        weather_factor = w_res["fuel_impact_factor"]
            except Exception as we:
                logger.warning(f"Weather failed: {we}")

        prediction_quality = build_prediction_quality_flags(
            route_details=route_dict,
            weather_factor=weather_factor,
        )
        # ML cold-start veya schema mismatch senaryolarında sefer kaydı
        # response'u 10sn beklemesin — timeout durumunda physics fallback.
        import asyncio as _asyncio

        try:
            prediction = await _asyncio.wait_for(
                pred_service.predict_consumption(
                    arac_id=data.arac_id,
                    mesafe_km=data.mesafe_km,
                    ton=data.ton or round(data.net_kg / 1000, 2),
                    ascent_m=data.ascent_m or 0.0,
                    descent_m=data.descent_m or 0.0,
                    flat_distance_km=data.flat_distance_km or 0.0,
                    sofor_id=data.sofor_id,
                    target_date=trip_date,
                    bos_sefer=data.bos_sefer,
                    dorse_id=data.dorse_id,
                    route_analysis=build_prediction_route_analysis(
                        route_details=route_dict,
                        weather_factor=weather_factor,
                    ),
                ),
                timeout=PREDICTION_TIMEOUT_SECONDS,
            )
        except _asyncio.TimeoutError:
            logger.warning(
                "Prediction timeout (>%ss) for arac=%s — sefer kaydı "
                "tahmin olmadan kaydedilecek.",
                PREDICTION_TIMEOUT_SECONDS,
                data.arac_id,
            )
            from app.infrastructure.monitoring.silent_fallback_probe import (
                record_silent_fallback,
            )

            record_silent_fallback("legacy_predict_timeout", arac_id=data.arac_id)
            return None, None, None
        tuk, meta = extract_prediction_values(prediction, quality_flags=prediction_quality)
        # Phase 4.4: tuple-3 — eski path simulation_id YOK
        return tuk, meta, None
    except Exception as pe:
        logger.error(f"Tahmin servisi hatası: {pe}")
        return None, None, None
