"""Reports v2 RV2.PWA — Web Push gönderim servisi.

Plan §7.2 — pywebpush ile VAPID self-hosted push gönderir. 410 Gone
yanıtlarında subscription'ı siler.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import delete, select, update

from app.config import settings
from app.database.models import PushSubscription
from app.database.unit_of_work import UnitOfWork
from app.schemas.push import PushSendResult

logger = logging.getLogger(__name__)


def _vapid_configured() -> bool:
    return bool(
        settings.VAPID_PUBLIC_KEY
        and settings.VAPID_PRIVATE_KEY
        and settings.VAPID_SUBJECT
        and settings.PUSH_NOTIFICATION_ENABLED
    )


async def _do_send(sub: PushSubscription, payload: dict) -> tuple[bool, bool]:
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
        webpush(
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


async def send_push_to_user(
    user_id: int,
    *,
    title: str,
    body: str,
    url: Optional[str] = None,
    uow: Optional[UnitOfWork] = None,
    respect_quiet_hours: bool = False,
) -> PushSendResult:
    """Bir kullanıcının tüm aboneliklerine push gönderir.

    410 Gone yanıtı alınan subscription kayıtları silinir.

    Args:
        user_id: Hedef kullanıcı id'si
        title: Push başlığı (showNotification.title)
        body: Push gövdesi
        url: Tıklamada açılacak relatif URL (ör. `/alerts?inv=42`)
        uow: Opsiyonel mevcut UoW; verilmezse yeni context açılır.
        respect_quiet_hours: True ise (Faz 5 — digest gibi acil olmayan
            bildirimler) kullanıcı sessiz saatteyse gönderim atlanır.
    """
    if not _vapid_configured():
        logger.debug("VAPID not configured; skipping push for user %s", user_id)
        return PushSendResult(sent=0, expired=0, failed=0)

    if respect_quiet_hours:
        from app.core.services.quiet_hours import is_user_quiet_now

        if await is_user_quiet_now(user_id):
            logger.debug("Kullanıcı %s sessiz saatte; push atlandı", user_id)
            return PushSendResult(sent=0, expired=0, failed=0)

    payload = {"title": title, "body": body}
    if url:
        payload["url"] = url

    owns_uow = uow is None
    ctx = UnitOfWork() if owns_uow else uow
    assert ctx is not None

    sent = expired = failed = 0
    expired_ids: list[int] = []

    if owns_uow:
        async with ctx as uow_local:
            sent, expired, failed, expired_ids = await _send_for_user(
                uow_local, user_id, payload
            )
            if expired_ids:
                await uow_local.session.execute(
                    delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
                )
            await uow_local.commit()
    else:
        sent, expired, failed, expired_ids = await _send_for_user(ctx, user_id, payload)
        if expired_ids:
            await ctx.session.execute(
                delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
            )

    return PushSendResult(sent=sent, expired=expired, failed=failed)


async def send_push_broadcast(
    *,
    title: str,
    body: str,
    url: Optional[str] = None,
    uow: Optional[UnitOfWork] = None,
) -> PushSendResult:
    """Tüm aktif aboneliklere push gönderir (filo geneli uyarılar).

    Faz 4 tetikleyicileri (kritik anomali, muayene yaklaşan) bunu kullanır:
    tek-tenant ops aracında abone olan herkes ilgili personeldir. 410 Gone
    yanıtı alınan subscription kayıtları silinir.
    """
    if not _vapid_configured():
        logger.debug("VAPID not configured; skipping broadcast push")
        return PushSendResult(sent=0, expired=0, failed=0)

    payload = {"title": title, "body": body}
    if url:
        payload["url"] = url

    owns_uow = uow is None
    ctx = UnitOfWork() if owns_uow else uow
    assert ctx is not None

    if owns_uow:
        async with ctx as uow_local:
            result = await _send_for_all(uow_local, payload)
            await uow_local.commit()
            return result
    return await _send_for_all(ctx, payload)


async def _send_for_all(uow: UnitOfWork, payload: dict) -> PushSendResult:
    rows = await uow.session.execute(select(PushSubscription))
    subs = rows.scalars().all()
    sent = expired = failed = 0
    expired_ids: list[int] = []
    used_ids: list[int] = []
    for sub in subs:
        ok, gone = await _do_send(sub, payload)
        if ok:
            sent += 1
            used_ids.append(sub.id)
        elif gone:
            expired += 1
            expired_ids.append(sub.id)
        else:
            failed += 1
    if expired_ids:
        await uow.session.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
        )
    if used_ids:
        from datetime import datetime, timezone

        await uow.session.execute(
            update(PushSubscription)
            .where(PushSubscription.id.in_(used_ids))
            .values(last_used_at=datetime.now(timezone.utc))
        )
    return PushSendResult(sent=sent, expired=expired, failed=failed)


async def _send_for_user(
    uow: UnitOfWork, user_id: int, payload: dict
) -> tuple[int, int, int, list[int]]:
    rows = await uow.session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subs = rows.scalars().all()
    sent = expired = failed = 0
    expired_ids: list[int] = []
    used_ids: list[int] = []
    for sub in subs:
        ok, gone = await _do_send(sub, payload)
        if ok:
            sent += 1
            used_ids.append(sub.id)
        elif gone:
            expired += 1
            expired_ids.append(sub.id)
        else:
            failed += 1
    if used_ids:
        from datetime import datetime, timezone

        await uow.session.execute(
            update(PushSubscription)
            .where(PushSubscription.id.in_(used_ids))
            .values(last_used_at=datetime.now(timezone.utc))
        )
    return sent, expired, failed, expired_ids
