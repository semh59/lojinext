"""Driver statistics, ranking, trend and elite-performance scoring.

Free functions (B.1 — no ``SoforAnalizService`` class). The pre-migration
class had an optional ``uow`` constructor param and 3 repo properties that
fell back to module-level singletons when no ``uow`` was supplied — every
function below keeps that same ``uow: Optional[UnitOfWork] = None``
fallback shape instead of a constructor.
"""

import asyncio
import math
from statistics import mean
from typing import Dict, List, Optional

from v2.modules.driver.domain.entities import DriverStats
from v2.modules.platform_infra.public import get_logger
from v2.modules.prediction_ml.public import get_prediction_service
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


def _repos(uow: Optional[UnitOfWork]):
    if uow is not None:
        return uow.analiz_repo, uow.sofor_repo, uow.sefer_repo

    from v2.modules.analytics_executive.public import get_analiz_repo
    from v2.modules.driver.infrastructure.repository import get_sofor_repo
    from v2.modules.trip.public import get_sefer_repo

    return get_analiz_repo(), get_sofor_repo(), get_sefer_repo()


async def _bulk_driver_metrics(uow: Optional[UnitOfWork]):
    from v2.modules.driver.infrastructure.driver_metrics_queries import (
        get_bulk_driver_metrics,
    )

    return await get_bulk_driver_metrics(uow)


async def get_driver_stats(
    sofor_id: Optional[int] = None,
    baslangic: Optional[str] = None,
    bitis: Optional[str] = None,
    include_elite_score: bool = True,
    uow: Optional[UnitOfWork] = None,
) -> List[DriverStats]:
    """
    Tüm şoförlerin veya tek şoförün istatistiklerini hesapla (Async).
    N+1 probleminden arındırılmış, optimize sürüm.
    """
    analiz_repo, sofor_repo, sefer_repo = _repos(uow)

    if sofor_id is None:
        sefer_stats = await _bulk_driver_metrics(uow)
    else:
        sefer_stats = await sofor_repo.get_sefer_stats(sofor_id, baslangic, bitis)

    if not sefer_stats:
        return []

    filo_ort = await analiz_repo.get_filo_ortalama_tuketim(baslangic, bitis)

    elite_score_map: Dict[int, Optional[float]] = {}
    if include_elite_score:
        sofor_ids = [stats["sofor_id"] for stats in sefer_stats]
        from app.config import settings as _s
        from v2.modules.driver.infrastructure.driver_trip_queries import (
            get_recent_trips_batch,
        )

        trips_by_driver = await get_recent_trips_batch(
            sofor_ids, limit_per_driver=_s.ELITE_SCORE_TRIP_LIMIT, uow=uow
        )

        for sid in sofor_ids:
            try:
                score = await _calc_elite_from_trips(trips_by_driver.get(sid, []))
                elite_score_map[sid] = score
            except Exception as exc:
                logger.warning(
                    "Elite score calculation failed for driver %s: %s", sid, exc
                )
                elite_score_map[sid] = None
    else:
        elite_score_map = {stats["sofor_id"]: None for stats in sefer_stats}

    result = []

    for stats in sefer_stats:
        sid = stats["sofor_id"]
        ort_tuketim = stats["ort_tuketim"] or 0.0

        if filo_ort > 0 and ort_tuketim > 0:
            filo_karsilastirma = round(((filo_ort - ort_tuketim) / filo_ort) * 100, 1)
        else:
            filo_karsilastirma = 0.0

        elite_score = elite_score_map.get(sid)

        driver_stats = DriverStats(
            sofor_id=sid,
            ad_soyad=stats["ad_soyad"],
            toplam_sefer=stats["toplam_sefer"],
            toplam_km=stats["toplam_km"],
            toplam_ton=float(stats.get("toplam_ton", 0) or 0),
            bos_sefer_sayisi=stats.get("bos_sefer_sayisi", 0),
            toplam_yakit=round(stats.get("toplam_yakit", 0) or 0, 1),
            ort_tuketim=round(ort_tuketim, 2),
            en_iyi_tuketim=round(stats["en_iyi_tuketim"], 2)
            if stats.get("en_iyi_tuketim")
            else None,
            en_kotu_tuketim=round(stats["en_kotu_tuketim"], 2)
            if stats.get("en_kotu_tuketim")
            else None,
            filo_karsilastirma=filo_karsilastirma,
            performans_puani=elite_score,
            trend=stats.get("trend", "stable"),
            guzergah_sayisi=stats.get("guzergah_sayisi", 0),
        )

        result.append(driver_stats)

    return result


