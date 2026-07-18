"""Use-case: bulk-create vehicles (UoW & Event Log Compatible).

Pasif (deaktif) plaka çakışması varsa aracı reaktive eder; aktif plaka
çakışması varsa satırı atlar.
"""

from typing import List

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType
from app.infrastructure.events.outbox_service import save_outbox_event
from app.infrastructure.logging.logger import get_logger
from v2.modules.fleet.application.vehicle_event_log import log_vehicle_event
from v2.modules.fleet.schemas import AracCreate

logger = get_logger(__name__)


async def bulk_add_vehicles(data_list: List[AracCreate]) -> int:
    """Creates vehicles in bulk (UoW & Event Log Compatible)."""
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
                await log_vehicle_event(
                    vid, "REACTIVATED", details="Bulk reactivated", uow=uow
                )
            total += len(to_reactivate)
            logger.info("Bulk vehicles reactivated: %d entries", len(to_reactivate))

        if to_add:
            ids = await uow.arac_repo.bulk_create(to_add)
            logger.info("Bulk vehicles created: %d entries", len(ids))
            for vid in ids:
                await log_vehicle_event(vid, "CREATED", details="Bulk created", uow=uow)
            total += len(ids)

        if total:
            # create_vehicle.py'nin tekil yolu her create/reactivate'te
            # ARAC_ADDED outbox event'i yazıyor (RAG sync + cache invalidation
            # relay'i tetikler); bulk yol bunu hiç yapmıyordu — Excel'den
            # toplu eklenen araçlar RAG indeksine/cache invalidation'a hiç
            # düşmüyordu (2026-07-16 dedektif denetimi bulgusu). Tek bir
            # aggregate event yeterli: on_arac_change (cache_invalidation.py)
            # payload'ı okumuyor, yalnız `arac:*`/`stats:filo*` wildcard
            # invalidate ediyor.
            await save_outbox_event(
                uow.session,
                EventType.ARAC_ADDED,
                {"created": len(to_add), "reactivated": len(to_reactivate)},
            )
            await uow.commit()

    return total
