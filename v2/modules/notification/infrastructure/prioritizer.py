"""Faz 5 — bildirim önceliklendirme: DB-sorgulu adaptör.

STATUS: ``NotificationPrioritizer`` hiçbir prod kod tarafından
çağrılmıyor — repo-genelinde dead code (yalnız kendi testlerinde
kullanılıyor). location modülünün taşınan-ama-ölü event publish
dekoratörüyle aynı durum; bu taşıma sırasında bir regresyon değil,
taşınırken keşfedilen pre-existing bir boşluk. Sessizce atılmadı,
buraya dokümante edildi.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select

from v2.modules.notification.domain.prioritizer import score_priority


class NotificationPrioritizer:
    """bildirim_gecmisi okuma oranından kullanıcı+olay_tipi önceliği."""

    def __init__(self, session: Any) -> None:
        self.session = session

    async def priority_for(self, *, user_id: int, olay_tipi: Optional[str]) -> str:
        from app.database.models import BildirimGecmisi

        if not olay_tipi:
            return "normal"
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(BildirimGecmisi)
                .where(BildirimGecmisi.kullanici_id == user_id)
                .where(BildirimGecmisi.olay_tipi == olay_tipi)
            )
        ).scalar() or 0
        read = (
            await self.session.execute(
                select(func.count())
                .select_from(BildirimGecmisi)
                .where(BildirimGecmisi.kullanici_id == user_id)
                .where(BildirimGecmisi.olay_tipi == olay_tipi)
                .where(BildirimGecmisi.okundu_tarihi.isnot(None))
            )
        ).scalar() or 0
        return score_priority(read=int(read), total=int(total))
