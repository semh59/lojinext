"""Feature A.2 — Şoför Koçluk endpoint'leri.

``router`` mounts at ``/coaching`` (3 route).

GET  /api/v1/coaching/{sofor_id}/insights — 30dk Redis cache'li öneriler
POST /api/v1/coaching/{sofor_id}/send     — Telegram (HTML) üzerinden mesaj
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_user, require_permissions
from app.config import settings
from app.database.models import CoachingDelivery, Kullanici, Sofor
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from v2.modules.driver.application.generate_coaching import get_driver_coaching_engine
from v2.modules.driver.application.get_score import get_score_breakdown_sofor
from v2.modules.driver.schemas import (
    CoachingEffectivenessResponse,
    CoachingInsightsResponse,
    SendCoachingRequest,
    SendCoachingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

CACHE_TTL_SECONDS = 30 * 60  # 30 dakika
CACHE_KEY_FMT = "coaching:insights:{sofor_id}"


def _ensure_enabled() -> None:
    if not settings.COACHING_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Koçluk modülü şu an devre dışı",
        )


_coaching_redis: Any = None  # singleton — modül ömrü boyunca tek pool


async def _get_redis():
    """Async Redis client (singleton); başarısızlıkta None → cache miss.

    Eskiden her HTTP isteğinde aioredis.from_url(...) yeni bir
    ConnectionPool yaratıyordu. Module-level cache ile tek pool kullanılır.
    Socket timeout=1.0s; dev host'ta DNS/connect hang olmaz.
    """
    global _coaching_redis
    if _coaching_redis is not None:
        return _coaching_redis
    try:
        import redis.asyncio as aioredis

        _coaching_redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        return _coaching_redis
    except Exception as exc:
        logger.debug("Coaching redis client init failed (expected if local): %s", exc)
        return None


@router.get("/{sofor_id}/insights", response_model=CoachingInsightsResponse)
async def get_coaching_insights(
    sofor_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """30 dk Redis cache'li koçluk önerileri."""
    _ensure_enabled()

    cache_key = CACHE_KEY_FMT.format(sofor_id=sofor_id)
    redis_client = await _get_redis()

    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return CoachingInsightsResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Coaching cache read failed: %s", exc)

    sofor = await db.get(Sofor, sofor_id)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")

    engine = get_driver_coaching_engine()
    try:
        result = await engine.generate_coaching(sofor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "Coaching generation crashed for %s: %s", sofor_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Koçluk önerileri üretilemedi"
        ) from exc

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key, CACHE_TTL_SECONDS, result.model_dump_json()
            )
        except Exception as exc:
            logger.warning("Coaching cache write failed: %s", exc)

    return result


def _build_telegram_text(message: str) -> str:
    """HTML-escaped Telegram mesaj gövdesi.

    Plan Q2 kararı: Markdown legacy escape sorunlarından kaçınmak için
    parse_mode=HTML + html.escape().
    """
    safe = html.escape(message)
    return f"🧭 <b>Koçluk Önerisi</b>\n\n{safe}"


