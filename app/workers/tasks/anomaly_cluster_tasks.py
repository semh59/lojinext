"""Faz 8 — günlük anomali kümeleme taraması (Celery beat)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.ml.anomaly_clustering import cluster_anomalies
from app.core.services.anomaly_detector import get_anomaly_detector
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run() -> dict[str, Any]:
    detector = get_anomaly_detector()
    rows = await detector.get_recent_anomalies(days=30)
    clusters = cluster_anomalies(rows)
    logger.info("Anomali kümeleme: %s anomali → %s küme", len(rows), len(clusters))
    for c in clusters[:5]:
        logger.info("  küme: %s", c["label"])
    return {"anomalies": len(rows), "clusters": len(clusters)}


@celery_app.task(bind=True, name="anomaly.cluster_scan", max_retries=1, acks_late=True)
def cluster_scan(self) -> dict[str, Any]:  # noqa: ARG001
    """Her gün anomalileri kümeleyip özet loglar (pattern izleme)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("anomaly cluster scan failed: %s", exc, exc_info=True)
        return {"anomalies": 0, "clusters": 0, "error": str(exc)}
    finally:
        loop.close()
