"""Use-case: create a new trailer record (Duplicate Check + Reactivation).

Aynı desen create_vehicle.py ile (2026-07-09 canlı-hazırlık denetimi
bulgusu): eskiden buradan doğrudan `repo.create()`'e düşülüyordu — plaka
unique constraint aktif/pasif ayrımı yapmadığı için (1) aynı plakalı aktif
bir dorse eklenmeye çalışılırsa IntegrityError endpoint'te özel
yakalanmıyordu (genel 500), (2) pasif bir dorsenin plakası asla yeniden
kullanılamıyordu (varsayılan liste aktif_only=True olduğu için operatör
pasif kaydı görüp elle reaktive de edemiyordu) — kalıcı çıkmaz sokak.
"""

import asyncio

from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
from v2.modules.platform_infra.public import get_logger

logger = get_logger(__name__)

# Process-local TOCTOU guard — aynı gerekçe create_vehicle.plaka_lock ile.
plaka_lock = asyncio.Lock()


async def create_trailer(repo: DorseRepository, **data) -> int:
    """Create a new trailer record (Duplicate Check + Reactivation)."""
    plaka = data.get("plaka")
    async with plaka_lock:  # Race Condition Guard (TOCTOU)
        existing = await repo.get_by_plate(plaka, for_update=True)
        if existing:
            if existing.aktif is False:
                logger.info(f"Re-activating passive trailer: {plaka}")
                update_data = {k: v for k, v in data.items() if k != "plaka"}
                update_data["aktif"] = True
                await repo.update(existing.id, **update_data)
                return existing.id
            raise ValueError(f"A trailer with this plate already exists: {plaka}")

        return await repo.create(**data)