async def compare_drivers(
    sofor_ids: Optional[List[int]] = None, uow: Optional[UnitOfWork] = None
) -> Dict:
    """
    Şoförleri karşılaştır ve sırala (async).

    Returns:
        {
            'en_verimli': DriverStats,
            'en_az_verimli': DriverStats,
            'filo_ortalama': float,
            'ranking': List[DriverStats]  # Sıralı (en iyiden kötüye)
        }
    """
    analiz_repo, _sofor_repo, _sefer_repo = _repos(uow)
    all_stats = await get_driver_stats(uow=uow)

    if sofor_ids:
        all_stats = [s for s in all_stats if s.sofor_id in sofor_ids]

    valid_stats = [s for s in all_stats if s.toplam_sefer >= 5 and s.ort_tuketim > 0]

    if not valid_stats:
        return {
            "en_verimli": None,
            "en_az_verimli": None,
            "filo_ortalama": 0.0,
            "ranking": [],
        }

    ranking = sorted(valid_stats, key=lambda x: x.performans_puani or 0.0, reverse=True)

    filo_ort = await analiz_repo.get_filo_ortalama_tuketim()

    return {
        "en_verimli": ranking[0] if ranking else None,
        "en_az_verimli": ranking[-1] if ranking else None,
        "filo_ortalama": filo_ort,
        "ranking": ranking,
    }


