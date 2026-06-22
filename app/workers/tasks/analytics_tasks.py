"""Faz 3 — kullanım analitiği retention task'i (gece prune)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.database.connection import session_scope
from app.database.repositories.page_view_repo import PageViewRepository
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="analytics.prune_page_views",
    max_retries=1,
    acks_late=True,
)
def prune_page_views(self) -> dict[str, Any]:  # noqa: ARG001
    """ANALYTICS_RETENTION_DAYS'ten eski page_views satırlarını siler."""

    async def _run() -> dict[str, Any]:
        async with session_scope() as session:
            repo = PageViewRepository(session)
            deleted = await repo.prune_older_than(
                days=settings.ANALYTICS_RETENTION_DAYS
            )
        return {"deleted": deleted}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("analytics prune failed: %s", exc, exc_info=True)
        return {"deleted": 0, "error": str(exc)}
    finally:
        loop.close()
