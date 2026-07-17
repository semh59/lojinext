"""Faz 5 — haftalık 'dikkat etmen gereken 3 şey' digest (Celery beat)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app
from v2.modules.notification.application.send_push_to_user import send_push_to_user
from v2.modules.reports.public import aggregate_today_triage

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
def weekly_digest(self) -> dict[str, Any]:
    """Pazartesi — abone kullanıcılara haftalık top-3 dikkat digest'i.

    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 16): eskiden TÜM
    hatalar yutulup normal bir sonuç dict'i dönüyordu — Celery bunu SUCCESS
    sayıyor, `max_retries` fiilen devre dışı kalıyordu (geçici bir DB/Redis
    hatası bile hiç retry edilmeden sessizce kayboluyordu). Artık geçici
    hatalar (`ConnectionError`/`TimeoutError`/`OSError`) retry ediliyor,
    diğerleri log'lanıp yeniden fırlatılıyor (task gerçekten FAILED olarak
    işaretlenir, izlenebilir).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_weekly_digest())
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
    except Exception:
        logger.exception("weekly digest failed permanently")
        raise
    finally:
        loop.close()
