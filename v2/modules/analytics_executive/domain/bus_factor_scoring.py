"""Feature E.7 — Bus Factor / risk yoğunlaşması, saf hesaplama (I/O yok).

PII koruma (plan §15): top_n_drivers listesinde sadece `score` + `yearly_km`
döner; **ad/soyad/id yok**.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §10
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

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


def risk_level_for_loss(loss_tl: float) -> str:
    """Plan §10 threshold'ları."""
    if loss_tl > RISK_HIGH_TL:
        return "high"
    if loss_tl > RISK_MEDIUM_TL:
        return "medium"
    return "low"


def median_score(rest_rows: List[Dict[str, Any]]) -> float:
    """Top-N dışında kalan şoförlerin medyan skoru."""
    if not rest_rows:
        return MEDIAN_FALLBACK
    sorted_scores = sorted(float(r["score"]) for r in rest_rows)
    mid = len(sorted_scores) // 2
    return sorted_scores[mid]


def compute_loss_tl(
    top_n: List[Dict[str, Any]],
    median: float,
    diesel_price_tl: float,
) -> float:
    """Top-N ayrılırsa medyana kayan seferlerin verim kaybı."""
    loss_l = 0.0
    for r in top_n:
        gap = max(0.0, float(r["score"]) - median)
        loss_l += float(r["yearly_km"]) * gap * LOSS_L_PER_KM / 100.0
    return loss_l * diesel_price_tl
