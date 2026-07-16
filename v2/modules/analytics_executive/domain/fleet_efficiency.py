"""Feature E.1 — Filo Verimliliği Endeksi (FVI), saf hesaplama (I/O yok).

4 alt-skorun ağırlıklı ortalaması; tek 0-100 sayı + alt-skor breakdown +
trend + confidence + insan-okur sebep listesi.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

# ── Sabitler ────────────────────────────────────────────────────────────
SUBSCORE_WEIGHTS: dict[str, float] = {
    "fuel": 0.35,
    "maintenance": 0.25,
    "driver": 0.25,
    "anomaly_quality": 0.15,
}
COLD_START_DEFAULT = 75.0  # her alt-skor için "veri yok" nötr
FUEL_DEVIATION_CAP = 0.30  # ±%30 sapma → 0-100 normalize edilir


# ── Veri sınıfı ────────────────────────────────────────────────────────
@dataclass
class FleetEfficiencyBreakdown:
    """Alt-skor + toplam endeks + trend + confidence + sebep listesi."""

    fvi: float  # 0-100
    fuel_score: float  # 0-100
    maintenance_score: float  # 0-100
    driver_score: float  # 0-100
    anomaly_quality_score: float  # 0-100
    confidence: float  # 0-1 (kaç sinyal cold-start değil)
    trend_30d: Optional[float] = None  # geçen aya göre delta
    reasons: List[str] = field(default_factory=list)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Saf yardımcılar (DB yok, test edilebilir) ──────────────────────────
def _fuel_score(
    avg_l_100km: Optional[float], target: Optional[float]
) -> tuple[float, str]:
    """Filo ortalaması hedeften ne kadar sapıyor?

    Düşük tüketim = yüksek skor. ±%30 cap'i ile linear normalize.
    Cold-start: ortalama veya hedef None ise 75 nötr.
    """
    if avg_l_100km is None or target is None or target <= 0:
        return COLD_START_DEFAULT, "Yetersiz yakıt verisi (cold-start)"
    dev = (avg_l_100km - target) / target
    clamped = max(-FUEL_DEVIATION_CAP, min(FUEL_DEVIATION_CAP, dev))
    # [-0.3, 0.3] → [100, 0]
    score = 100 * (1 - (clamped + FUEL_DEVIATION_CAP) / (2 * FUEL_DEVIATION_CAP))
    return round(score, 1), (f"Filo ort. {avg_l_100km:.1f} L/100km, hedef {target:.1f}")


def _maintenance_score(overdue_count: int, total_active: int) -> tuple[float, str]:
    """Bakımı geciken araç oranı düşük = skor yüksek."""
    if total_active <= 0:
        return COLD_START_DEFAULT, "Aktif araç yok"
    score = 100 * (1 - overdue_count / total_active)
    return round(max(0.0, min(100.0, score)), 1), (
        f"{overdue_count}/{total_active} araç bakım gecikmiş"
    )


def _driver_score(avg_hybrid: Optional[float]) -> tuple[float, str]:
    """Sofor.score 0.1-2.0 aralığında; 1.0 = nötr, 2.0 = mükemmel.

    Normalize: [0.5, 2.0] → [0, 100]. 0.5 altı clamp 0.
    """
    if avg_hybrid is None:
        return COLD_START_DEFAULT, "Şoför skor verisi yok"
    score = max(0.0, min(100.0, (avg_hybrid - 0.5) * 100 / 1.5))
    return round(score, 1), f"Filo şoför avg skor: {avg_hybrid:.2f}"


def _anomaly_quality_score(
    resolved: int, acknowledged: int, total: int
) -> tuple[float, str]:
    """Resolved + ack'lenmiş oranı / total. Düşük = aksiyon alınmıyor."""
    if total <= 0:
        return COLD_START_DEFAULT, "Son 30 günde anomali yok"
    score = 100 * (resolved + acknowledged) / total
    return round(max(0.0, min(100.0, score)), 1), (
        f"{resolved + acknowledged}/{total} anomali aksiyon almış (30g)"
    )


def compute_fvi(
    *,
    fuel_avg: Optional[float],
    fuel_target: Optional[float],
    overdue_maintenance: int,
    total_active_vehicles: int,
    driver_avg_hybrid: Optional[float],
    resolved_anomalies: int,
    acked_anomalies: int,
    total_anomalies: int,
    previous_fvi: Optional[float] = None,
) -> FleetEfficiencyBreakdown:
    """Tüm alt-skorları hesaplayıp weighted average ile FVI üret."""
    f_score, f_reason = _fuel_score(fuel_avg, fuel_target)
    m_score, m_reason = _maintenance_score(overdue_maintenance, total_active_vehicles)
    d_score, d_reason = _driver_score(driver_avg_hybrid)
    a_score, a_reason = _anomaly_quality_score(
        resolved_anomalies, acked_anomalies, total_anomalies
    )

    fvi = round(
        SUBSCORE_WEIGHTS["fuel"] * f_score
        + SUBSCORE_WEIGHTS["maintenance"] * m_score
        + SUBSCORE_WEIGHTS["driver"] * d_score
        + SUBSCORE_WEIGHTS["anomaly_quality"] * a_score,
        1,
    )

    # Confidence: kaç alt-skor cold-start değil?
    real_signals = sum(
        1 for s in (f_score, m_score, d_score, a_score) if s != COLD_START_DEFAULT
    )
    confidence = round(real_signals / 4, 2)

    trend = None
    if previous_fvi is not None:
        trend = round(fvi - previous_fvi, 1)

    return FleetEfficiencyBreakdown(
        fvi=fvi,
        fuel_score=f_score,
        maintenance_score=m_score,
        driver_score=d_score,
        anomaly_quality_score=a_score,
        confidence=confidence,
        trend_30d=trend,
        reasons=[f_reason, m_reason, d_reason, a_reason],
    )
