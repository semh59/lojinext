"""
DLQ tüketim/gözlem task'ları.
"""

import json
from datetime import datetime
from typing import Optional, cast

import redis

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

REDIS_URL = celery_app.conf.broker_url


@celery_app.task(name="prediction.drain_dlq", bind=True, max_retries=0)
def drain_prediction_dlq(self, requeue: bool = False):
    """
    pred:dlq kuyruğundaki hatalı işleri loglar; opsiyonel yeniden kuyruğa alır.
    """
    r = redis.Redis.from_url(REDIS_URL)
    drained = 0
    while True:
        raw = cast(Optional[bytes], r.rpop("pred:dlq"))
        if not raw:
            break
        drained += 1
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw.decode("utf-8", errors="ignore")}

        logger.error("[DLQ] prediction task failed: %s", payload)

        if requeue:
            r.lpush("pred:retry", raw)
            logger.info(
                "[DLQ] requeued to pred:retry: task_id=%s", payload.get("task_id")
            )

    if drained:
        from datetime import timezone

        return {"drained": drained, "timestamp": datetime.now(timezone.utc).isoformat()}
    return {"drained": 0}
