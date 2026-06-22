"""Faz 5 — haftalık 'dikkat etmen gereken 3 şey' digest (Celery beat)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.core.services.push_sender import send_push_to_user
from app.core.services.triage_aggregator import aggregate_today_triage
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _distinct_subscriber_ids(uow: Any) -> list[int]:
    from app.database.models import PushSubscription

    rows = await uow.session.execute(select(PushSubscription.user_id).distinct())
    return [int(r) for r in rows.scalars().all() if r is not None]


def _digest_body(triage: Any) -> str:
    items = getattr(triage, "items", []) or []
    top3 = items[:3]
    if not top3:
        return "Bu hafta dikkat gerektiren acil bir konu görünmüyor."
    lines = [f"• {getattr(i, 'title', '—')}" for i in top3]
    return "Bu hafta dikkat etmen gereken 3 şey:\n" + "\n".join(lines)


async def _run_weekly_digest() -> dict[str, Any]:
    async with UnitOfWork() as uow:
        user_ids = await _distinct_subscriber_ids(uow)
        if not user_ids:
            return {"users": 0, "pushed": 0}
        triage = await aggregate_today_triage(uow, lookback_days=7)
        body = _digest_body(triage)
        pushed = 0
        for uid in user_ids:
            res = await send_push_to_user(
                uid,
                title="Haftalık Özet",
                body=body,
                url="/today",
                uow=uow,
                respect_quiet_hours=True,
            )
            pushed += getattr(res, "sent", 0)
    return {"users": len(user_ids), "pushed": pushed}


@celery_app.task(
    bind=True, name="notifications.weekly_digest", max_retries=1, acks_late=True
)
def weekly_digest(self) -> dict[str, Any]:  # noqa: ARG001
    """Pazartesi — abone kullanıcılara haftalık top-3 dikkat digest'i."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_weekly_digest())
    except Exception as exc:  # noqa: BLE001
        logger.error("weekly digest failed: %s", exc, exc_info=True)
        return {"users": 0, "pushed": 0, "error": str(exc)}
    finally:
        loop.close()
