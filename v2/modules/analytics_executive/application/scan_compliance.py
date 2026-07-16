"""Use-case: muayene compliance heatmap taraması (E.4)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

from v2.modules.analytics_executive.domain.compliance_risk import (
    ComplianceItem,
    risk_for_days,
)


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
                risk_level=risk_for_days(days),
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
                risk_level=risk_for_days(days),
            )
        )

    return sorted(items, key=lambda x: x.days_until)
