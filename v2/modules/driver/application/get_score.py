"""Use-case: hybrid ML correction score + XAI score breakdown."""

from typing import Any, Dict, Optional

from v2.modules.platform_infra.public import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def calculate_hybrid_score(
    sofor_id: int,
    manual_score: float,
    uow: Optional[UnitOfWork] = None,
) -> float:
    """Hybrid ML correction factor stored as ``soforler.score``.

    Scale: 0.1-2.0 (multiplicative factor, NOT a percentage).
    Interpretation: 1.0 = average driver (30 L/100km reference), >1.0 = more
    efficient, <1.0 = less efficient. Used by the ML pipeline to adjust
    per-driver fuel predictions. Formula: 60% perf_factor + 40% manual_score.

    NOT comparable to the 0-100 elite/fleet scores — different scale and purpose.
    Pass an existing ``uow`` to avoid nested UoW when called from a transaction.
    """
    try:
        if uow is not None:
            stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
        else:
            async with UnitOfWork() as _uow:
                stats_list = await _uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
        if not stats_list:
            return float(manual_score)

        stats = stats_list[0]
        avg_consumption = float(stats.get("ort_tuketim") or 0)

        if avg_consumption <= 0:
            return float(manual_score)

        target_reference = 30.0
        perf_factor = target_reference / avg_consumption
        perf_score = max(0.1, min(2.0, perf_factor))

        hybrid = (float(perf_score) * 0.6) + (float(manual_score) * 0.4)
        return round(float(hybrid), 2)

    except Exception as e:
        logger.error(f"Hybrid score calculation error: {e}")
        return float(manual_score)


async def get_score_breakdown_sofor(
    sofor_id: int, uow: Optional[UnitOfWork] = None
) -> Dict[str, Any]:
    """XAI: hybrid score kırılımı.

    Aynı ``calculate_hybrid_score`` mantığını paylaşır ama hesaplamadaki
    her bileşeni (manual, auto, ağırlıklar, ortalama tüketim, sefer
    sayısı, referans) ayrı ayrı döner. Frontend bunları görsel formüle
    çevirir. ``uow`` verilirse aynı transaction paylaşılır (coaching engine
    gibi çağıranlar için — repo session-aware olmak zorunda).
    """
    if uow is not None:
        sofor = await uow.sofor_repo.get_by_id(sofor_id)
    else:
        async with UnitOfWork() as _uow:
            sofor = await _uow.sofor_repo.get_by_id(sofor_id)
    if not sofor:
        raise ValueError("Driver not found")

    manual = float(sofor.get("manual_score") or sofor.get("score") or 1.0)
    manual = max(0.1, min(2.0, manual))

    target_reference = 30.0
    manual_weight = 0.4
    auto_weight = 0.6
    avg_consumption = 0.0
    trip_count = 0
    has_trips = False
    auto = manual  # fallback

    try:
        if uow is not None:
            stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
        else:
            async with UnitOfWork() as _uow:
                stats_list = await _uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
        if stats_list:
            stats = stats_list[0]
            trip_count = int(stats.get("toplam_sefer") or 0)
            avg_consumption = float(stats.get("ort_tuketim") or 0)
            if avg_consumption > 0 and trip_count > 0:
                perf_factor = target_reference / avg_consumption
                auto = max(0.1, min(2.0, perf_factor))
                has_trips = True
    except Exception as e:
        logger.error(f"Score breakdown stats fetch error: {e}")
        # has_trips False kalsın → frontend "henüz yeterli veri yok" göstersin.

    total = round(manual * manual_weight + auto * auto_weight, 2)

    return {
        "sofor_id": sofor_id,
        "ad_soyad": sofor.get("ad_soyad") or "",
        "manual": round(manual, 2),
        "manual_weight": manual_weight,
        "auto": round(auto, 2),
        "auto_weight": auto_weight,
        "total": total,
        "trip_count": trip_count,
        "avg_consumption": round(avg_consumption, 2),
        "target_reference": target_reference,
        "has_trips": has_trips,
    }
