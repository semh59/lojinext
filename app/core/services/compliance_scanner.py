"""Feature E.4 — Compliance heatmap v1.

v1 scope: yalnız muayene tarihi takibi (araç + dorse).
v2 (deferred — backlog/2026-05-26-feature-m-takograf...):
    SRC belgesi, K1/K2/K3, tachograph AETR ihlalleri.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Literal

logger = logging.getLogger(__name__)

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


def _risk_for_days(days: int) -> RiskLevel:
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


async def scan_compliance(uow, *, days_horizon: int = 90) -> List[ComplianceItem]:
    """Önümüzdeki `days_horizon` gün içinde veya geçmiş muayeneleri tara.

    Args:
        days_horizon: bugünden N gün ileri pencere (default 90)

    Returns:
        ComplianceItem listesi, days_until ASC (önce overdue + en yakın)
    """
    from sqlalchemy import text

    today = date.today()
    horizon = today + timedelta(days=days_horizon)
    items: List[ComplianceItem] = []

    # Araç muayenesi
    arac_rows = (
        (
            await uow.session.execute(
                text(
                    """
                SELECT id, plaka, muayene_tarihi
                FROM araclar
                WHERE aktif = TRUE AND is_deleted = FALSE
                  AND muayene_tarihi IS NOT NULL
                  AND muayene_tarihi <= :horizon
                ORDER BY muayene_tarihi
                """
                ),
                {"horizon": horizon},
            )
        )
        .mappings()
        .all()
    )
    for r in arac_rows:
        days = (r["muayene_tarihi"] - today).days
        items.append(
            ComplianceItem(
                entity_type="arac",
                entity_id=int(r["id"]),
                plaka=str(r["plaka"]),
                field="muayene",
                expiry_date=r["muayene_tarihi"],
                days_until=days,
                risk_level=_risk_for_days(days),
            )
        )

    # Dorse muayenesi
    dorse_rows = (
        (
            await uow.session.execute(
                text(
                    """
                SELECT id, plaka, muayene_tarihi
                FROM dorseler
                WHERE aktif = TRUE AND is_deleted = FALSE
                  AND muayene_tarihi IS NOT NULL
                  AND muayene_tarihi <= :horizon
                ORDER BY muayene_tarihi
                """
                ),
                {"horizon": horizon},
            )
        )
        .mappings()
        .all()
    )
    for r in dorse_rows:
        days = (r["muayene_tarihi"] - today).days
        items.append(
            ComplianceItem(
                entity_type="dorse",
                entity_id=int(r["id"]),
                plaka=str(r["plaka"]),
                field="muayene",
                expiry_date=r["muayene_tarihi"],
                days_until=days,
                risk_level=_risk_for_days(days),
            )
        )

    return sorted(items, key=lambda x: x.days_until)
