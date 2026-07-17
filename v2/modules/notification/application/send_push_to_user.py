"""Reports v2 RV2.PWA — bir kullanıcının tüm aboneliklerine push gönderir."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from app.database.models import PushSubscription
from app.database.unit_of_work import UnitOfWork
from v2.modules.notification.domain.vapid import vapid_configured
from v2.modules.notification.infrastructure.webpush_client import send_webpush
from v2.modules.notification.schemas import PushSendResult

logger = logging.getLogger(__name__)


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
    if not vapid_configured():
        logger.debug("VAPID not configured; skipping push for user %s", user_id)
        return PushSendResult(sent=0, expired=0, failed=0)

    if respect_quiet_hours:
        from v2.modules.notification.application.quiet_hours import is_user_quiet_now

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

    # Bağımsız subscription'lara paralel gönder — sıralı `await` her push'u
    # (bloklayıcı-çağrı düzeltmesinden sonra bile) birbiri ardına bekletirdi.
    # send_webpush hiçbir shared/mutable state'e (uow.session) dokunmuyor,
    # yalnız `sub`'ın kendi alanlarını okuyor — paralelleştirmek güvenli.
    results = await asyncio.gather(*(send_webpush(sub, payload) for sub in subs))
    for sub, (ok, gone) in zip(subs, results):
        if ok:
            sent += 1
            used_ids.append(sub.id)
        elif gone:
            expired += 1
            expired_ids.append(sub.id)
        else:
            failed += 1
    if used_ids:
        await uow.session.execute(
            update(PushSubscription)
            .where(PushSubscription.id.in_(used_ids))
            .values(last_used_at=datetime.now(timezone.utc))
        )
    return sent, expired, failed, expired_ids
