"""Use-case: paged, filtered location listing."""

from typing import Optional

from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonResponse
from v2.modules.platform_infra.public import get_logger

logger = get_logger(__name__)


async def list_locations(
    repo: LokasyonRepository,
    skip: int = 0,
    limit: int = 100,
    aktif_only: bool = True,
    zorluk: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Sayfalı ve filtreli lokasyon listesi + Toplam Sayı"""
    filters = {}
    if zorluk:
        filters["zorluk"] = zorluk
    if search:
        filters["search"] = search

    records = await repo.get_all(
        offset=skip, limit=limit, include_inactive=not aktif_only, filters=filters
    )
    total = await repo.count(filters=filters, include_inactive=not aktif_only)

    items = []
    skipped = 0
    for r in records:
        try:
            items.append(LokasyonResponse.model_validate(dict(r)))
        except Exception as e:
            logger.error(f"Lokasyon validasyon hatasi (ID {r.get('id')}): {e}")
            skipped += 1

    # Adjust total downward by skipped records on this page so the frontend
    # doesn't navigate to pages that would return 0 items.
    return {"items": items, "total": max(0, total - skipped)}
