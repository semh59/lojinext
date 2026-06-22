"""Feature A.2 — Coaching Celery görevleri.

- coaching.weekly_digest: her aktif şoför için DriverCoachingEngine
  çalıştırır; priority='high' olanları Telegram'a (eğer telegram_id varsa)
  HTML formatında otomatik gönderir.

Plan: Pazartesi 09:00 UTC (celery_app.py beat_schedule).
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Any, Dict

import httpx
from celery.exceptions import SoftTimeLimitExceeded

from app.config import settings
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)

# Pazartesi 09:00 koçluk batch'i için özel limitler. 500 şoför × ~2s Groq
# LLM = 1000s; global 90s task_time_limit yetmiyordu. 1 saat aktif çalışma
# + 5 dakika cooldown.
WEEKLY_DIGEST_SOFT_LIMIT = 3600  # 60 dk
WEEKLY_DIGEST_HARD_LIMIT = 3900  # 65 dk


async def _send_high_priority_to_telegram(
    telegram_id: str,
    headline: str,
    top_suggestion: str | None,
) -> bool:
    bot_token = settings.TELEGRAM_DRIVER_BOT_TOKEN
    if not bot_token:
        return False

    safe_headline = html.escape(headline)
    safe_suggestion = html.escape(top_suggestion or "")
    body = f"📢 <b>Haftalık Koçluk</b>\n\n{safe_headline}"
    if safe_suggestion:
        body += f"\n\n💡 <b>Öneri</b>: {safe_suggestion}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": body,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Weekly digest send failed for %s: %s", telegram_id, exc)
        return False


async def _run_digest() -> Dict[str, Any]:
    """Aktif şoförler için sırayla engine.generate_coaching çağırır.

    SoftTimeLimitExceeded (Celery worker'ın limit'e yaklaştığında attığı
    sinyal) yakalanır → o ana kadarki ilerleme partial sonuç olarak döner;
    `timeout_partial=True` bayrağı operasyon ekibine zaman aşımını
    bildirir.
    """
    from app.core.ai.driver_coaching_engine import get_driver_coaching_engine
    from app.database.unit_of_work import UnitOfWork

    engine = get_driver_coaching_engine()
    async with UnitOfWork() as uow:
        soforler = await uow.sofor_repo.get_all(sadece_aktif=True, limit=500)

    results: Dict[str, Any] = {
        "processed": 0,
        "high_priority": 0,
        "sent": 0,
        "errors": 0,
        "total": len(soforler),
        "timeout_partial": False,
    }
    try:
        for s in soforler:
            sid = int(s["id"])
            try:
                insights = await engine.generate_coaching(sid)
                results["processed"] += 1
                if insights.priority == "high":
                    results["high_priority"] += 1
                    tg_id = s.get("telegram_id")
                    if tg_id and settings.COACHING_ENABLED:
                        top = (
                            insights.insights[0].suggestion
                            if insights.insights
                            else None
                        )
                        sent = await _send_high_priority_to_telegram(
                            tg_id, insights.headline, top
                        )
                        if sent:
                            results["sent"] += 1
            except SoftTimeLimitExceeded:
                # Çağrı zincirinden dışarı taşı — kümülatif partial dönüş.
                raise
            except Exception as exc:
                logger.error("Coaching digest failed for sofor %s: %s", sid, exc)
                results["errors"] += 1
    except SoftTimeLimitExceeded:
        results["timeout_partial"] = True
        logger.warning(
            "Weekly digest SoftTimeLimitExceeded — partial result: %s/%s",
            results["processed"],
            results["total"],
        )
    return results


@celery_app.task(
    bind=True,
    name="coaching.weekly_digest",
    max_retries=2,
    acks_late=True,
    soft_time_limit=WEEKLY_DIGEST_SOFT_LIMIT,
    time_limit=WEEKLY_DIGEST_HARD_LIMIT,
)
def weekly_coaching_digest(self) -> Dict[str, Any]:  # noqa: ARG001
    """Haftalık koçluk özeti — Pazartesi 09:00 UTC.

    Global Celery task_time_limit=90s; 500 şoför için yetmediğinden bu
    task'a özel 1 saatlik soft limit + 5 dk cushion eklendi.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_digest())
    finally:
        loop.close()


async def _run_evaluate_pending() -> Dict[str, Any]:
    """A.5 — 14 günden eski + evaluated_at NULL CoachingDelivery'leri işle:
    o anki skoru oku, delta'yı yaz, evaluated_at doldur."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select, update

    from app.core.services.sofor_service import SoforService
    from app.database.models import CoachingDelivery
    from app.database.unit_of_work import UnitOfWork

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    results: Dict[str, Any] = {"evaluated": 0, "skipped": 0, "errors": 0}

    async with UnitOfWork() as uow:
        stmt = select(CoachingDelivery).where(
            CoachingDelivery.sent_at < cutoff,
            CoachingDelivery.evaluated_at.is_(None),
        )
        rows = (await uow.session.execute(stmt)).scalars().all()
        if not rows:
            return results

        svc = SoforService(repo=uow.sofor_repo)
        now = datetime.now(timezone.utc)

        for d in rows:
            try:
                score = await svc.get_score_breakdown(d.sofor_id)
                current_total = float(score.get("total") or 0)
                if d.score_before and d.score_before > 0:
                    delta = (current_total - d.score_before) / d.score_before * 100.0
                else:
                    delta = 0.0
                await uow.session.execute(
                    update(CoachingDelivery)
                    .where(CoachingDelivery.id == d.id)
                    .values(
                        score_after_2w=current_total,
                        score_delta_pct=round(delta, 2),
                        evaluated_at=now,
                    )
                )
                results["evaluated"] += 1
            except Exception as exc:
                logger.warning(
                    "Coaching evaluate failed for delivery %s: %s", d.id, exc
                )
                results["errors"] += 1
        await uow.commit()
    return results


@celery_app.task(
    bind=True,
    name="coaching.evaluate_pending",
    max_retries=2,
    acks_late=True,
)
def evaluate_pending_deliveries(self) -> Dict[str, Any]:  # noqa: ARG001
    """Günde bir kez (02:00 UTC) — vakti gelmiş delivery'lerin etki ölçümü."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_evaluate_pending())
    finally:
        loop.close()
