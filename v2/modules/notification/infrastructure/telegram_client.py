"""Fire-and-forget Telegram error notifications.

Backend bileşenlerinden gelen hataları ops_bot webhook'una gönderir.
Ops_bot URL: TELEGRAM_OPS_BOT_URL env var (varsayılan: http://telegram-ops-bot:8080)
"""

from __future__ import annotations

import asyncio
import logging
import os

from app.infrastructure.monitoring.external_api_probe import get_monitored_client

logger = logging.getLogger(__name__)

_OPS_BOT_URL = os.environ.get("TELEGRAM_OPS_BOT_URL", "http://telegram-ops-bot:8080")
_WEBHOOK_URL = f"{_OPS_BOT_URL}/webhook/error"
_FEEDBACK_WEBHOOK_URL = f"{_OPS_BOT_URL}/webhook/feedback"
_TIMEOUT = 10.0
_MAX_RETRIES = 3
_RETRY_DELAYS = (1.0, 3.0)  # saniye cinsinden, 3. deneme sonrası fallback

# 2026-07-01 prod-grade denetimi P1: ops_bot artık OPS_WEBHOOK_SECRET
# yapılandırılmamışsa TÜM webhook isteklerini reddediyor (fail-closed) — bu
# istemci de aynı secret'ı Authorization: Bearer header'ı olarak göndermeli,
# aksi halde kendi hata/feedback bildirimleri 503 ile reddedilir.
_OPS_WEBHOOK_SECRET = os.environ.get("OPS_WEBHOOK_SECRET", "")


def _auth_headers() -> dict[str, str]:
    if not _OPS_WEBHOOK_SECRET:
        return {}
    return {"Authorization": f"Bearer {_OPS_WEBHOOK_SECRET}"}


async def notify_error(
    *,
    level: str,
    message: str,
    path: str = "",
    trace_id: str = "",
) -> None:
    """ops_bot /webhook/error endpointine hata bildirimi gönderir.

    3 deneme yapar (1s ve 3s aralıklarla). Hepsi başarısız olursa
    error:sync_fallback listesine yazar — digest task daha sonra tüketir.
    """
    payload = {"level": level, "message": message, "path": path, "trace_id": trace_id}
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with get_monitored_client(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _WEBHOOK_URL, json=payload, headers=_auth_headers()
                )
                resp.raise_for_status()
                return
        except Exception as exc:
            last_exc = exc
            if attempt < len(_RETRY_DELAYS):
                await asyncio.sleep(_RETRY_DELAYS[attempt])

    logger.warning(
        "Telegram notify_error failed after %d attempts — ops bot unreachable at %s: %s",
        _MAX_RETRIES,
        _WEBHOOK_URL,
        last_exc,
    )
    await _push_to_sync_fallback(
        level=level, message=message, path=path, trace_id=trace_id
    )


async def notify_feedback(
    *,
    message: str,
    username: str = "",
    page: str = "",
) -> bool:
    """Pilot kullanıcı geri bildirimini ops_bot /webhook/feedback'e iletir.

    Best-effort: 2 deneme (1s ara). Başarısızsa False döner (endpoint yine 202).
    Hata bildiriminden ayrı kanal — rate-limit/sync-fallback uygulanmaz.
    """
    payload = {"message": message, "username": username, "page": page}
    for attempt in range(2):
        try:
            async with get_monitored_client(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _FEEDBACK_WEBHOOK_URL, json=payload, headers=_auth_headers()
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            if attempt == 0:
                await asyncio.sleep(1.0)
            else:
                logger.warning(
                    "Telegram notify_feedback failed (ops bot %s): %s",
                    _FEEDBACK_WEBHOOK_URL,
                    exc,
                )
    return False


async def _push_to_sync_fallback(
    *, level: str, message: str, path: str, trace_id: str
) -> None:
    """Tüm denemeler başarısız olunca sync_fallback listesine yazar.

    Async Redis client kullanır (2026-07-09 event-loop-blokaj bulgusu,
    Sentry LOJINEXT-182): önceden senkron redis-py ile ``r.lpush()``/
    ``r.ltrim()`` doğrudan bu async fonksiyon (her zaman çalışan bir event
    loop içinde çağrılır) içinden çalıştırılıyordu — bloklayan bir socket
    çağrısı, o an event loop'ta zamanlanmış HER coroutine/task'ı (SQLAlchemy
    sorgu callback'leri dahil) donduruyordu. Canlı bir "Slow query: 3528ms"
    olayının breadcrumb'ları bunu doğruladı: bayraklanan sorgu (`SELECT
    araclar.id ...`) önemsizdi, ölçülen süre bu blokajı da kapsıyordu.
    """
    import json

    try:
        from app.infrastructure.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        if mgr.redis is None:
            return
        payload = json.dumps(
            {
                "layer": "api",
                "category": "telegram_delivery_failure",
                "severity": level,
                "message": message,
                "path": path,
                "trace_id": trace_id,
                "metadata": {},
            }
        )
        # redis-py's async stubs give lpush/ltrim a pipeline-compatible
        # overload that mypy can't disambiguate from plain client usage
        # (unlike .set/.get/.incr elsewhere in redis_pubsub.py, which don't
        # hit this) — both calls are correctly awaited at runtime.
        await mgr.redis.lpush("error:sync_fallback", payload)  # type: ignore[misc]
        await mgr.redis.ltrim("error:sync_fallback", 0, 999)  # type: ignore[misc]
    except Exception as fb_exc:
        logger.debug("sync_fallback push failed: %s", fb_exc)
