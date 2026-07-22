"""
Prediction task (async) - RAG + LLM çağrısı.
Sonuçlar Celery backend + opsiyonel Redis cache'te tutulur.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import cast

import redis

from app.infrastructure.background.celery_app import celery_app
from v2.modules.ai_assistant.public import LLMMessage, get_llm_client
from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.prediction_ml.infrastructure.models import PredictionResult

_log = logging.getLogger(__name__)


@celery_app.task(bind=True, name="prediction.generate", max_retries=3, acks_late=True)
def run_prediction_task(self, question: str, context: str | None = None) -> dict:
    """
    Basit RAG+LLM task'ı (bloklayan).
    Dönen dict JSON-serileştirilebilir olmalı.
    """
    llm = get_llm_client()

    async def _run() -> str:
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": question})
        return await llm.chat(
            messages=[LLMMessage(**m) for m in messages],
            max_tokens=512,
            temperature=0.3,
            system_prompt="Sen bir TIR yakıt ve lojistik uzmansın. Kısa, Türkçe yanıt ver.",
        )

    redis_client = redis.Redis.from_url(celery_app.conf.broker_url)
    cache_key = f"pred:result:{self.request.id}"

    # Idempotency: önceden tamamlanmışsa cache'den dön
    try:
        if redis_client.exists(cache_key):
            cached = json.loads(cast("bytes", redis_client.get(cache_key)))
            return cached
    except Exception:
        pass

    try:
        answer = asyncio.run(_run())
        result_payload = {
            "status": "completed",
            "answer": answer,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run(_persist(task_id=self.request.id, status="success", answer=answer))
        try:
            redis_client.setex(cache_key, 86400, json.dumps(result_payload))
        except Exception:
            pass
        return result_payload
    except Exception as exc:
        try:
            # Celery's self.retry() always raises (Retry or MaxRetriesExceededError);
            # the re-raise is unreachable but makes the flow explicit for mypy.
            self.retry(exc=exc, countdown=2**self.request.retries)
            raise exc
        except self.MaxRetriesExceededError:
            asyncio.run(
                _persist(task_id=self.request.id, status="failed", error=str(exc))
            )
            try:
                redis_client.lpush(
                    "pred:dlq",
                    json.dumps(
                        {
                            "task_id": self.request.id,
                            "status": "failed",
                            "error": str(exc),
                            "failed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                )
            except Exception:
                pass
            return {
                "status": "failed",
                "error": str(exc),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }


async def _persist(
    task_id: str, status: str, answer: str | None = None, error: str | None = None
):
    """Sonucu prediction_results tablosuna yazar (best-effort)."""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(PredictionResult).where(PredictionResult.task_id == task_id)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                existing = PredictionResult(task_id=task_id)
                session.add(existing)
            existing.status = status
            existing.answer = answer
            existing.error = error
            existing.finished_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception as _e:
        # DB yazımı best-effort; hata loglansın ama task'ı engellesin
        _log.warning("_persist failed for task_id=%s: %s", task_id, _e)
