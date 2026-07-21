"""Sefer okuma (read-only) use-case'leri — eski SeferReadService'in dissolve edilmiş hali."""

from datetime import date
from typing import Any, Dict, List, Optional

from app.infrastructure.logging.logger import get_logger
from v2.modules.auth_rbac.public import Kullanici, SecurityService
from v2.modules.trip.domain.entities import Sefer
from v2.modules.trip.infrastructure.repository import SeferRepository, get_sefer_repo
from v2.modules.trip.infrastructure.sefer_timeline_repo import (
    get_sefer_timeline,
)
from v2.modules.trip.schemas import SeferResponse
from v2.modules.trip.sefer_status import normalize_sefer_status

logger = get_logger(__name__)


async def get_by_id(
    sefer_id: int,
    current_user: Optional[Kullanici] = None,
    repo: Optional[SeferRepository] = None,
) -> Optional[Sefer]:
    """ID ile sefer getir (İzolasyon korumalı)"""
    repo = repo or get_sefer_repo()
    row = await repo.get_by_id_with_details(sefer_id)
    if not row:
        return None

    sefer = Sefer.model_validate(row)

    # Ownership check
    if current_user:
        SecurityService.verify_ownership(current_user, sefer.sofor_id)

    return sefer


async def get_sefer_by_id(
    sefer_id: int,
    current_user: Optional[Kullanici] = None,
    repo: Optional[SeferRepository] = None,
) -> Optional[Dict[str, Any]]:
    """Legacy support for Dict return (İzolasyon korumalı)"""
    sefer = await get_by_id(sefer_id, current_user, repo=repo)
    return sefer.model_dump() if sefer else None


async def get_by_vehicle(
    arac_id: int, limit: int = 50, repo: Optional[SeferRepository] = None
) -> List[Sefer]:
    """Araç sefer geçmişini getir"""
    repo = repo or get_sefer_repo()
    records = await repo.get_all(arac_id=arac_id, limit=limit)
    return [Sefer.model_validate(dict(r)) for r in records]


async def get_all_paged(
    current_user: Optional[Kullanici] = None,
    skip: int = 0,
    limit: int = 100,
    aktif_only: bool = True,
    repo: Optional[SeferRepository] = None,
    **filters: Any,
) -> Dict[str, Any]:
    """
    Sayfalı ve filtreli sefer listesi (Güvenli Katman).
    Kullanıcı yetkisine göre veri izolasyonu (Isolation) uygular.
    """
    repo = repo or get_sefer_repo()
    # Repo katmanı zaten MAX_LIMIT'te kesiyor; servis cap'ini ona hizala ki
    # API gerçekte uygulanmayan (5005) bir limiti ima etmesin (API-003).
    limit = min(max(1, limit), SeferRepository.MAX_LIMIT)
    skip = max(0, skip)

    if current_user:
        filters = SecurityService.apply_isolation(current_user, filters)

    # Normalize Turkish or mixed-case durum filter values to the English
    # canonical form stored in the DB ('Planned'/'Completed'/'Cancelled').
    if filters.get("durum"):
        normalized_durum = normalize_sefer_status(str(filters["durum"]))
        if normalized_durum:
            filters["durum"] = normalized_durum

    # Total count for metadata
    total = await repo.count_all(include_inactive=not aktif_only, filters=filters)

    records = await repo.get_all(
        offset=skip, limit=limit, include_inactive=not aktif_only, filters=filters
    )

    results: List[SeferResponse] = []
    for r in records:
        try:
            # Ensure we handle the dict conversion
            data = dict(r) if not isinstance(r, dict) else r
            results.append(SeferResponse.model_validate(data))
        except Exception as e:
            logger.error(f"Sefer validasyon hatasi (ID {r.get('id')}): {e}")
            continue

    return {
        "items": results,
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


async def get_all_trips(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sofor_id: Optional[int] = None,
    arac_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    repo: Optional[SeferRepository] = None,
) -> List[SeferResponse]:
    """Filtreli sefer listesi (Legacy support, redirected to paged)"""
    # Note: This returns List[Sefer], but get_all_paged returns Dict.
    # We need to adapt it.
    paged_result = await get_all_paged(
        limit=limit,
        arac_id=arac_id,
        sofor_id=sofor_id,
        baslangic_tarih=start_date,
        bitis_tarih=end_date,
        durum=status,
        repo=repo,
    )

    return paged_result["items"]


async def get_timeline(sefer_id: int) -> List[Dict[str, Any]]:
    return await get_sefer_timeline(sefer_id)
