"""Reports v2 RV2.2 — Period-over-period filo karşılaştırma.

Bu period (week/month) vs geçen period için 3 kalem:
  - Toplam yakıt L (yakit_avg × sefer × mesafe)
  - Toplam tahmini maliyet (yakıt × diesel)
  - Açık anomali sayısı (severity > low)

Saf yardımcı: _delta_pct (bölme sıfıra karşı güvenli).

Plan kaynağı: docs/superpowers/plans/2026-05-27-reports-v2-mvp-v3.md §4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

logger = logging.getLogger(__name__)

PeriodType = Literal["week", "month"]


@dataclass
class PeriodMetrics:
    """Tek period için aggregat KPI'lar."""

    fuel_l: float
    fuel_cost_tl: float
    anomaly_count: int
    trip_count: int


@dataclass
class FleetComparison:
    period: PeriodType
    current: PeriodMetrics
    previous: PeriodMetrics
    fuel_l_delta_pct: Optional[float]
    fuel_cost_delta_pct: Optional[float]
    anomaly_delta_pct: Optional[float]
    trip_delta_pct: Optional[float]
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date


def _delta_pct(current: float, previous: float) -> Optional[float]:
    """Yüzdesel değişim. previous=0 → None (anlamsız)."""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _period_dates(period: PeriodType) -> tuple[date, date, date, date]:
    """Mevcut + önceki period'un başlangıç/bitiş tarihleri."""
    today = date.today()
    if period == "week":
        current_start = today - timedelta(days=7)
        current_end = today
        previous_start = today - timedelta(days=14)
        previous_end = today - timedelta(days=7)
    else:  # month
        current_start = today - timedelta(days=30)
        current_end = today
        previous_start = today - timedelta(days=60)
        previous_end = today - timedelta(days=30)
    return current_start, current_end, previous_start, previous_end


async def _fetch_metrics(
    uow,
    *,
    start: date,
    end: date,
    diesel_price_tl: float,
) -> PeriodMetrics:
    """Tek period için aggregat."""
    from sqlalchemy import text

    sql = """
        SELECT
            COALESCE(SUM(s.tuketim), 0) AS fuel_l,
            COUNT(*) AS trip_count,
            (
                SELECT COUNT(*) FROM anomalies
                WHERE tarih BETWEEN :start AND :end
                  AND severity IN ('critical', 'high', 'medium')
                  AND resolved_at IS NULL
            ) AS anomaly_count
        FROM seferler s
        WHERE s.is_deleted = FALSE
          AND s.tarih BETWEEN :start AND :end
          AND s.durum = 'Completed'
    """
    row = (
        (await uow.session.execute(text(sql), {"start": start, "end": end}))
        .mappings()
        .one()
    )
    fuel_l = float(row.get("fuel_l") or 0)
    return PeriodMetrics(
        fuel_l=fuel_l,
        fuel_cost_tl=round(fuel_l * diesel_price_tl, 0),
        anomaly_count=int(row.get("anomaly_count") or 0),
        trip_count=int(row.get("trip_count") or 0),
    )


async def compute_fleet_comparison(
    uow,
    *,
    period: PeriodType = "month",
    diesel_price_tl: float = 50.0,
) -> FleetComparison:
    """Bu periyot vs geçen periyot için 4 metrik delta'sı."""
    cs, ce, ps, pe = _period_dates(period)
    current = await _fetch_metrics(
        uow, start=cs, end=ce, diesel_price_tl=diesel_price_tl
    )
    previous = await _fetch_metrics(
        uow, start=ps, end=pe, diesel_price_tl=diesel_price_tl
    )
    return FleetComparison(
        period=period,
        current=current,
        previous=previous,
        fuel_l_delta_pct=_delta_pct(current.fuel_l, previous.fuel_l),
        fuel_cost_delta_pct=_delta_pct(current.fuel_cost_tl, previous.fuel_cost_tl),
        anomaly_delta_pct=_delta_pct(current.anomaly_count, previous.anomaly_count),
        trip_delta_pct=_delta_pct(current.trip_count, previous.trip_count),
        current_start=cs,
        current_end=ce,
        previous_start=ps,
        previous_end=pe,
    )
