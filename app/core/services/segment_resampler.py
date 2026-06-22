"""500m segment resampler (Phase 1.3).

Mapbox Directions'ın ham segment'leri Türkiye'de avg 30-100m (Phase 0.1
ölçüm: otoyol 82m, şehir 33m, dağlık 106m) — bu kadar granular UI'a fazla
ve simulator'da gereksiz CPU yükü.

Resampler: ham segment listesini sabit `target_length_km` parçalara
böler (default 500m). Her bucket'ın attribute'ları:
  - length_km: bucket'a düşen kümülatif uzunluk (son bucket route sonu
    olduğu için 500m'den az olabilir)
  - grade_pct: overlap-weighted ortalama
  - road_class: overlap-weighted mode (en uzun süre içeren class)
  - maxspeed_kmh / traffic_speed_kmh: overlap-weighted ortalama
    (None değerler atlanır)
  - congestion: overlap-weighted mode

Geometry coords da resample edilir — her bucket boundary için (N+1 nokta
N bucket için) doğrusal interpolate edilir. Phase 1.4'te Open-Meteo
elevation enrichment bu coord'lara çağrılır, grade hesabı boundary
elevation deltasından doldurulur (bucket içi raw segment'lerden ortalama
yerine).
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Sequence, Tuple

from app.core.ml.segment_simulator import SegmentInput

_DEFAULT_TARGET_KM = 0.5


def resample_segments(
    segments: Sequence[SegmentInput],
    coords: Sequence[Tuple[float, float]],
    target_length_km: float = _DEFAULT_TARGET_KM,
) -> Tuple[List[SegmentInput], List[Tuple[float, float]]]:
    """Ham segmentleri sabit target_length parçalara yeniden böl.

    Args:
        segments: Ham SegmentInput listesi (Mapbox extract'tan).
        coords: N+1 geometry koordinatı (segments için boundary'ler).
        target_length_km: Hedef bucket uzunluğu (default 500m).

    Returns:
        (resampled_segments, resampled_coords). resampled_coords M+1 nokta
        (M bucket için).
    """
    if not segments:
        return [], list(coords)
    if target_length_km <= 0:
        raise ValueError("target_length_km must be > 0")

    # Cumulative km @ input segment boundary'leri
    cum: List[float] = [0.0]
    for s in segments:
        cum.append(cum[-1] + max(0.0, s.length_km))
    total_km = cum[-1]
    if total_km <= 0:
        return [], list(coords)

    # Bucket boundary'leri: 0, target, 2*target, ..., total
    bucket_boundaries: List[float] = []
    k = 0.0
    while k < total_km - 1e-9:
        bucket_boundaries.append(k)
        k += target_length_km
    bucket_boundaries.append(total_km)
    # Bucket sayısı = len(boundaries) - 1

    resampled: List[SegmentInput] = []
    for b_i in range(len(bucket_boundaries) - 1):
        b_start = bucket_boundaries[b_i]
        b_end = bucket_boundaries[b_i + 1]
        bucket = _aggregate_bucket(segments, cum, b_start, b_end)
        if bucket is not None:
            resampled.append(bucket)

    # Boundary coordinates: her bucket boundary için interpolate
    if len(coords) >= 2 and len(cum) == len(coords):
        resampled_coords = [
            _interpolate_coord(coords, cum, k) for k in bucket_boundaries
        ]
    else:
        resampled_coords = list(coords)

    return resampled, resampled_coords


def _aggregate_bucket(
    segments: Sequence[SegmentInput],
    cum: List[float],
    b_start: float,
    b_end: float,
) -> Optional[SegmentInput]:
    """Bucket [b_start, b_end] aralığındaki segment overlap'lerinden SegmentInput üret."""
    if b_end <= b_start:
        return None

    # Overlap'lı segment'leri topla (overlap_km, seg)
    overlaps: List[Tuple[float, SegmentInput]] = []
    for i, seg in enumerate(segments):
        seg_start = cum[i]
        seg_end = cum[i + 1]
        ov_start = max(seg_start, b_start)
        ov_end = min(seg_end, b_end)
        ov = ov_end - ov_start
        if ov > 1e-9:
            overlaps.append((ov, seg))

    if not overlaps:
        return None

    total_ov = sum(o for o, _ in overlaps)

    # Numeric: overlap-weighted avg, None değerleri ağırlık dağıtımına dahil etme
    def _weighted_avg(getter) -> Optional[float]:
        num = 0.0
        wsum = 0.0
        for ov, s in overlaps:
            v = getter(s)
            if v is not None:
                num += v * ov
                wsum += ov
        return (num / wsum) if wsum > 0 else None

    grade_pct = _weighted_avg(lambda s: s.grade_pct) or 0.0
    maxspeed_kmh = _weighted_avg(lambda s: s.maxspeed_kmh)
    traffic_speed_kmh = _weighted_avg(lambda s: s.traffic_speed_kmh)

    # Categorical: mode by overlap weight
    road_class = _weighted_mode(overlaps, lambda s: s.road_class)
    congestion = _weighted_mode(overlaps, lambda s: s.congestion) or "low"

    return SegmentInput(
        length_km=round(total_ov, 6),
        grade_pct=grade_pct,
        road_class=road_class or "",
        maxspeed_kmh=maxspeed_kmh,
        traffic_speed_kmh=traffic_speed_kmh,
        congestion=congestion,
    )


def _weighted_mode(overlaps: List[Tuple[float, SegmentInput]], getter) -> Optional[str]:
    weights: dict[str, float] = defaultdict(float)
    for ov, s in overlaps:
        key = getter(s)
        if not key:
            continue
        weights[key] += ov
    if not weights:
        return None
    return max(weights.items(), key=lambda kv: kv[1])[0]


def _interpolate_coord(
    coords: Sequence[Tuple[float, float]], cum: List[float], target_km: float
) -> Tuple[float, float]:
    """target_km'ye karşılık gelen koordinatı geometry boundary'leri üzerinden interpolate et."""
    if target_km <= cum[0]:
        return coords[0]
    if target_km >= cum[-1]:
        return coords[-1]
    # cum monoton artıyor — binary search
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= target_km:
            lo = mid
        else:
            hi = mid
    span = cum[hi] - cum[lo]
    if span <= 0:
        return coords[lo]
    t = (target_km - cum[lo]) / span
    lon_lo, lat_lo = coords[lo]
    lon_hi, lat_hi = coords[hi]
    return (lon_lo + (lon_hi - lon_lo) * t, lat_lo + (lat_hi - lat_lo) * t)


__all__ = ["resample_segments"]