async def get_driver_trend(
    sofor_id: int, window: int = 10, uow: Optional[UnitOfWork] = None
) -> Dict:
    """
    Son N seferdeki trend analizi (async).

    Returns:
        {
            'trend': 'improving' | 'stable' | 'declining',
            'slope': float,
            'values': List[float],
            'moving_avg': List[float]
        }
    """
    _analiz_repo, sofor_repo, _sefer_repo = _repos(uow)
    tuketimler = await sofor_repo.get_yakit_tuketimi(sofor_id, limit=window * 2)
    values = [t["tuketim"] for t in reversed(tuketimler) if t.get("tuketim")]

    if len(values) < 5:
        return {
            "trend": "stable",
            "slope": 0.0,
            "values": values,
            "moving_avg": values,
        }

    trend = calculate_trend(values[-window:])

    moving_avg = []
    for i in range(len(values)):
        start = max(0, i - 2)
        end = i + 1
        moving_avg.append(round(mean(values[start:end]), 2))

    n = len(values[-window:])
    if n >= 3:
        x_mean = (n - 1) / 2
        y_mean = mean(values[-window:])

        numerator = sum((i - x_mean) * (values[-window:][i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator > 0 else 0
    else:
        slope = 0

    return {
        "trend": trend,
        "slope": round(slope, 4),
        "values": values,
        "moving_avg": moving_avg,
    }


async def get_route_performance(
    sofor_id: int, uow: Optional[UnitOfWork] = None
) -> List[Dict]:
    """
    Güzergah bazlı performans (async).

    Returns:
        [{
            'guzergah': str,
            'sefer_sayisi': int,
            'ort_tuketim': float,
            'en_iyi': float,
            'en_kotu': float,
            'fark': float  # Filo ortalamasına göre
        }]
    """
    analiz_repo, sofor_repo, _sefer_repo = _repos(uow)
    guzergahlar = await sofor_repo.get_guzergah_performansi(sofor_id)
    filo_ort = await analiz_repo.get_filo_ortalama_tuketim()

    result = []
    for g in guzergahlar:
        ort = g.get("ort_tuketim") or 0
        fark = (
            round(((filo_ort - ort) / filo_ort) * 100, 1)
            if filo_ort > 0 and ort > 0
            else 0
        )

        result.append(
            {
                "guzergah": g["guzergah"],
                "sefer_sayisi": g["sefer_sayisi"],
                "toplam_km": g.get("toplam_km", 0),
                "ort_tuketim": round(ort, 2),
                "en_iyi": round(g.get("en_iyi") or 0, 2),
                "en_kotu": round(g.get("en_kotu") or 0, 2),
                "fark": fark,
            }
        )

    return result


async def _calc_elite_from_trips(seferler: list) -> Optional[float]:
    """ML-deviation elite score (0-100) for the analytics dashboard.

    Scale: 0-100. Baseline 75 = exact match with ML prediction.
    Interpretation: >75 = driver consumes LESS than ML predicts (efficient),
    <75 = driver consumes MORE than ML predicts. Formula: +1.5 pts per 1%
    saving, -2.0 pts per 1% overage. Stored in `performans_puani` field.

    NOT comparable to: `calculate_performance_score` (fleet-average-based) or
    `calculate_hybrid_score` (0.1-2.0 ML correction factor).

    Batch path: pre-fetched trip list — DB-fetch part of
    `calculate_elite_performance_score` is skipped for N+1 prevention.
    """
    if not seferler:
        return None
    pred_service = get_prediction_service()
    sem = asyncio.Semaphore(5)

    async def safe_predict(trip):
        async with sem:
            try:
                actual = trip.get("tuketim")
                if not actual or actual <= 0:
                    return None
                pred = await pred_service.predict_consumption(
                    arac_id=trip["arac_id"],
                    mesafe_km=trip["mesafe_km"],
                    ton=float(trip.get("net_kg", 0)) / 1000.0,
                    ascent_m=trip.get("ascent_m", 0),
                    descent_m=trip.get("descent_m", 0),
                    sofor_id=trip.get("sofor_id"),
                )
                expected = pred.get("tahmini_tuketim", 0)
                if expected <= 0:
                    return None
                return ((actual - expected) / expected) * 100
            except Exception as e:
                logger.warning("Predict failed for elite score: %s", e)
                return None

    results = await asyncio.gather(*[safe_predict(t) for t in seferler])
    deviations = [r for r in results if r is not None]
    if not deviations:
        return None
    avg_dev = mean(deviations)
    if avg_dev < 0:
        score = 75 + (abs(avg_dev) * 1.5)
    else:
        score = 75 - (avg_dev * 2.0)
    return round(max(0, min(100, score)), 1)


async def calculate_elite_performance_score(
    sofor_id: int,
    baslangic: Optional[str] = None,
    bitis: Optional[str] = None,
    uow: Optional[UnitOfWork] = None,
) -> Optional[float]:
    """
    Elite Puanlama Algoritması.
    Sadece filo ortalaması değil, her sefer için 'Elite Prediction' ile 'Gerçek' arasındaki farkı baz alır.
    Bu sayede zor güzergahta çalışan şoför cezalandırılmaz.
    """
    from app.config import settings

    _analiz_repo, _sofor_repo, sefer_repo = _repos(uow)

    trip_limit = settings.ELITE_SCORE_TRIP_LIMIT
    seferler = await sefer_repo.get_all(
        filters={"sofor_id": sofor_id}, limit=trip_limit
    )
    if not seferler:
        return None

    pred_service = get_prediction_service()
    sem = asyncio.Semaphore(5)

    async def safe_predict(trip):
        async with sem:
            try:
                actual = trip.get("tuketim")
                if not actual or actual <= 0:
                    return None

                pred = await pred_service.predict_consumption(
                    arac_id=trip["arac_id"],
                    mesafe_km=trip["mesafe_km"],
                    ton=float(trip.get("net_kg", 0)) / 1000.0,
                    ascent_m=trip.get("ascent_m", 0),
                    descent_m=trip.get("descent_m", 0),
                    sofor_id=sofor_id,
                )

                expected = pred.get("tahmini_tuketim", 0)
                if expected <= 0:
                    return None

                return ((actual - expected) / expected) * 100
            except Exception as e:
                logger.warning(f"Predict failed for elite score: {e}")
                return None

    results = await asyncio.gather(*[safe_predict(t) for t in seferler])
    deviations = [r for r in results if r is not None]

    if not deviations:
        return None

    avg_dev = mean(deviations)

    if avg_dev < 0:
        score = 75 + (abs(avg_dev) * 1.5)
    else:
        score = 75 - (avg_dev * 2.0)

    return round(max(0, min(100, score)), 1)


def calculate_performance_score(
    ort_tuketim: float, filo_ort: float, sefer_sayisi: int
) -> float:
    """Fleet-comparison performance score (0-100) for report generation.

    Scale: 0-100. Baseline 50 = fleet average.
    Interpretation: >50 = below-average consumption (efficient), <50 = above-average.
    Used by `report_service` for driver reports — NOT used in the analytics dashboard
    (which uses the ML-deviation elite score via `_calc_elite_from_trips`).

    NOT comparable to: `calculate_hybrid_score` (0.1-2.0 ML factor) or the
    target-vs-actual score in `report_service._calculate_performance_score`.
    """
    if ort_tuketim <= 0 or filo_ort <= 0:
        return 50.0

    fark_puan = ((filo_ort - ort_tuketim) / filo_ort) * 200
    sefer_bonus = min(10, math.log10(max(1, sefer_sayisi)) * 5)
    puan = 50 + fark_puan + sefer_bonus

    return round(max(0, min(100, puan)), 1)


def calculate_trend(values: List[float]) -> str:
    """
    Trend yönü hesapla.

    Returns:
        'improving' | 'stable' | 'declining'
    """
    if len(values) < 5:
        return "stable"

    mid = len(values) // 2
    first_half = mean(values[:mid])
    second_half = mean(values[mid:])

    if first_half > 0:
        change = ((second_half - first_half) / first_half) * 100
    else:
        return "stable"

    if change < -5:
        return "improving"
    elif change > 5:
        return "declining"
    else:
        return "stable"
