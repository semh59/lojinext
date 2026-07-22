"""Use-case: manuel araç/şoför atama düzeltmesi (trip attribution override).

B.1: eski ``AttributionService`` sınıfı kaldırıldı (location/notification/
fleet/fuel/driver/auth-rbac'taki kararla aynı gerekçe) — constructor sadece
``uow`` + ``event_bus`` tutuyordu, gerçek state değildi. ``uow`` parametresi
opsiyonel: endpoint request-scoped session'ı (``UnitOfWork(db)``) geçirir,
bulk yol her item için taze bir ``UnitOfWork()`` açar (aşağıdaki
``bulk_override_attribution`` docstring'inde açıklandığı gibi, tek bir
paylaşılan instance üzerinden — davranış aynı, eskiden ``self.uow`` da
tüm loop boyunca aynı instance'tı).
"""

from typing import Optional

from fastapi import HTTPException, status

from v2.modules.platform_infra.public import (
    Event,
    EventType,
    get_event_bus,
    get_logger,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def override_attribution(
    sefer_id: int,
    arac_id: Optional[int] = None,
    sofor_id: Optional[int] = None,
    reason: str = "",
    uow: Optional[UnitOfWork] = None,
) -> bool:
    """
    Manually override the vehicle or driver for a trip.
    Triggers physics and ML recalculation events.
    """
    active_uow = uow if uow is not None else UnitOfWork()
    async with active_uow:
        # 1. Fetch the trip
        sefer = await active_uow.sefer_repo.get_by_id(sefer_id)
        if not sefer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sefer bulunamadı: {sefer_id}",
            )

        old_arac_id = sefer["arac_id"]
        old_sofor_id = sefer["sofor_id"]

        # 2. Update fields
        updates = {"is_corrected": True, "correction_reason": reason}

        if arac_id is not None:
            updates["arac_id"] = arac_id
        if sofor_id is not None:
            updates["sofor_id"] = sofor_id

        success = await active_uow.sefer_repo.update(sefer_id, **updates)

        if success:
            # 3. Commit the transaction
            await active_uow.commit()

            # 4. Publish Event for downstream systems (Physics, ML, Cache)
            await get_event_bus().publish_async(
                Event(
                    type=EventType.SEFER_UPDATED,
                    data={
                        "sefer_id": sefer_id,
                        "old_arac_id": old_arac_id,
                        "new_arac_id": arac_id or old_arac_id,
                        "old_sofor_id": old_sofor_id,
                        "new_sofor_id": sofor_id or old_sofor_id,
                        "reason": reason,
                        "trigger": "manual_override",
                    },
                    source="AttributionService",
                )
            )

            logger.info(
                f"Attribution override successful for Sefer {sefer_id}. Reason: {reason}"
            )
            return True

        return False


async def bulk_override_attribution(overrides: list) -> int:
    """
    Apply multiple overrides in one go (not yet implemented in repo bulk, using loop).

    Tek bir paylaşılan ``UnitOfWork`` instance'ı tüm item'lar boyunca yeniden
    kullanılır — eski ``AttributionService.bulk_override``'ın ``self.uow``'u
    her ``self.override_attribution(...)`` çağrısında yeniden kullanmasıyla
    birebir aynı davranış.
    """
    uow = UnitOfWork()
    count = 0
    for item in overrides:
        try:
            if await override_attribution(
                sefer_id=item["sefer_id"],
                arac_id=item.get("arac_id"),
                sofor_id=item.get("sofor_id"),
                reason=item.get("reason", "Toplu güncelleme"),
                uow=uow,
            ):
                count += 1
        except Exception as e:
            logger.error(f"Bulk item failed: {e}")
    return count
