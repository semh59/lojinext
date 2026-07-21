"""Use-cases: paged/filtered fuel listing + aggregate statistics."""

from datetime import date
from typing import Any, Dict, List, Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.fuel.domain.entities import YakitAlimi

logger = get_logger(__name__)


async def get_all_paged(
    skip: int = 0, limit: int = 100, aktif_only: bool = True, **filters: Any
) -> Dict[str, Any]:
    """Returns paged and filtered fuel list."""
    if filters.get("baslangic_tarih") and isinstance(filters["baslangic_tarih"], str):
        try:
            filters["baslangic_tarih"] = date.fromisoformat(filters["baslangic_tarih"])
        except ValueError:
            pass

    if filters.get("bitis_tarih") and isinstance(filters["bitis_tarih"], str):
        try:
            filters["bitis_tarih"] = date.fromisoformat(filters["bitis_tarih"])
        except ValueError:
            pass

    async with UnitOfWork() as uow:
        paged_data = await uow.yakit_repo.get_all(
            offset=skip, limit=limit, include_inactive=not aktif_only, **filters
        )

    records = paged_data.get("items", [])
    total_count = paged_data.get("total", 0)

    results = []
    for r in records:
        try:
            results.append(YakitAlimi.model_validate(dict(r)))
        except Exception as e:
            logger.error(f"Fuel validation error (ID {r.get('id')}): {e}")
            continue
    return {"items": results, "total": total_count}


async def get_all(
    limit: int = 100, vehicle_id: Optional[int] = None
) -> List[YakitAlimi]:
    """Legacy support for getting all records."""
    result = await get_all_paged(limit=limit, arac_id=vehicle_id)
    if isinstance(result, dict):
        return result.get("items", [])
    return result


async def get_stats(
    baslangic_tarih: Optional[date] = None, bitis_tarih: Optional[date] = None
) -> Dict:
    """Retrieves general fuel statistics with filter support."""
    if baslangic_tarih is not None or bitis_tarih is not None:
        async with UnitOfWork() as uow:
            return await uow.yakit_repo.get_stats(
                baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
            )

    try:
        async with UnitOfWork() as uow:
            dashboard = await uow.analiz_repo.get_dashboard_stats()
        if dashboard:
            return {
                "toplam_yakit": dashboard.get("toplam_yakit", 0),
                "aylik_ort": dashboard.get("filo_ortalama", 0),
                "toplam_tutar": dashboard.get("toplam_tutar", 0),
                **dashboard,
            }
    except Exception as e:
        logger.warning(f"Dashboard stats fallback failed: {e}")

    async with UnitOfWork() as uow:
        return await uow.yakit_repo.get_stats(
            baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
        )


async def get_monthly_summary() -> List[Dict]:
    """Retrieves monthly consumption summary."""
    async with UnitOfWork() as uow:
        if hasattr(uow.analiz_repo, "get_monthly_consumption_series"):
            return await uow.analiz_repo.get_monthly_consumption_series()
        return await uow.analiz_repo.get_daily_consumption_series(days=365)


async def get_monthly_cost_trend(months: int = 12) -> List[Dict]:
    """Son N ay için aylık toplam yakıt maliyeti — `[{"ay": "YYYY-MM", "tutar": float}, ...]`."""
    async with UnitOfWork() as uow:
        rows = await uow.yakit_repo.get_monthly_cost_trend(months=months)
    return [{"ay": r["ay"], "tutar": float(r["tutar"])} for r in rows]
