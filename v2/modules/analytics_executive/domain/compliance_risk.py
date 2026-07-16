"""Feature E.4 — Compliance heatmap v1, saf risk sınıflandırması (I/O yok).

v1 scope: yalnız muayene tarihi takibi (araç + dorse).
v2 (deferred — backlog/2026-05-26-feature-m-takograf...):
    SRC belgesi, K1/K2/K3, tachograph AETR ihlalleri.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §7
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

EntityType = Literal["arac", "dorse"]
RiskLevel = Literal["overdue", "soon", "normal", "low"]


@dataclass
class ComplianceItem:
    entity_type: EntityType
    entity_id: int
    plaka: str
    field: str  # "muayene" (v1'de sadece bu)
    expiry_date: date
    days_until: int  # negatif = geçmiş; pozitif = gelecek
    risk_level: RiskLevel


def risk_for_days(days: int) -> RiskLevel:
    """Plan §7.2 sınırları:
    < 0  → overdue
    0-14 → soon
    15-60→ normal
    60+  → low
    """
    if days < 0:
        return "overdue"
    if days <= 14:
        return "soon"
    if days <= 60:
        return "normal"
    return "low"
