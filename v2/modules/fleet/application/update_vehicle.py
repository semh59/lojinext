"""Use-case: update a vehicle (Safe Plate Changes handled)."""

from typing import Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.events.outbox_service import save_outbox_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.fleet.application.create_vehicle import plaka_lock
from v2.modules.fleet.application.vehicle_event_log import log_vehicle_event
from v2.modules.fleet.infrastructure.models import VehicleSpecTimeline
from v2.modules.fleet.schemas import AracUpdate

logger = get_logger(__name__)


@monitor_errors(category="arac_write", severity="error")
@publishes(EventType.ARAC_UPDATED)
async def update_vehicle(
    arac_id: int, data: AracUpdate, uow: Optional[UnitOfWork] = None
) -> bool:
    """Updates a vehicle (Safe Plate Changes handled)."""
    if uow is None:
        async with UnitOfWork() as new_uow:
            return await _update_vehicle_impl(arac_id, data, new_uow)
    else:
        return await _update_vehicle_impl(arac_id, data, uow)


async def _update_vehicle_impl(arac_id: int, data: AracUpdate, uow: UnitOfWork) -> bool:
    if data.plaka:
        async with plaka_lock:
            existing = await uow.arac_repo.get_by_plaka(data.plaka, for_update=True)
            if existing and existing["id"] != arac_id:
                raise ValueError(f"This plate belongs to another vehicle: {data.plaka}")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return False

    arac = await uow.arac_repo.get_by_id(arac_id)
    if arac is None:
        # Vehicle doesn't exist, or exists but is currently passive
        # (soft-deleted). A generic update must not silently mutate a
        # retired vehicle's data by bypassing the reactivation flow —
        # only an explicit reactivation (aktif=True in the payload) is
        # allowed to touch a passive vehicle's row.
        if update_data.get("aktif") is True:
            arac = await uow.arac_repo.get_by_id(arac_id, include_inactive=True)
        if arac is None:
            return False

    old_status = None
    if "aktif" in update_data and arac:
        old_status = "ACTIVE" if arac.get("aktif") else "PASSIVE"

    success = await uow.arac_repo.update(arac_id, **update_data)
    if success:
        logger.info(f"Vehicle updated: ID {arac_id}")
        if "aktif" in update_data:
            new_status = "ACTIVE" if update_data["aktif"] else "PASSIVE"
            if old_status != new_status:
                await log_vehicle_event(
                    arac_id,
                    "STATUS_CHANGE",
                    old_status=old_status,
                    new_status=new_status,
                    details="Status updated via update_vehicle",
                    uow=uow,
                )

        spec_fields = [
            "dingil_sayisi",
            "yakit_tipi",
            "bos_agirlik_kg",
            "maks_yuk_kapasitesi_kg",
        ]
        changed = arac and any(
            field in update_data and update_data[field] != arac.get(field)
            for field in spec_fields
        )

        if changed:
            timeline = VehicleSpecTimeline(
                arac_id=arac_id,
                dingil_sayisi=update_data.get(
                    "dingil_sayisi", arac.get("dingil_sayisi")
                ),
                yakit_tipi=update_data.get("yakit_tipi", arac.get("yakit_tipi")),
                bos_agirlik_kg=update_data.get(
                    "bos_agirlik_kg", arac.get("bos_agirlik_kg")
                ),
                kapasite_kg=update_data.get(
                    "maks_yuk_kapasitesi_kg", arac.get("maks_yuk_kapasitesi_kg")
                ),
                notlar=f"Update triggered spec change. Fields: {', '.join(update_data.keys())}",
            )
            uow.session.add(timeline)

        await save_outbox_event(
            uow.session, EventType.ARAC_UPDATED, {"result": arac_id}
        )
        await uow.commit()
    return success
