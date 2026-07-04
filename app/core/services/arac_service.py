"""
LOJINEXT Fuel Tracking - Vehicle Service
Business logic layer: Vehicle management and validations (English).

TYPE: PER-REQUEST
SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
DEPENDS_ON: UoW.arac_repo
CREATED_BY: app/api/deps.py::deps.get_arac_service()
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.core.entities.models import (
    Arac as AracEntity,
)
from app.core.entities.models import (
    AracCreate,
    AracUpdate,
    VehicleStats,
)
from app.database.models import VehicleSpecTimeline
from app.database.repositories.arac_repo import AracRepository, get_arac_repo
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import (
    EventBus,
    EventType,
    get_event_bus,
    publishes,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors

logger = get_logger(__name__)


class AracService:
    """Vehicle business logic service."""

    def __init__(
        self,
        repo: Optional["AracRepository"] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.repo = repo or get_arac_repo()
        self.event_bus = event_bus or get_event_bus()
        self._lock = (
            asyncio.Lock()
        )  # process-local; does not protect against multi-worker races

    async def _log_vehicle_event(
        self,
        arac_id: int,
        event_type: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        details: Optional[str] = None,
        uow: Optional[Any] = None,
        triggered_by: Optional[str] = "SYSTEM",
    ):
        """Creates a vehicle event log entry (Atomic & UoW Compatible)."""
        try:
            from app.database.models import VehicleEventLog

            log = VehicleEventLog(
                arac_id=arac_id,
                event_type=event_type,
                old_status=old_status,
                new_status=new_status,
                triggered_by=triggered_by,
                details=details,
            )

            if uow:
                uow.session.add(log)
            else:
                async with UnitOfWork() as uow_internal:
                    uow_internal.session.add(log)
                    await uow_internal.commit()
        except Exception as e:
            logger.error(f"Vehicle event log error: {e}")

    @monitor_errors(category="arac_write", severity="error")
    @publishes(EventType.ARAC_ADDED)
    async def create_arac(
        self, data: AracCreate, uow: Optional[UnitOfWork] = None
    ) -> int:
        """Creates a new vehicle (Duplicate Check + Reactivation)."""
        if uow is None:
            async with UnitOfWork() as new_uow:
                return await self._create_arac_impl(data, new_uow)
        else:
            return await self._create_arac_impl(data, uow)

    async def _create_arac_impl(self, data: AracCreate, uow: UnitOfWork) -> int:
        async with self._lock:  # Race Condition Guard (TOCTOU)
            existing = await uow.arac_repo.get_by_plaka(data.plaka, for_update=True)
            if existing:
                if existing.get("aktif") is False:
                    logger.info(f"Re-activating passive vehicle: {data.plaka}")
                    await uow.arac_repo.update(
                        existing["id"],
                        aktif=True,
                        marka=data.marka,
                        model=data.model or "",
                        yil=data.yil,
                        tank_kapasitesi=data.tank_kapasitesi,
                        hedef_tuketim=data.hedef_tuketim,
                        notlar=data.notlar or "",
                    )
                    await self._log_vehicle_event(
                        existing["id"],
                        "RE_ACTIVATED",
                        details=f"Passive vehicle reactivated: {data.plaka}",
                        uow=uow,
                    )
                    # Persist the reactivation. Without this the UnitOfWork's
                    # ghost-transaction guard rolls back the aktif=True update and
                    # the event log on __aexit__, so the vehicle silently stays
                    # passive (the insert path below already commits at line ~160).
                    await uow.commit()
                    return existing["id"]
                else:
                    raise ValueError(
                        f"A vehicle with this plate already exists: {data.plaka}"
                    )

            new_arac = await uow.arac_repo.add(
                plaka=data.plaka,
                marka=data.marka,
                model=data.model or "",
                yil=data.yil,
                tank_kapasitesi=data.tank_kapasitesi,
                hedef_tuketim=data.hedef_tuketim,
                notlar=data.notlar or "",
                muayene_tarihi=getattr(data, "muayene_tarihi", None),
                aktif=getattr(data, "aktif", True),
            )
            logger.info(f"New vehicle added: {data.plaka}")

            from datetime import datetime, timezone

            from app.database.models import VehicleEventLog

            log = VehicleEventLog(
                arac_id=new_arac.id,
                event_type="CREATED",
                created_at=datetime.now(timezone.utc),
                triggered_by="SYSTEM",
                details=f"New vehicle added: {data.plaka}",
            )
            uow.session.add(log)
            uow.session.add(new_arac)
            await uow.session.flush()

            timeline = VehicleSpecTimeline(
                arac_id=new_arac.id,
                dingil_sayisi=data.dingil_sayisi,
                yakit_tipi=data.yakit_tipi,
                bos_agirlik_kg=data.bos_agirlik_kg,
                kapasite_kg=data.maks_yuk_kapasitesi_kg,
                notlar="Initial specification",
            )
            uow.session.add(timeline)

            await uow.commit()
            return int(new_arac.id)

    @monitor_errors(category="arac_write", severity="error")
    @publishes(EventType.ARAC_UPDATED)
    async def update_arac(
        self, arac_id: int, data: AracUpdate, uow: Optional[UnitOfWork] = None
    ) -> bool:
        """Updates a vehicle (Safe Plate Changes handled)."""
        if uow is None:
            async with UnitOfWork() as new_uow:
                return await self._update_arac_impl(arac_id, data, new_uow)
        else:
            return await self._update_arac_impl(arac_id, data, uow)

    async def _update_arac_impl(
        self, arac_id: int, data: AracUpdate, uow: UnitOfWork
    ) -> bool:
        if data.plaka:
            async with self._lock:
                existing = await uow.arac_repo.get_by_plaka(data.plaka, for_update=True)
                if existing and existing["id"] != arac_id:
                    raise ValueError(
                        f"This plate belongs to another vehicle: {data.plaka}"
                    )

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
                    await self._log_vehicle_event(
                        arac_id,
                        "STATUS_CHANGE",
                        old_status=old_status,
                        new_status=new_status,
                        details="Status updated via update_arac",
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

            await uow.commit()
        return success

    @monitor_errors(category="arac_write", severity="error")
    @publishes(EventType.ARAC_DELETED)
    async def delete_arac(self, arac_id: int) -> bool:
        """Deletes a vehicle (Smart Delete: Active->Passive, Passive->Hard Delete)."""
        async with UnitOfWork() as uow:
            # include_inactive=True: bu smart-delete state machine, ikinci
            # çağrıda (aktif=False → hard-delete) zaten pasif kaydı görmesi
            # gerekiyor — kök soft-delete filtresi burada kasıtlı bypass edilir.
            current = await uow.arac_repo.get_by_id(arac_id, include_inactive=True)
            if not current:
                return False

            if current.get("aktif"):
                success = await uow.arac_repo.update(arac_id, aktif=False)
                if success:
                    logger.info(f"Vehicle set to passive (Soft Deleted): ID {arac_id}")
                    await self._log_vehicle_event(
                        arac_id,
                        "STATUS_CHANGE",
                        old_status="ACTIVE",
                        new_status="PASSIVE",
                        details="Soft deleted via delete_arac",
                        uow=uow,
                    )
                    await uow.commit()
                return success
            else:
                try:
                    success = await uow.arac_repo.hard_delete(arac_id)
                    if success:
                        logger.info(
                            f"Vehicle permanently deleted (Hard Deleted): ID {arac_id}"
                        )
                        await uow.commit()
                    return success
                except Exception as e:
                    logger.warning(f"Hard delete prevented (Dependent data): {e}")
                    raise ValueError(
                        "This vehicle has active/archived trip or fuel records and cannot be permanently deleted. Keeping it passive is recommended."  # noqa: E501
                    )

    async def delete_all_vehicles(self) -> int:
        """Clears all vehicles (Admin Only)."""
        async with UnitOfWork() as uow:
            try:
                count = await uow.arac_repo.hard_delete_all()
                logger.info(f"All vehicles cleared: {count} entries")
                await uow.commit()
                return count
            except Exception as e:
                logger.error(f"Bulk delete error: {e}")
                raise ValueError(
                    "Some vehicles could not be deleted due to dependencies."
                )

    async def get_all_paged(
        self,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        search: Optional[str] = None,
        marka: Optional[str] = None,
        model: Optional[str] = None,
        min_yil: Optional[int] = None,
        max_yil: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Returns a paged and filtered list of vehicles."""
        filters: Dict[str, Any] = {}
        if marka:
            filters["marka"] = marka
        if model:
            filters["model"] = model
        if min_yil is not None:
            filters["yil_ge"] = min_yil
        if max_yil is not None:
            filters["yil_le"] = max_yil

        async with UnitOfWork() as uow:
            rows = await uow.arac_repo.get_all(
                offset=skip,
                limit=limit,
                sadece_aktif=aktif_only,
                search=search,
                filters=filters,
            )
            total = await uow.arac_repo.count_all(
                sadece_aktif=aktif_only,
                search=search,
                filters=filters,
            )

        vehicles: List[AracEntity] = []
        for r in rows:
            try:
                vehicles.append(AracEntity.model_validate(dict(r)))
            except Exception as e:
                logger.warning(f"Skipping invalid vehicle record ID {r.get('id')}: {e}")
                continue
        return {"items": vehicles, "total": total}

    async def get_all_vehicles(self, only_active: bool = True) -> List[AracEntity]:
        """Lists all vehicles (Legacy support)."""
        result = await self.get_all_paged(aktif_only=only_active)
        return result["items"]

    async def get_vehicle_stats(self, arac_id: int) -> Optional[VehicleStats]:
        """Returns vehicle details and statistics."""
        async with UnitOfWork() as uow:
            row = await uow.arac_repo.get_arac_with_stats(arac_id)
        if not row:
            return None
        return VehicleStats.model_validate(dict(row))

    async def get_by_id(self, arac_id: int) -> Optional[AracEntity]:
        """Retrieves a vehicle by ID."""
        async with UnitOfWork() as uow:
            row = await uow.arac_repo.get_by_id(arac_id)
        if not row:
            return None
        return AracEntity.model_validate(dict(row))

    async def bulk_add_arac(self, data_list: List[AracCreate]) -> int:
        """Creates vehicles in bulk (UoW & Event Log Compatible).

        Pasif (deaktif) plaka çakışması varsa aracı reaktive eder;
        aktif plaka çakışması varsa satırı atlar.
        """
        if not data_list:
            return 0

        async with UnitOfWork() as uow:
            # Fetch ALL plates (active + inactive) to handle reactivation.
            plaka_map = await uow.arac_repo.get_plaka_id_map()

            to_add = []
            to_reactivate: list[int] = []
            for data in data_list:
                existing = plaka_map.get(data.plaka)
                if existing is None:
                    to_add.append(
                        {
                            "plaka": data.plaka,
                            "marka": data.marka,
                            "model": data.model or "",
                            "yil": data.yil,
                            "tank_kapasitesi": data.tank_kapasitesi,
                            "hedef_tuketim": data.hedef_tuketim,
                            "bos_agirlik_kg": data.bos_agirlik_kg,
                            "motor_verimliligi": data.motor_verimliligi,
                            "lastik_direnc_katsayisi": data.lastik_direnc_katsayisi,
                            "on_kesit_alani_m2": data.on_kesit_alani_m2,
                            "hava_direnc_katsayisi": data.hava_direnc_katsayisi,
                            "maks_yuk_kapasitesi_kg": data.maks_yuk_kapasitesi_kg,
                            "notlar": data.notlar or "",
                            "aktif": True,
                        }
                    )
                else:
                    existing_id, is_active = existing
                    if not is_active:
                        to_reactivate.append(existing_id)

            total = 0

            if to_reactivate:
                for vid in to_reactivate:
                    await uow.arac_repo.update(vid, aktif=True)
                    await self._log_vehicle_event(
                        vid, "REACTIVATED", details="Bulk reactivated", uow=uow
                    )
                total += len(to_reactivate)
                logger.info("Bulk vehicles reactivated: %d entries", len(to_reactivate))

            if to_add:
                ids = await uow.arac_repo.bulk_create(to_add)
                logger.info("Bulk vehicles created: %d entries", len(ids))
                for vid in ids:
                    await self._log_vehicle_event(
                        vid, "CREATED", details="Bulk created", uow=uow
                    )
                total += len(ids)

            if total:
                await uow.commit()

        return total


def get_arac_service() -> AracService:
    from app.core.container import get_container

    return get_container().arac_service
