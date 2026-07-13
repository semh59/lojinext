"""Faz 5 — bildirim önceliklendirme: kullanıcı geçmiş okuma davranışı (saf kural).

olay_tipi bazlı okuma oranı (okundu/toplam) → öncelik. Yeterli geçmiş yoksa
'normal'. Yüksek okuma oranı = kullanıcı umursuyor = high; düşük = low.

I/O gerektiren kısım (DB'den read/total sayımı) için bkz.
`infrastructure/prioritizer.py`'deki `NotificationPrioritizer`.
"""

from __future__ import annotations

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
