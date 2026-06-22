"""Faz 5 — bildirim önceliklendirme: kullanıcı geçmiş okuma davranışı.

olay_tipi bazlı okuma oranı (okundu/toplam) → öncelik. Yeterli geçmiş yoksa
'normal'. Yüksek okuma oranı = kullanıcı umursuyor = high; düşük = low.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select

# Anlamlı bir oran için minimum geçmiş örnek sayısı.
_MIN_HISTORY = 5
_HIGH_THRESHOLD = 0.6
_LOW_THRESHOLD = 0.2


def score_priority(*, read: int, total: int) -> str:
    """Okuma oranından öncelik döndürür: 'high' | 'normal' | 'low'."""
    if total < _MIN_HISTORY:
        return "normal"
    rate = read / total
    if rate >= _HIGH_THRESHOLD:
        return "high"
    if rate <= _LOW_THRESHOLD:
        return "low"
    return "normal"


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
