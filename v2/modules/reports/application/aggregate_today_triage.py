"""Reports v2 RV2.1 — Today/Triage aggregator.

Bugünün acil + bekleyen aksiyonlarını çoklu kaynaktan toplar:
  - Açık anomaliler (resolved_at IS NULL, son 7g)
  - Bakım gecikmeli + 7g içinde olan (D.1 predictions)
  - Açık fuel investigation (B)
  - Aktif sefer sayısı (sadece counter)
  - Bugün tamamlanan sefer sayısı (sadece counter)

Priority sıralama: severity (critical->low) -> timestamp DESC.

Plan kaynağı: docs/superpowers/plans/2026-05-27-reports-v2-mvp-v3.md §3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


SEVERITY_RANK: Dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


TriageCategory = Literal[
    "anomaly", "maintenance", "investigation", "telegram_approval", "active_trip"
]
TriageSeverity = Literal["critical", "high", "medium", "low"]
TriageActionType = Literal["navigate", "modal", "external"]


@dataclass
class TriageAction:
    label: str
    url: str
    action_type: TriageActionType = "navigate"


@dataclass
class TriageItem:
    id: str
    category: TriageCategory
    severity: TriageSeverity
    title: str
    subtitle: str
    timestamp: datetime
    plaka: Optional[str] = None
    actions: List[TriageAction] = field(default_factory=list)


@dataclass
class TodayTriage:
    critical_count: int
    pending_count: int
    items: List[TriageItem] = field(default_factory=list)
    active_trips_count: int = 0
    completed_today_count: int = 0
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Saf yardımcılar ────────────────────────────────────────────────────
def _map_anomaly_severity(raw: Optional[str]) -> TriageSeverity:
    """Anomaly.severity -> TriageSeverity (Literal)."""
    if not raw:
        return "low"
    s = raw.lower()
    if s == "critical":
        return "critical"
    if s == "high":
        return "high"
    if s == "medium":
        return "medium"
    return "low"


def _map_maintenance_risk(risk_level: Optional[str]) -> TriageSeverity:
    """D.1 risk_level (overdue/soon/normal/low) -> TriageSeverity."""
    mapping: Dict[str, TriageSeverity] = {
        "overdue": "critical",
        "soon": "high",
        "normal": "medium",
        "low": "low",
    }
    if not risk_level:
        return "low"
    return mapping.get(risk_level, "low")


def _sort_items(items: List[TriageItem]) -> List[TriageItem]:
    """Priority: severity ASC (critical önce), timestamp DESC (yeni önce)."""
    return sorted(
        items,
        key=lambda i: (SEVERITY_RANK.get(i.severity, 99), -i.timestamp.timestamp()),
    )


# ── Aggregator ────────────────────────────────────────────────────────
async def aggregate_today_triage(
    uow,
    *,
    limit: int = 50,
    lookback_days: int = 7,
) -> TodayTriage:
    """Çoklu kaynaktan triage items aggregat'ı.

    Args:
        uow: UnitOfWork instance
        limit: max item sayısı (plan §3 default 50)
        lookback_days: anomaly window (default 7)

    Returns:
        TodayTriage — items priority sıralı, counts dolu.
    """
    from sqlalchemy import text

    items: List[TriageItem] = []

    # 1. Açık anomaliler
    try:
        anomaly_rows = (
            (
                await uow.session.execute(
                    text(
                        """
                    SELECT a.id, a.severity, a.tip, a.sapma_yuzde, a.tarih,
                        a.created_at, a.aciklama,
                        COALESCE(v.plaka, NULL) AS plaka
                    FROM anomalies a
                    LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer'
                        AND a.kaynak_id = sf.id
                    LEFT JOIN araclar v ON
                        (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                        OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
                    WHERE a.resolved_at IS NULL
                      AND a.tarih >= CURRENT_DATE
                          - (:lookback * INTERVAL '1 day')
                    ORDER BY a.created_at DESC
                    LIMIT :limit
                    """
                    ),
                    {"lookback": lookback_days, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        for r in anomaly_rows:
            ts = r.get("created_at") or datetime.combine(
                r["tarih"], datetime.min.time(), tzinfo=timezone.utc
            )
            sapma = r.get("sapma_yuzde")
            sapma_str = f"%{sapma:.1f}" if sapma is not None else ""
            items.append(
                TriageItem(
                    id=f"anomaly:{r['id']}",
                    category="anomaly",
                    severity=_map_anomaly_severity(r.get("severity")),
                    title=f"{r.get('tip', 'Anomali')} {sapma_str}".strip(),
                    subtitle=str(r.get("aciklama") or "")[:200],
                    timestamp=ts,
                    plaka=r.get("plaka"),
                    actions=[
                        TriageAction(label="İncele", url=f"/alerts?id={r['id']}"),
                    ],
                )
            )
    except Exception as exc:
        logger.warning("Triage anomaly fetch failed: %s", exc)

    # 2. Bakım gecikmeli/yakın (D.1)
    try:
        from v2.modules.fleet.public import MaintenancePredictor

        preds = await MaintenancePredictor().predict_all()
        today = date.today()
        for p in preds:
            if not getattr(p, "predictable", False):
                continue
            if not p.predicted_date:
                continue
            days_remaining = (p.predicted_date - today).days
            # Sadece kritik veya yakın: overdue (negatif) ya da <= 7 gün
            if days_remaining > 7:
                continue
            items.append(
                TriageItem(
                    id=f"maintenance:{p.arac_id}",
                    category="maintenance",
                    severity=_map_maintenance_risk(p.risk_level),
                    title=f"{p.bakim_tipi} bakım "
                    + (
                        "gecikti"
                        if days_remaining < 0
                        else f"{days_remaining} gün kaldı"
                    ),
                    subtitle=f"Güven: %{int(p.confidence * 100)}",
                    timestamp=datetime.combine(
                        p.predicted_date, datetime.min.time(), tzinfo=timezone.utc
                    ),
                    plaka=p.plaka,
                    actions=[
                        TriageAction(
                            label="Planla",
                            url=f"/maintenance?arac_id={p.arac_id}",
                        ),
                    ],
                )
            )
    except Exception as exc:
        logger.warning("Triage maintenance fetch failed: %s", exc)

    # 3. Açık fuel investigation (B)
    try:
        inv_rows = (
            (
                await uow.session.execute(
                    text(
                        """
                    SELECT i.id, i.suspicion_level, i.suspicion_score,
                        i.created_at,
                        COALESCE(v.plaka, NULL) AS plaka,
                        a.sapma_yuzde
                    FROM fuel_investigations i
                    JOIN anomalies a ON i.anomaly_id = a.id
                    LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer'
                        AND a.kaynak_id = sf.id
                    LEFT JOIN araclar v ON
                        (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                        OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
                    WHERE i.status IN ('open', 'assigned', 'investigating')
                    ORDER BY i.created_at DESC
                    LIMIT 20
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        for r in inv_rows:
            severity: TriageSeverity = (
                "critical"
                if r.get("suspicion_level") == "high"
                else "high"
                if r.get("suspicion_level") == "medium"
                else "medium"
            )
            score = r.get("suspicion_score")
            score_str = f" — skor {score:.2f}" if score is not None else ""
            items.append(
                TriageItem(
                    id=f"investigation:{r['id']}",
                    category="investigation",
                    severity=severity,
                    title=f"Şüpheli yakıt soruşturması{score_str}",
                    subtitle=(
                        f"Sapma %{r['sapma_yuzde']:.1f}"
                        if r.get("sapma_yuzde") is not None
                        else ""
                    ),
                    timestamp=r["created_at"] or datetime.now(timezone.utc),
                    plaka=r.get("plaka"),
                    actions=[
                        TriageAction(
                            label="Detay",
                            url=f"/alerts?inv={r['id']}",
                        ),
                    ],
                )
            )
    except Exception as exc:
        logger.warning("Triage investigation fetch failed: %s", exc)

    # 4. Aktif trip sayısı (counter)
    active_count = 0
    completed_count = 0
    try:
        counts_row = (
            (
                await uow.session.execute(
                    text(
                        """
                    SELECT
                        COUNT(*) FILTER (WHERE durum = 'Planned') AS active,
                        COUNT(*) FILTER (
                            WHERE durum = 'Completed'
                            AND tarih = CURRENT_DATE
                        ) AS completed_today
                    FROM seferler WHERE is_deleted = FALSE
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
        active_count = int(counts_row.get("active") or 0)
        completed_count = int(counts_row.get("completed_today") or 0)
    except Exception as exc:
        logger.warning("Triage trip counters failed: %s", exc)

    # 5. Sıralama + limit
    sorted_items = _sort_items(items)[:limit]
    critical_count = sum(1 for i in sorted_items if i.severity == "critical")
    pending_count = len(sorted_items) - critical_count

    return TodayTriage(
        critical_count=critical_count,
        pending_count=pending_count,
        items=sorted_items,
        active_trips_count=active_count,
        completed_today_count=completed_count,
    )
