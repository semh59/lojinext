"""Reports v2 RV2.PWA — Web Push gönderim adaptörü (pywebpush I/O).

Plan §7.2 — pywebpush ile VAPID self-hosted push gönderir.
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings
from app.database.models import PushSubscription

logger = logging.getLogger(__name__)


async def send_webpush(sub: PushSubscription, payload: dict) -> tuple[bool, bool]:
    """Tek subscription'a push gönder.

    Returns:
        (success, expired) — expired True ise 410 Gone alındı, kayıt silinmeli.
    """
    try:
        from pywebpush import (  # type: ignore[import-not-found]
            WebPushException,
            webpush,
        )
    except ImportError:
        logger.warning("pywebpush not installed; push send skipped")
        return False, False

    try:
        # pywebpush.webpush() bloklayıcı — HTTPS round-trip + VAPID JWT/ECDSA
        # imzalama (CPU-bound). Doğrudan çağrılırsa paylaşılan event loop'u
        # her push için durdurur — telegram_client.py'nin docstring'inde
        # anlatılan gerçek prod-incident'iyle (Sentry LOJINEXT-182, bloklayıcı
        # bir çağrının event loop'u dondurup zamanlanmış coroutine'leri
        # etkilemesi) aynı sınıf, 2026-07-16 dedektif denetiminde bulundu.
        await asyncio.to_thread(
            webpush,
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
        )
        return True, False
    except WebPushException as exc:
        # 410 Gone → subscription artık geçersiz
        status = getattr(exc.response, "status_code", None)
        if status == 410:
            logger.info("Subscription expired (410): %s", sub.endpoint[:60])
            return False, True
        logger.warning(
            "WebPush failed (status=%s) for %s: %s",
            status,
            sub.endpoint[:60],
            exc,
        )
        return False, False
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected push error: %s", exc)
        return False, False
