"""Sefer onay durumu (approval workflow) use-case'leri."""

from typing import Any, List, Optional

from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from v2.modules.trip.application.list_trips import get_sefer_by_id
from v2.modules.trip.infrastructure.repository import SeferRepository, get_sefer_repo

logger = get_logger(__name__)

_VALID_ONAY_DURUMLARI = {"beklemede", "onaylandi", "reddedildi"}


async def set_onay_durumu(
    sefer_id: int,
    yeni_durum: str,
    onay_notu: Optional[str] = None,
    onaylayan_id: Optional[int] = None,
    repo: Optional[SeferRepository] = None,
) -> Optional[Any]:
    """Sefer onay durumunu günceller (beklemede → onaylandi / reddedildi)."""
    if yeni_durum not in _VALID_ONAY_DURUMLARI:
        raise ValueError(f"Geçersiz onay durumu: '{yeni_durum}'")

    repo = repo or get_sefer_repo()
    before = await get_sefer_by_id(sefer_id, repo=repo)
    updated = await repo.set_onay_durumu(sefer_id, yeni_durum, onay_notu, onaylayan_id)
    if updated is None:
        return None

    eski_durum = before.get("onay_durumu") if before else None
    logger.info(
        "set_onay_durumu: sefer_id=%s %s→%s by user_id=%s",
        sefer_id,
        eski_durum,
        yeni_durum,
        onaylayan_id,
    )
    await log_audit_event(
        action="sefer_onay_guncelle",
        module="sefer",
        entity_id=str(sefer_id),
        user_id=onaylayan_id,
        details={"eski": eski_durum, "yeni": yeni_durum, "not": onay_notu},
    )
    return await get_sefer_by_id(sefer_id, repo=repo)


async def get_by_onay_durumu(
    onay_durumu: str,
    skip: int = 0,
    limit: int = 50,
    repo: Optional[SeferRepository] = None,
) -> List[Any]:
    """Onay durumuna göre seferler."""
    repo = repo or get_sefer_repo()
    return await repo.get_by_onay_durumu(onay_durumu, skip=skip, limit=limit)
