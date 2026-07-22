"""Use-case: create a new location/route record."""

from typing import Optional

from app.infrastructure.logging.logger import get_logger
from v2.modules.location.application.analyze_location_route import (
    analyze_location_route,
)
from v2.modules.location.domain.route_key import normalize_turkish_title, route_key
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonCreate
from v2.modules.platform_infra.events.event_bus import EventType, publishes
from v2.modules.shared_kernel.infrastructure.outbox import save_outbox_event

logger = get_logger(__name__)

# Schema fields not accepted by the repository layer's add() signature.
_REPO_EXCLUDE = {"route_analysis", "source"}


@publishes(EventType.LOKASYON_ADDED)
async def create_location(
    repo: LokasyonRepository,
    data: LokasyonCreate,
    existing_index: Optional[dict] = None,
) -> int:
    """Yeni lokasyon/güzergah ekle.

    ``existing_index``: toplu import (bkz. ImportService.import_routes)
    satır-başına ayrı SELECT atmamak için önceden TEK sorguyla doldurduğu
    ``{route_key: {"id", "aktif"}}`` haritası. Verilirse ``repo.get_by_route``
    çağrısı atlanır ve bu haritadan okunur; ekleme/reaktivasyon sonrası
    harita yerinde güncellenir (aynı batch içindeki tekrarlar da yakalanır).
    None ise (mevcut tüm diğer çağıranlar, örn. tekil POST /locations)
    davranış aynen korunur.
    """
    data.cikis_yeri = normalize_turkish_title(data.cikis_yeri)
    data.varis_yeri = normalize_turkish_title(data.varis_yeri)

    key = route_key(data.cikis_yeri, data.varis_yeri)
    if existing_index is not None:
        existing = existing_index.get(key)
    else:
        existing = await repo.get_by_route(data.cikis_yeri, data.varis_yeri)
    if existing:
        if existing.get("aktif"):
            raise ValueError(
                f"Bu güzergah zaten mevcut: {data.cikis_yeri} -> {data.varis_yeri}"
            )
        # Pasif ise geri getir ve güncelle
        logger.info(
            f"Pasif lokasyon tekrar aktifleştiriliyor: {data.cikis_yeri} -> {data.varis_yeri}"
        )
        await repo.update(
            existing["id"], aktif=True, **data.model_dump(exclude_unset=True)
        )
        if existing_index is not None:
            existing_index[key]["aktif"] = True
        await save_outbox_event(
            repo.session, EventType.LOKASYON_ADDED, {"result": existing["id"]}
        )
        return existing["id"]

    lokasyon_id = await repo.add(**data.model_dump(exclude=_REPO_EXCLUDE))
    logger.info(f"Yeni güzergah eklendi: ID {lokasyon_id}")
    if existing_index is not None:
        existing_index[key] = {"id": lokasyon_id, "aktif": True}
    await save_outbox_event(
        repo.session, EventType.LOKASYON_ADDED, {"result": lokasyon_id}
    )

    # Rota analizi yap (opsiyonel — yalnız koordinatlar varsa tetiklenir).
    payload = data.model_dump()
    if all(
        [
            payload.get("cikis_lat"),
            payload.get("cikis_lon"),
            payload.get("varis_lat"),
            payload.get("varis_lon"),
        ]
    ):
        try:
            await analyze_location_route(repo, lokasyon_id)
        except Exception as e:
            logger.warning(f"Otomatik rota analizi başarısız (ID: {lokasyon_id}): {e}")

    return lokasyon_id
