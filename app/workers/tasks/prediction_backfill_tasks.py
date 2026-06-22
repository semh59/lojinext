"""Faz 1 — Tahmin backfill Celery task (gece beat + manuel tetik)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="prediction.backfill_missing",
    max_retries=1,
    acks_late=True,
    # limit=50 sefer × 2.5s estimator timeout = minimum 125s > global 90s limit.
    # 10 dakika soft + 1 dakika cooldown.
    soft_time_limit=600,
    time_limit=660,
)
def backfill_missing(self, limit: int = 50) -> dict[str, Any]:  # noqa: ARG001
    """tahmini_tuketim=NULL seferleri estimator ile doldur."""
    from app.core.services.prediction_backfill_service import (
        PredictionBackfillService,
    )

    async def _run() -> dict[str, Any]:
        return await PredictionBackfillService().backfill(limit=limit)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("prediction backfill task failed: %s", exc, exc_info=True)
        return {
            "processed": 0,
            "filled": 0,
            "failed": 0,
            "skipped": 0,
            "error": str(exc),
        }
    finally:
        loop.close()