@router.post(
    "/{sofor_id}/send",
    response_model=SendCoachingResponse,
    dependencies=[
        Depends(RateLimiterDependency("coaching_send", rate=10.0, period=60.0))
    ],
)
async def send_coaching(
    sofor_id: int,
    payload: SendCoachingRequest,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sofor:write"))],
):
    """Telegram üzerinden manuel koçluk mesajı gönder."""
    _ensure_enabled()

    sofor = await db.get(Sofor, sofor_id)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    if not sofor.telegram_id:
        raise HTTPException(
            status_code=409,
            detail="Bu şoför Telegram'a kayıtlı değil; mesaj gönderilemez",
        )

    bot_token = settings.TELEGRAM_DRIVER_BOT_TOKEN
    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot yapılandırması eksik (TELEGRAM_DRIVER_BOT_TOKEN)",
        )

    text = _build_telegram_text(payload.message)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage",
                json={
                    "chat_id": sofor.telegram_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Telegram send failed for sofor %s: %s", sofor_id, exc)
        await log_audit_event(
            action="coaching_send_failed",
            module="coaching",
            entity_id=str(sofor_id),
            user_id=current_admin.id,
            new_value={
                "error": str(exc),
                "channel": payload.channel,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=f"Telegram gönderimi başarısız: {exc}",
        ) from exc

    sent_at = datetime.now(timezone.utc)

    # A.5 — CoachingDelivery kaydı (etki ölçümü için score_before snapshot'ı).
    # Engine zaten score_breakdown'u önbellekte tutmuş olabilir, ama mesaj
    # gönderildiği tam an'daki skoru almak istiyoruz → inline UoW + free func.
    delivery_id: int | None = None
    try:
        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            score_snapshot = await get_score_breakdown_sofor(sofor_id, uow=uow)
            # Virtual super-admin id=0 → DB'de kayıt yok; FK ihlali yaşamamak
            # için yalnız gerçek user id'yi yaz.
            sent_by = getattr(current_admin, "id", None)
            if sent_by is not None and sent_by <= 0:
                sent_by = None
            delivery = CoachingDelivery(
                sofor_id=sofor_id,
                score_before=float(score_snapshot.get("total") or 1.0),
                channel=payload.channel,
                insight_category=payload.insight_category,
                message_excerpt=payload.message[:500],
                sent_by_user_id=sent_by,
            )
            uow.session.add(delivery)
            await uow.session.flush()
            await uow.session.refresh(delivery)
            delivery_id = int(delivery.id)
            await uow.commit()
    except Exception as exc:
        # Audit kalır ama etki ölçümü kaybedilir — kullanıcı akışı bozulmasın.
        logger.warning("CoachingDelivery INSERT failed: %s", exc)

    await log_audit_event(
        action="coaching_sent",
        module="coaching",
        entity_id=str(sofor_id),
        user_id=current_admin.id,
        new_value={
            "message_excerpt": payload.message[:200],
            "channel": payload.channel,
            "category": payload.insight_category,
            "delivery_id": delivery_id,
        },
    )

    return SendCoachingResponse(
        sent=True,
        delivery_id=delivery_id,
        channel=payload.channel,
        sent_at=sent_at.isoformat(),
    )


@router.get("/effectiveness", response_model=CoachingEffectivenessResponse)
async def get_coaching_effectiveness(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = 30,
):
    """Son N günde gönderilen koçluk mesajlarının etki özeti.

    Caveat: skor değişimi yalnız koçluğa atfedilemez (mevsimsellik,
    güzergah değişimi, self-selection bias). UI bunu açıkça gösterir.
    """
    _ensure_enabled()
    from datetime import timedelta

    from sqlalchemy import text

    days = max(7, min(180, int(days)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = text(
        """
        SELECT
            COUNT(*)                                                       AS total_sent,
            COUNT(*) FILTER (WHERE evaluated_at IS NOT NULL)                AS total_evaluated,
            COUNT(*) FILTER (WHERE score_delta_pct IS NOT NULL
                                 AND score_delta_pct > 0)                   AS improved,
            COUNT(*) FILTER (WHERE score_delta_pct IS NOT NULL
                                 AND score_delta_pct < 0)                   AS worsened,
            AVG(score_delta_pct) FILTER (WHERE evaluated_at IS NOT NULL)    AS avg_delta
        FROM coaching_deliveries
        WHERE sent_at >= :cutoff
        """
    )
    row = (await db.execute(stmt, {"cutoff": cutoff})).mappings().one()
    total_evaluated = int(row["total_evaluated"] or 0)
    improved = int(row["improved"] or 0)
    avg_delta = row["avg_delta"]

    return CoachingEffectivenessResponse(
        window_days=days,
        total_sent=int(row["total_sent"] or 0),
        total_evaluated=total_evaluated,
        improved=improved,
        worsened=int(row["worsened"] or 0),
        improve_rate=(improved / total_evaluated) if total_evaluated > 0 else None,
        avg_score_delta_pct=(float(avg_delta) if avg_delta is not None else None),
        caveat=(
            "Bu metrik istatistiksel kanıt değil, yalnız gözlemdir. "
            "Skor değişiminde mevsimsellik, güzergah ve operasyonel "
            "faktörler de etkilidir."
        ),
    )
