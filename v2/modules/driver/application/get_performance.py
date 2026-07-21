"""Use-case: composite driver performance card (safety/eco/compliance)."""

from typing import Any, Dict

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_performance_details(sofor_id: int) -> Dict[str, Any]:
    """Calculates driver performance details (AI & Stats Analysis)."""
    async with UnitOfWork() as uow:
        stats_list = await uow.sofor_repo.get_sefer_stats(sofor_id=sofor_id)
        stats = stats_list[0] if stats_list else {}

        total_km = float(stats.get("toplam_km") or 0)
        total_trips = int(stats.get("toplam_sefer") or 0)
        avg_consumption = float(stats.get("ort_tuketim") or 0)

        anomalies = await uow.sofor_repo.get_driver_anomalies_count(sofor_id, days=30)

    deduction = (
        (anomalies.get("critical", 0) * 10)
        + (anomalies.get("high", 0) * 5)
        + (anomalies.get("medium", 0) * 2)
    )
    safety_score = max(0.0, 100.0 - deduction)

    target = 30.0
    if avg_consumption > 0:
        deviation_pct = ((avg_consumption - target) / target) * 100
        if deviation_pct > 0:
            eco_score = max(0.0, 100.0 - deviation_pct)
        else:
            eco_score = min(100.0, 100.0 + (abs(deviation_pct) * 0.5))
    else:
        eco_score = 90.0

    compliance_deduction = (
        (anomalies.get("critical", 0) * 6)
        + (anomalies.get("high", 0) * 3)
        + (anomalies.get("medium", 0) * 1.5)
        + (anomalies.get("low", 0) * 0.5)
    )
    compliance_score = max(0.0, 100.0 - compliance_deduction)

    total_score = (safety_score * 0.4) + (eco_score * 0.4) + (compliance_score * 0.2)

    trend = "stable"
    if total_score > 90:
        trend = "increasing"
    elif total_score < 70:
        trend = "decreasing"

    return {
        "safety_score": round(safety_score, 1),
        "eco_score": round(eco_score, 1),
        "compliance_score": round(compliance_score, 1),
        "total_score": round(total_score, 1),
        "trend": trend,
        "total_km": round(total_km, 1),
        "total_trips": total_trips,
    }
