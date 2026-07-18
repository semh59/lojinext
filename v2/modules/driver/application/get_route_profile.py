"""Use-case: driver × route-type performance profile."""

from typing import Any, Dict, List, Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.driver.application.route_profile import ROUTE_TYPES, classify_route

logger = get_logger(__name__)

_LABELS = {
    "highway_dominant": "Otoyol Ağırlıklı",
    "mountain": "Dağlık",
    "urban": "Şehir İçi",
    "mixed": "Karışık",
}


async def get_route_profile_sofor(
    sofor_id: int,
    min_trips_for_best: int = 5,
    uow: Optional[UnitOfWork] = None,
) -> Dict[str, Any]:
    """Şoför × güzergah tipi profili.

    Her route_type için ortalama gerçek/tahmini tüketim ve sapma yüzdesini
    döndürür. ``best_route_type`` en az ``min_trips_for_best`` seferi olan
    ve sapma_pct'si en düşük (= tahminden en iyi performans) profili
    seçer; aday yoksa None döner. ``uow`` verilirse aynı transaction
    paylaşılır (coaching engine gibi çağıranlar için).
    """
    if uow is not None:
        sofor = await uow.sofor_repo.get_by_id(sofor_id)
        trips = await uow.sefer_repo.get_driver_trips_with_route_analysis(
            sofor_id=sofor_id, limit=300, days=365
        )
    else:
        async with UnitOfWork() as _uow:
            sofor = await _uow.sofor_repo.get_by_id(sofor_id)
            trips = await _uow.sefer_repo.get_driver_trips_with_route_analysis(
                sofor_id=sofor_id, limit=300, days=365
            )
    if not sofor:
        raise ValueError("Driver not found")

    buckets: Dict[str, List[Dict[str, float]]] = {rt: [] for rt in ROUTE_TYPES}
    for t in trips:
        rota = t.get("rota_detay") or {}
        route_analysis = rota.get("route_analysis") or rota
        try:
            rtype = classify_route(
                route_analysis if isinstance(route_analysis, dict) else {}
            )
        except Exception as e:
            logger.warning(f"classify_route failed for trip {t.get('id')}: {e}")
            continue
        if rtype not in buckets:
            continue
        actual = t.get("gercek_tuketim") or 0
        predicted = t.get("tahmini_tuketim") or 0
        if actual > 0 and predicted > 0:
            buckets[rtype].append({"actual": actual, "predicted": predicted})

    profiles: List[Dict[str, Any]] = []
    for rt in ROUTE_TYPES:
        samples = buckets[rt]
        count = len(samples)
        if count == 0:
            profiles.append(
                {
                    "route_type": rt,
                    "label": _LABELS[rt],
                    "trip_count": 0,
                    "avg_actual": 0.0,
                    "avg_predicted": 0.0,
                    "deviation_pct": 0.0,
                }
            )
            continue
        avg_actual = sum(s["actual"] for s in samples) / count
        avg_predicted = sum(s["predicted"] for s in samples) / count
        deviation_pct = (
            ((avg_actual - avg_predicted) / avg_predicted * 100.0)
            if avg_predicted > 0
            else 0.0
        )
        profiles.append(
            {
                "route_type": rt,
                "label": _LABELS[rt],
                "trip_count": count,
                "avg_actual": round(avg_actual, 2),
                "avg_predicted": round(avg_predicted, 2),
                "deviation_pct": round(deviation_pct, 2),
            }
        )

    candidates = [p for p in profiles if p["trip_count"] >= min_trips_for_best]
    best_route_type: Optional[str] = None
    if candidates:
        best = min(candidates, key=lambda p: p["deviation_pct"])
        best_route_type = best["route_type"]

    return {
        "sofor_id": sofor_id,
        "ad_soyad": sofor.get("ad_soyad") or "",
        "profiles": profiles,
        "best_route_type": best_route_type,
        "min_trips_for_best": min_trips_for_best,
    }
