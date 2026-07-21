"""Use-case: create a driver (single + bulk)."""

from datetime import date
from typing import Any, List, Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType, publishes
from app.infrastructure.logging.logger import get_logger
from v2.modules.driver.application._locks import SOFOR_WRITE_LOCK
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event

logger = get_logger(__name__)


@publishes(EventType.SOFOR_ADDED)
async def add_sofor(
    ad_soyad: str,
    telefon: str = "",
    ehliyet_sinifi: str = "E",
    ise_baslama: Optional[date] = None,
    manual_score: float = 1.0,
    notlar: str = "",
    telegram_id: Optional[str] = None,
) -> int:
    """Adds a new driver (UoW & Atomic Check)."""
    async with UnitOfWork() as uow:
        async with SOFOR_WRITE_LOCK:
            if not ad_soyad or len(ad_soyad.strip()) < 3:
                raise ValueError("Ad soyad en az 3 karakter olmalıdır.")

            ad_soyad_clean = " ".join(
                word.capitalize() for word in ad_soyad.strip().split()
            )

            existing = await uow.sofor_repo.get_by_name(ad_soyad_clean, for_update=True)
            if existing:
                if existing.get("aktif"):
                    raise ValueError(
                        f"An active driver with this name already exists: {ad_soyad_clean}"
                    )
                logger.info(f"Re-activating passive driver (ID: {existing['id']})")
                await uow.sofor_repo.update(existing["id"], aktif=True)
                await save_outbox_event(
                    uow.session, EventType.SOFOR_ADDED, {"result": existing["id"]}
                )
                await uow.commit()
                return existing["id"]

            sofor_id = await uow.sofor_repo.add(
                ad_soyad=ad_soyad_clean,
                telefon=telefon,
                ehliyet_sinifi=ehliyet_sinifi,
                ise_baslama=ise_baslama,
                manual_score=manual_score,
                score=manual_score,
                notlar=notlar,
                telegram_id=telegram_id,
            )

            logger.info(f"New driver added: {ad_soyad_clean} (ID: {sofor_id})")
            await save_outbox_event(
                uow.session, EventType.SOFOR_ADDED, {"result": int(sofor_id)}
            )
            await uow.commit()
            return int(sofor_id)


async def bulk_add_sofor(data_list: List[Any]) -> int:
    """Bulk creates drivers (UoW & performance optimized)."""
    if not data_list:
        return 0

    async with UnitOfWork() as uow:
        existing_names = await uow.sofor_repo.get_aktif_isimler()
        existing_set = set(existing_names)

        to_add = []
        for data in data_list:
            if hasattr(data, "model_dump"):
                d = data.model_dump()
            elif hasattr(data, "dict"):
                d = data.dict()
            else:
                d = data

            ad_soyad = d.get("ad_soyad", "").strip()
            if not ad_soyad or len(ad_soyad) < 3:
                continue

            ad_soyad = " ".join(word.capitalize() for word in ad_soyad.split())

            if ad_soyad in existing_set:
                continue

            to_add.append(
                {
                    "ad_soyad": ad_soyad,
                    "telefon": d.get("telefon", ""),
                    "ise_baslama": d.get("ise_baslama") or None,
                    "ehliyet_sinifi": d.get("ehliyet_sinifi", "E"),
                    "notlar": d.get("notlar", ""),
                    "aktif": True,
                    "score": 1.0,
                }
            )

        if to_add:
            ids = await uow.sofor_repo.bulk_create(to_add)
            logger.info(f"Bulk drivers added: {len(ids)} entries")
            await uow.commit()
            return len(ids)

    return 0
