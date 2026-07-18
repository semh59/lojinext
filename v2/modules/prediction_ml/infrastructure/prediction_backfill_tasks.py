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
def backfill_missing(self, limit: int = 50) -> dict[str, Any]:
    """tahmini_tuketim=NULL seferleri estimator ile doldur.

    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 16): eskiden TÜM
    hatalar yutulup normal bir sonuç dict'i dönüyordu — Celery bunu SUCCESS
    sayıyor, `max_retries` fiilen devre dışı kalıyordu. Artık geçici hatalar
    (`ConnectionError`/`TimeoutError`/`OSError` — Mapbox/Open-Meteo/DB
    bağlantı sorunları) retry ediliyor, diğerleri log'lanıp yeniden
    fırlatılıyor (task gerçekten FAILED olarak işaretlenir, izlenebilir).
    """
    from v2.modules.prediction_ml.application.prediction_backfill_service import (
        PredictionBackfillService,
    )

    async def _run() -> dict[str, Any]:
        return await PredictionBackfillService().backfill(limit=limit)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
    except Exception:
        logger.exception("prediction backfill task failed permanently")
        raise
    finally:
        loop.close()
