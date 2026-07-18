"""Use-case: analyze a location's route via the hybrid get_route_details use-case.

NOT (geçici, mimari borç): route_simulation modülünün henüz public.py'si
yok (application/get_route_details.py'den doğrudan import ediliyor) — o
modülün API/application katmanları tamamlanınca bu import
v2.modules.route_simulation.public'e güncellenecek.
"""

from datetime import datetime, timezone

from app.infrastructure.logging.logger import get_logger
from v2.modules.location.infrastructure.repository import LokasyonRepository

logger = get_logger(__name__)


async def analyze_location_route(repo: LokasyonRepository, lokasyon_id: int) -> dict:
    """Hibrit rota tespit use-case'i kullanarak güzergahı analiz et ve güncelle"""
    from v2.modules.route_simulation.public import get_route_details

    loc = await repo.get_by_id(lokasyon_id)
    if not loc or not all(
        [
            loc.get("cikis_lat"),
            loc.get("cikis_lon"),
            loc.get("varis_lat"),
            loc.get("varis_lon"),
        ]
    ):
        raise ValueError(f"Lokasyon {lokasyon_id} koordinat bilgileri eksik.")

    start_coords = (loc["cikis_lon"], loc["cikis_lat"])
    end_coords = (loc["varis_lon"], loc["varis_lat"])

    # use_cache=False because we want fresh analysis/correction
    result = await get_route_details(start_coords, end_coords, use_cache=False)

    if "error" in result:
        raise ValueError(f"Analiz hatası: {result['error']}")

    await repo.update(
        lokasyon_id,
        mesafe_km=result["distance_km"],
        tahmini_sure_saat=round(result["duration_min"] / 60, 2),
        api_mesafe_km=result["distance_km"],
        api_sure_saat=round(result["duration_min"] / 60, 2),
        ascent_m=result["ascent_m"],
        descent_m=result["descent_m"],
        flat_distance_km=result["flat_distance_km"],
        otoban_mesafe_km=result.get("otoban_mesafe_km"),
        sehir_ici_mesafe_km=result.get("sehir_ici_mesafe_km"),
        zorluk=result.get("difficulty", loc.get("zorluk", "Normal")),
        source=result.get("source"),
        is_corrected=result.get("is_corrected", False),
        correction_reason=result.get("correction_reason"),
        route_analysis=result.get("route_analysis"),
        distributions=result.get("distributions"),
        last_api_call=datetime.now(timezone.utc),
    )

    logger.info(
        f"Güzergah {lokasyon_id} hibrit servis ile güncellendi. Kaynak: {result.get('source')}"
    )

    await _apply_baseline_fuel_estimate(repo, lokasyon_id, result)

    return result


async def _apply_baseline_fuel_estimate(
    repo: LokasyonRepository, lokasyon_id: int, result: dict
) -> None:
    """Baseline yakıt tahmini (standart TIR, 13t yük — güzergah kartında göstermek için).

    2026-07-18: prediction_ml taşındı — artık `v2.modules.prediction_ml.public`
    üzerinden erişiyor (eski `app.core.ml.physics_fuel_predictor` bypass'ı kapandı).
    """
    try:
        import asyncio

        from v2.modules.prediction_ml.public import (
            PhysicsBasedFuelPredictor,
            RouteConditions,
        )

        predictor = PhysicsBasedFuelPredictor()
        route_conds = RouteConditions(
            distance_km=result["distance_km"],
            load_ton=13.0,
            ascent_m=result.get("ascent_m", 0) or 0,
            descent_m=result.get("descent_m", 0) or 0,
            flat_distance_km=result.get("flat_distance_km", 0) or 0,
            route_analysis=result.get("route_analysis"),
        )
        fuel_pred = await asyncio.to_thread(predictor.predict, route_conds)
        await repo.update(lokasyon_id, tahmini_yakit_lt=fuel_pred.total_liters)
        result["tahmini_yakit_lt"] = fuel_pred.total_liters
    except Exception as e:
        logger.warning(f"Baseline yakıt tahmini başarısız (ID: {lokasyon_id}): {e}")
