"""Use-cases: maintenance history / completion / upcoming alerts."""

from datetime import datetime
from typing import Any, Dict, List

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.fleet.application.maintenance_cache import invalidate_predictions_cache
from v2.modules.fleet.infrastructure.models import AracBakim

logger = get_logger(__name__)


async def get_vehicle_maintenance_history(arac_id: int) -> List[AracBakim]:
    """Retrieve full maintenance history for a vehicle."""
    async with UnitOfWork() as uow:
        return await uow.maintenance_repo.get_by_arac_id(arac_id)


async def mark_maintenance_completed(bakim_id: int) -> bool:
    """Mark a maintenance record as completed."""
    async with UnitOfWork() as uow:
        success = await uow.maintenance_repo.update(bakim_id, tamamlandi=True)
        if success:
            await uow.commit()
            logger.info(f"Maintenance {bakim_id} marked as completed.")
    # D.2 — bakım tamamlandı, tahmin cache'i geçersiz
    if success:
        await invalidate_predictions_cache()
    return success


async def get_upcoming_maintenance_alerts() -> List[Dict[str, Any]]:
    """Fetch vehicles that are due or overdue for maintenance."""
    async with UnitOfWork() as uow:
        bakimlar = await uow.maintenance_repo.get_upcoming_maintenance()
        # Enrich with vehicle plates for UI convenience. Batch-fetch the
        # vehicles in one query (avoids an N+1 get_by_id per maintenance row).
        arac_map = await uow.arac_repo.get_by_ids([b.arac_id for b in bakimlar])
        results = []
        for b in bakimlar:
            arac = arac_map.get(b.arac_id)
            results.append(
                {
                    "id": b.id,
                    "arac_id": b.arac_id,
                    "plaka": arac.plaka if arac else "N/A",
                    "bakim_tipi": b.bakim_tipi,
                    "tarih": b.bakim_tarihi,
                    "vade_durumu": "OVERDUE"
                    if b.bakim_tarihi.replace(tzinfo=None) < datetime.now()
                    else "UPCOMING",
                }
            )
        return results
