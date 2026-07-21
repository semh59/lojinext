"""Maliyet analizi use-case'leri (dalga 11 — B.1: eski `CostAnalyzer` sınıfı
kaldırıldı, `location`/`notification`/`fleet`/`fuel`/`driver`/`auth_rbac`
ile aynı gerekçe — constructor `pass` idi, hiçbir gerçek state taşımıyordu).

Kaynak-destekli hesaplama ilkesi (davranış değişmedi): eksik yakıt/sefer
verisi varsa ROI/tasarruf sayıları uydurulmaz, `{"error": ...}` döner.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from app.infrastructure.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.shared_kernel.utils.clock import current_date

logger = get_logger(__name__)


@dataclass
class CostBreakdown:
    """Normalized cost breakdown for a date window."""

    fuel_cost: Decimal
    fuel_liters: float
    avg_price_per_liter: Decimal
    trip_count: int
    total_distance: float
    cost_per_km: Decimal
    period_start: date
    period_end: date


async def calculate_period_cost(
    start_date: date, end_date: date, arac_id: Optional[int] = None
) -> CostBreakdown:
    """Calculate source-backed cost totals for a period."""
    async with UnitOfWork() as uow:
        fuel_records = await uow.yakit_repo.get_by_date_range(
            start_date.isoformat(), end_date.isoformat(), arac_id
        )

        total_cost = Decimal("0")
        total_liters = 0.0

        for record in fuel_records:
            total_cost += Decimal(str(record.get("toplam_tutar", 0) or 0))
            total_liters += float(record.get("litre", 0) or 0)

        trips = await uow.sefer_repo.get_by_date_range(
            start_date.isoformat(), end_date.isoformat(), arac_id
        )

        total_distance = sum(float(t.get("mesafe_km", 0) or 0) for t in trips)
        trip_count = len(trips)

        avg_price = (
            total_cost / Decimal(str(total_liters))
            if total_liters > 0
            else Decimal("0")
        )
        cost_per_km = (
            total_cost / Decimal(str(total_distance))
            if total_distance > 0
            else Decimal("0")
        )

        return CostBreakdown(
            fuel_cost=round(total_cost, 2),
            fuel_liters=round(total_liters, 1),
            avg_price_per_liter=round(avg_price, 2),
            trip_count=trip_count,
            total_distance=round(total_distance, 1),
            cost_per_km=round(cost_per_km, 2),
            period_start=start_date,
            period_end=end_date,
        )


async def get_monthly_trend(months: int = 12) -> List[Dict]:
    """Return the monthly cost trend using repository aggregates."""
    async with UnitOfWork() as uow:
        raw_stats = await uow.analiz_repo.get_bulk_cost_stats(months=months)

        trends = []
        for row in raw_stats:
            month_key = row["ay"]
            fuel_cost = Decimal(str(row["yakit_tl"] or 0))
            total_distance = float(row["toplam_km"] or 0)
            cost_per_km = (
                fuel_cost / Decimal(str(total_distance))
                if total_distance > 0
                else Decimal("0")
            )

            trends.append(
                {
                    "month": int(month_key[5:7]),
                    "year": int(month_key[0:4]),
                    "label": f"{month_key[5:7]}/{month_key[0:4]}",
                    "fuel_cost": float(fuel_cost),
                    "fuel_liters": float(row["yakit_litre"] or 0),
                    "trip_count": int(row["sefer_sayisi"] or 0),
                    "total_distance": total_distance,
                    "cost_per_km": float(round(cost_per_km, 2)),
                }
            )

        return trends


async def get_vehicle_cost_comparison(months: int = 3) -> List[Dict]:
    """Compare vehicle cost performance using real trip and fuel data."""
    # Fetch vehicles then close the UoW immediately — keeping an idle
    # outer transaction open across the per-vehicle gather wastes a pool
    # connection for the entire duration of all inner calculations.
    async with UnitOfWork() as uow:
        vehicles = await uow.arac_repo.get_all(sadece_aktif=True)

    if not vehicles:
        return []

    today = current_date()
    start_date = today - timedelta(days=months * 30)

    # Limit concurrency to 5 to avoid pool exhaustion under large fleets.
    _sem = asyncio.Semaphore(5)

    async def calculate_for_vehicle(vehicle):
        arac_id = vehicle.get("id")
        async with _sem:
            try:
                breakdown = await calculate_period_cost(start_date, today, arac_id)
                return {
                    "arac_id": arac_id,
                    "plaka": vehicle.get("plaka"),
                    "fuel_cost": float(breakdown.fuel_cost),
                    "total_distance": breakdown.total_distance,
                    "cost_per_km": float(breakdown.cost_per_km),
                    "avg_consumption": round(
                        breakdown.fuel_liters / (breakdown.total_distance / 100)
                        if breakdown.total_distance > 0
                        else 0,
                        2,
                    ),
                }
            except Exception as exc:
                logger.warning(
                    "Cost calculation failed for vehicle %s: %s",
                    arac_id,
                    exc,
                )
                return {
                    "arac_id": arac_id,
                    "plaka": vehicle.get("plaka"),
                    "unavailable": True,
                    "error_code": "SERVICE_UNAVAILABLE",
                    "error_message": "Cost comparison is unavailable for this vehicle.",
                }

    comparisons = await asyncio.gather(
        *[calculate_for_vehicle(vehicle) for vehicle in vehicles]
    )

    return sorted(
        comparisons,
        key=lambda item: item.get("cost_per_km")
        if item.get("cost_per_km") is not None
        else float("inf"),
    )


async def calculate_savings_potential(target_consumption: float = 30.0) -> Dict:
    """Calculate savings potential against a caller-supplied target baseline."""
    if target_consumption <= 0:
        return {"error": "Target consumption must be greater than zero."}

    today = current_date()
    start_date = today - timedelta(days=90)
    period_days = max((today - start_date).days, 1)

    current = await calculate_period_cost(start_date, today)
    if current.total_distance <= 0 or current.fuel_liters <= 0:
        return {"error": "Savings analysis requires source-backed trip and fuel data."}

    current_cost = float(current.fuel_cost)
    current_consumption = round(current.fuel_liters / (current.total_distance / 100), 2)
    target_liters = (current.total_distance / 100) * target_consumption
    target_cost = float(round(target_liters * float(current.avg_price_per_liter), 2))
    potential_savings = round(current_cost - target_cost, 2)
    savings_percentage = round(
        (potential_savings / current_cost * 100) if current_cost > 0 else 0, 1
    )
    annual_projection = round(potential_savings * (365 / period_days), 2)

    return {
        "current_consumption": current_consumption,
        "target_consumption": round(target_consumption, 2),
        "current_cost": round(current_cost, 2),
        "target_cost": target_cost,
        "potential_savings": potential_savings,
        "savings_percentage": savings_percentage,
        "annual_projection": annual_projection,
        "observed_period_days": period_days,
    }


async def calculate_roi(
    investment: float,
    months: int = 12,
    target_consumption: float = 30.0,
) -> Dict:
    """Calculate ROI from real savings potential only."""
    if investment <= 0:
        return {"error": "Investment must be greater than zero."}

    savings_result = await calculate_savings_potential(target_consumption)
    if "error" in savings_result:
        return savings_result

    observed_period_days = max(int(savings_result["observed_period_days"]), 1)
    daily_savings = savings_result["potential_savings"] / observed_period_days
    monthly_savings = round(daily_savings * 30, 2)
    annual_savings = round(daily_savings * 365, 2)

    if monthly_savings <= 0:
        return {
            "error": "ROI requires a positive savings baseline from real source data."
        }

    return {
        "investment": round(investment, 2),
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "payback_months": round(investment / monthly_savings, 1),
        "annual_roi_percentage": round((annual_savings / investment) * 100, 1),
        "cost_improvement_pct": round(savings_result["savings_percentage"], 1),
        "analysis_months": months,
        "target_consumption": savings_result["target_consumption"],
    }
