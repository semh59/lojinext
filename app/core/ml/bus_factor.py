"""Feature E.7 — Bus Factor / risk yoğunlaşması.

En iyi N şoför ayrılırsa filo veriminin ne kadar düşeceğini hesaplar.
Heuristic: top-N şoförün medyandan açtığı puan farkı × yıllık km ×
loss_l_per_km × diesel_price → TL.

PII koruma (plan §15): top_n_drivers listesinde sadece `score` + `yearly_km`
döner; **ad/soyad/id yok**.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §10
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Sabitler (heuristic v1) ────────────────────────────────────────────
LOSS_L_PER_KM = 0.5  # her şoför 0.5 L/100km fark açabilir
MEDIAN_FALLBACK = 1.0  # rest boşsa Sofor.score nötr default

# Plan §10 risk threshold'ları
RISK_HIGH_TL = 200_000
RISK_MEDIUM_TL = 50_000


@dataclass
class BusFactorReport:
    top_n_drivers_loss_tl: float
    top_n_drivers: List[Dict[str, Any]] = field(default_factory=list)
    bottlenecked_routes: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = "low"  # "high" | "medium" | "low"
    n: int = 3


def _risk_level_for_loss(loss_tl: float) -> str:
    """Plan §10 threshold'ları."""
    if loss_tl > RISK_HIGH_TL:
        return "high"
    if loss_tl > RISK_MEDIUM_TL:
        return "medium"
    return "low"


def _median_score(rest_rows: List[Dict[str, Any]]) -> float:
    """Top-N dışında kalan şoförlerin medyan skoru."""
    if not rest_rows:
        return MEDIAN_FALLBACK
    sorted_scores = sorted(float(r["score"]) for r in rest_rows)
    mid = len(sorted_scores) // 2
    return sorted_scores[mid]


def _compute_loss_tl(
    top_n: List[Dict[str, Any]],
    median_score: float,
    diesel_price_tl: float,
) -> float:
    """Top-N ayrılırsa medyana kayan seferlerin verim kaybı."""
    loss_l = 0.0
    for r in top_n:
        gap = max(0.0, float(r["score"]) - median_score)
        loss_l += float(r["yearly_km"]) * gap * LOSS_L_PER_KM / 100.0
    return loss_l * diesel_price_tl


async def compute_bus_factor(
    uow,
    *,
    n: int = 3,
    diesel_price_tl: float = 50.0,
) -> BusFactorReport:
    """Top-N şoför ayrılırsa filo verim kaybını hesapla.

    Args:
        n: top-N şoför (default 3)
        diesel_price_tl: dizel L birim fiyat

    Returns:
        BusFactorReport — kayıp TL + top-N (PII'siz) + risk_level
    """
    from sqlalchemy import text

    rows = (
        (
            await uow.session.execute(
                text(
                    """
                WITH driver_perf AS (
                    SELECT s.id, s.score,
                        COALESCE(SUM(t.mesafe_km), 0) AS yearly_km
                    FROM soforler s
                    LEFT JOIN seferler t ON t.sofor_id = s.id
                        AND t.is_deleted = FALSE
                        AND t.tarih >= CURRENT_DATE - INTERVAL '365 days'
                    WHERE s.aktif = TRUE AND s.is_deleted = FALSE
                    GROUP BY s.id
                )
                SELECT * FROM driver_perf ORDER BY score DESC
                """
                )
            )
        )
        .mappings()
        .all()
    )

    if not rows:
        return BusFactorReport(
            top_n_drivers_loss_tl=0.0,
            top_n_drivers=[],
            bottlenecked_routes=[],
            risk_level="low",
            n=n,
        )

    top_n = [dict(r) for r in rows[:n]]
    rest = [dict(r) for r in rows[n:]]
    median = _median_score(rest)
    loss_tl = _compute_loss_tl(top_n, median, diesel_price_tl)

    return BusFactorReport(
        top_n_drivers_loss_tl=round(loss_tl, 0),
        # PII koruma: yalnız score + km (plan §15)
        top_n_drivers=[
            {
                "score": round(float(r["score"]), 2),
                "yearly_km": int(r["yearly_km"]),
            }
            for r in top_n
        ],
        bottlenecked_routes=[],  # v2'de eklenir (plan §10.1 yorum)
        risk_level=_risk_level_for_loss(loss_tl),
        n=n,
    )
