"""Feature E.5 — Predictive cashflow projection (90 gün).

3 ana kalem aggregator:
  1. Yakıt: aktif planlı seferlerin (durum='Planned') tahmini_tuketim
     toplamı × diesel_price_tl
  2. Bakım: MaintenancePredictor.predict_all() çıktısından horizon içine
     düşen tahminler × avg bakım maliyeti (son 90g)
  3. Ceza: trailing 90g ortalama (placeholder=0; cezalar tablosu yoksa)

Haftalık breakdown (default 12 hafta) + toplam + assumptions.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


@dataclass
class CashflowWeek:
    week_start: date
    fuel_tl: float
    maintenance_tl: float
    # None ise ceza tablosu yok (frontend "—" gösterir); 0 ise hesaplandı.
    penalty_tl: Optional[float]
    total_tl: float


@dataclass
class CashflowProjection:
    horizon_days: int
    weeks: List[CashflowWeek] = field(default_factory=list)
    total_fuel_tl: float = 0.0
    total_maintenance_tl: float = 0.0
    total_penalty_tl: Optional[float] = None
    # True ise ceza tablosu (cezalar) DB'de var; False ise placeholder yok
    # (UI total'a dahil etmemeli, "—" göstermeli).
    penalty_data_available: bool = False
    grand_total_tl: float = 0.0
    confidence: float = 0.65
    assumptions: Dict[str, float] = field(default_factory=dict)


async def project_cashflow(
    uow,
    *,
    horizon_days: int = 90,
    diesel_price_tl: float = 50.0,
    avg_bakim_cost_fallback_tl: float = 5000.0,
    predictor: Optional[Any] = None,
) -> CashflowProjection:
    """3 kalem 12 haftalık projeksiyon.

    Args:
        horizon_days: ileri pencere (default 90; min 7, max 365)
        diesel_price_tl: dizel L birim fiyat (settings.LITRE_DIESEL_TL'den)
        avg_bakim_cost_fallback_tl: son 90g'de bakım yoksa varsayım
        predictor: MaintenancePredictor instance; None → varsayılan yeni
            instance. Test'lerde mock geçirilebilir.

    Returns:
        CashflowProjection — haftalık breakdown + toplam + assumptions.
    """
    from sqlalchemy import text

    if horizon_days < 7:
        horizon_days = 7
    horizon_days = min(horizon_days, 365)

    # 1. Yakıt: aktif planlı seferler
    fuel_sql = """
        SELECT tarih, COALESCE(SUM(tahmini_tuketim), 0) AS total_l
        FROM seferler
        WHERE is_deleted = FALSE
          AND durum = 'Planned'
          AND tarih BETWEEN CURRENT_DATE
              AND CURRENT_DATE + (:h * INTERVAL '1 day')
        GROUP BY tarih
        ORDER BY tarih
    """
    fuel_rows = (
        (await uow.session.execute(text(fuel_sql), {"h": horizon_days}))
        .mappings()
        .all()
    )

    # 2. Avg bakım maliyeti (son 90g)
    avg_cost_row = (
        (
            await uow.session.execute(
                text(
                    """
                SELECT AVG(maliyet) AS avg_cost
                FROM arac_bakimlari
                WHERE tamamlandi = TRUE
                  AND bakim_tarihi >= CURRENT_DATE - INTERVAL '90 days'
                """
                )
            )
        )
        .mappings()
        .one()
    )
    avg_bakim = (
        float(avg_cost_row["avg_cost"])
        if avg_cost_row.get("avg_cost") is not None
        else float(avg_bakim_cost_fallback_tl)
    )

    # 3. MaintenancePredictor — yeni instance veya parametre ile gelen
    if predictor is None:
        from v2.modules.fleet.public import MaintenancePredictor

        predictor = MaintenancePredictor()
    try:
        preds = await predictor.predict_all()
    except Exception as exc:
        logger.warning("MaintenancePredictor failed in cashflow: %s", exc)
        preds = []

    today = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Istanbul")).date()
    horizon_end = today + timedelta(days=horizon_days)
    upcoming_bakim = [
        p
        for p in preds
        if getattr(p, "predictable", False)
        and getattr(p, "predicted_date", None) is not None
        and today <= p.predicted_date <= horizon_end
    ]

    # 4. Ceza projeksiyonu — cezalar (trafik/idari) tablosu henüz şemada yok.
    # placeholder=0 yerine None ile "veri yok" sinyali veriyoruz; UI bu
    # bilgiyle hücreyi "—" gösterir ve grand_total'a dahil etmez.
    # Tablo (cezalar) eklendiğinde burada trailing 90g ortalama hesaplanır.
    penalty_data_available = False
    week_penalty_tl: Optional[float] = None

    # 5. Haftalık breakdown — tavan bölme ile kalan günler son haftaya dahil
    weeks_count = max(1, (horizon_days + 6) // 7)
    horizon_end = today + timedelta(days=horizon_days)
    fuel_by_date: Dict[date, float] = {}
    for r in fuel_rows:
        d = r["tarih"]
        fuel_by_date[d] = float(r["total_l"] or 0)

    weeks: List[CashflowWeek] = []
    for w in range(weeks_count):
        week_start = today + timedelta(days=w * 7)
        week_end = min(week_start + timedelta(days=7), horizon_end)
        week_fuel_l = sum(
            litres for d, litres in fuel_by_date.items() if week_start <= d < week_end
        )
        week_fuel_tl = week_fuel_l * diesel_price_tl
        week_bakim_count = sum(
            1 for p in upcoming_bakim if week_start <= p.predicted_date < week_end
        )
        week_bakim_tl = week_bakim_count * avg_bakim
        week_total_tl = week_fuel_tl + week_bakim_tl  # penalty None → toplam dışı
        weeks.append(
            CashflowWeek(
                week_start=week_start,
                fuel_tl=round(week_fuel_tl, 0),
                maintenance_tl=round(week_bakim_tl, 0),
                penalty_tl=week_penalty_tl,
                total_tl=round(week_total_tl, 0),
            )
        )

    total_fuel = sum(w.fuel_tl for w in weeks)
    total_bakim = sum(w.maintenance_tl for w in weeks)
    total_penalty: Optional[float] = None  # cezalar tablosu yokken None

    return CashflowProjection(
        horizon_days=horizon_days,
        weeks=weeks,
        total_fuel_tl=round(total_fuel, 0),
        total_maintenance_tl=round(total_bakim, 0),
        total_penalty_tl=total_penalty,
        penalty_data_available=penalty_data_available,
        grand_total_tl=round(total_fuel + total_bakim, 0),
        confidence=0.65,
        assumptions={
            "diesel_price_tl": round(diesel_price_tl, 2),
            "avg_bakim_cost_tl": round(avg_bakim, 0),
            "weeks_count": float(weeks_count),
            "upcoming_bakim_count": float(len(upcoming_bakim)),
        },
    )
