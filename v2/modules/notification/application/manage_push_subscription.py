"""Use-case'ler: Web Push subscription yaşam döngüsü (`push_subscriptions`).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/push_routes.py``'nin ``subscribe``/
``unsubscribe`` handler'ları daha önce ``application/`` katmanını atlayıp
doğrudan ``uow.session``/``PushSubscription`` ORM'ine erişiyordu.

🔴 **Gerçek bug bulundu ve düzeltildi (mekanik taşımanın ötesinde, tek
davranış değişikliği):** eski ``unsubscribe`` handler'ı ``uow.commit()``
hiç ÇAĞIRMIYORDU. ``UnitOfWork.__aexit__``'in ghost-transaction guard'ı
yalnız ORM identity-map'i (``session.new``/``dirty``/``deleted``) kontrol
eder — Core-tarzı ``session.execute(delete(...))`` bulk-delete bu
koleksiyonlara hiç dokunmaz, dolayısıyla guard hiç tetiklenmiyordu ve
``async with UnitOfWork()`` "temiz çıkış (read-only), sadece kapat" dalına
düşüp DELETE'i **rollback ediyordu**. Sonuç: ``DELETE /push/subscribe``
200/204 dönüyordu ama satır veritabanında kalıyordu — kullanıcı asla
gerçekten unsubscribe olamıyordu. Bu bug taşımadan ÖNCE de vardı
(``git show 78fd145:v2/modules/notification/api/push_routes.py`` ile
doğrulandı); B.1 taşıması sırasında fonksiyonu buraya taşırken fark edildi,
tek satırlık düzeltmesi (``await uow.commit()``) davranış-genişletici değil
sadece dokümante edilen bug'ı kapatıyor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select

from v2.modules.notification.infrastructure.models import PushSubscription
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def subscribe_push(
    user_id: int,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: Optional[str],
) -> PushSubscription:
    """Yeni subscription kaydı (endpoint unique → upsert)."""
    async with UnitOfWork() as uow:
        existing = await uow.session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        sub = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if sub is not None:
            sub.user_id = user_id
            sub.p256dh = p256dh
            sub.auth = auth
            sub.user_agent = user_agent
            sub.last_used_at = now
        else:
            sub = PushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent,
                last_used_at=now,
            )
            uow.session.add(sub)
        await uow.session.flush()
        await uow.session.refresh(sub)
        await uow.commit()
        return sub


async def unsubscribe_push(user_id: int, endpoint: str) -> None:
    """Bir endpoint için subscription sil — yalnız kendi kayıtları."""
    async with UnitOfWork() as uow:
        await uow.session.execute(
            delete(PushSubscription).where(
                PushSubscription.endpoint == endpoint,
                PushSubscription.user_id == user_id,
            )
        )
        await uow.commit()
