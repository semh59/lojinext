"""Use-case: create a new vehicle (Duplicate Check + Reactivation)."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from v2.modules.fleet.application.vehicle_event_log import log_vehicle_event
from v2.modules.fleet.infrastructure.models import VehicleEventLog, VehicleSpecTimeline
from v2.modules.fleet.schemas import AracCreate
from v2.modules.platform_infra.events.event_bus import EventType, publishes
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.monitoring.service_probe import monitor_errors
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)

# Process-local TOCTOU guard shared with update_vehicle.py (same plaka-uniqueness
# race). Does not protect against multi-worker races — the real guard is the
# UNIQUE(plaka) constraint (see AracRepository.add docstring).
plaka_lock = asyncio.Lock()


@monitor_errors(category="arac_write", severity="error")
@publishes(EventType.ARAC_ADDED)
async def create_vehicle(data: AracCreate, uow: Optional[UnitOfWork] = None) -> int:
    """Creates a new vehicle (Duplicate Check + Reactivation)."""
    if uow is None:
        async with UnitOfWork() as new_uow:
            return await _create_vehicle_impl(data, new_uow)
    else:
        return await _create_vehicle_impl(data, uow)


async def _create_vehicle_impl(data: AracCreate, uow: UnitOfWork) -> int:
    async with plaka_lock:  # Race Condition Guard (TOCTOU)
        existing = await uow.arac_repo.get_by_plaka(data.plaka, for_update=True)
        if existing:
            if existing.get("aktif") is False:
                logger.info(f"Re-activating passive vehicle: {data.plaka}")
                # Teknik özellikler (ağırlık/aerodinamik/motor/lastik/yük/dingil/
                # yakıt tipi/muayene) de geçilmeli — bunlar PredictionService.
                # _build_vehicle_specs'in fizik-tabanlı yakıt tahmininde OKUDUĞU
                # gerçek girdiler. Eskiden sadece marka/model/yil/tank/hedef_
                # tuketim/notlar güncelleniyordu; operatör "araç ekle" formuna
                # yeni teknik değerler girse bile eski (reaktive edilen) aracın
                # değerleri sessizce korunuyordu — yanlış tahmin girdisi
                # üretiyordu (canlı-hazırlık denetimi bulgusu, 2026-07-09).
                await uow.arac_repo.update(
                    existing["id"],
                    aktif=True,
                    marka=data.marka,
                    model=data.model or "",
                    yil=data.yil,
                    tank_kapasitesi=data.tank_kapasitesi,
                    hedef_tuketim=data.hedef_tuketim,
                    notlar=data.notlar or "",
                    dingil_sayisi=data.dingil_sayisi,
                    yakit_tipi=data.yakit_tipi,
                    bos_agirlik_kg=data.bos_agirlik_kg,
                    hava_direnc_katsayisi=data.hava_direnc_katsayisi,
                    on_kesit_alani_m2=data.on_kesit_alani_m2,
                    motor_verimliligi=data.motor_verimliligi,
                    lastik_direnc_katsayisi=data.lastik_direnc_katsayisi,
                    maks_yuk_kapasitesi_kg=data.maks_yuk_kapasitesi_kg,
                    muayene_tarihi=getattr(data, "muayene_tarihi", None),
                    sigorta_tarihi=getattr(data, "sigorta_tarihi", None),
                    motor_no=getattr(data, "motor_no", None),
                    sasi_no=getattr(data, "sasi_no", None),
                )
                await log_vehicle_event(
                    existing["id"],
                    "RE_ACTIVATED",
                    details=f"Passive vehicle reactivated: {data.plaka}",
                    uow=uow,
                )
                await save_outbox_event(
                    uow.session, EventType.ARAC_ADDED, {"result": existing["id"]}
                )
                # Persist the reactivation. Without this the UnitOfWork's
                # ghost-transaction guard rolls back the aktif=True update and
                # the event log on __aexit__, so the vehicle silently stays
                # passive (the insert path below already commits at line ~90).
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
            sigorta_tarihi=getattr(data, "sigorta_tarihi", None),
            motor_no=getattr(data, "motor_no", None),
            sasi_no=getattr(data, "sasi_no", None),
            aktif=getattr(data, "aktif", True),
        )
        logger.info(f"New vehicle added: {data.plaka}")

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

        await save_outbox_event(
            uow.session, EventType.ARAC_ADDED, {"result": int(new_arac.id)}
        )
        await uow.commit()
        return int(new_arac.id)
