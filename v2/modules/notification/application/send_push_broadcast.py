"""Reports v2 RV2.PWA — tüm aktif aboneliklere push gönderir (filo geneli uyarılar)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update

from app.database.unit_of_work import UnitOfWork
from v2.modules.notification.domain.vapid import vapid_configured
from v2.modules.notification.infrastructure.models import PushSubscription
from v2.modules.notification.infrastructure.webpush_client import send_webpush
from v2.modules.notification.schemas import PushSendResult

logger = logging.getLogger(__name__)


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
    if not vapid_configured():
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

    # Filo geneli broadcast — sıralı gönderim en kötü durumda (fleet ölçekli
    # abone sayısı) event loop'u N ardışık HTTPS round-trip boyunca bloke
    # ederdi. send_webpush hiçbir shared/mutable state'e dokunmuyor,
    # paralelleştirmek güvenli (2026-07-16 dedektif denetimi bulgusu).
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
    if expired_ids:
        await uow.session.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
        )
    if used_ids:
        await uow.session.execute(
            update(PushSubscription)
            .where(PushSubscription.id.in_(used_ids))
            .values(last_used_at=datetime.now(timezone.utc))
        )
    return PushSendResult(sent=sent, expired=expired, failed=failed)
