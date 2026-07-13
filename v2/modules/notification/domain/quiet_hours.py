"""Faz 5 — sessiz saatler.

/preferences (modul='bildirim', ayar_tipi='quiet_hours',
deger={enabled, start 'HH:MM', end 'HH:MM'}) ile saklanır.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

_APP_TZ = ZoneInfo("Europe/Istanbul")


def _parse(hhmm: Any) -> Optional[time]:
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return None
    try:
        h, m = hhmm.split(":", 1)
        return time(int(h), int(m))
    except (ValueError, TypeError):
        return None


def is_within_quiet_hours(deger: dict, now_t: time) -> bool:
    """deger sözlüğüne göre now_t sessiz saat aralığında mı.

    Gece-aşırı aralıkları (22:00→07:00) doğru ele alır. Hatalı/eksik
    ayar → False (güvenli; sessiz değil).
    """
    if not isinstance(deger, dict) or not deger.get("enabled"):
        return False
    start = _parse(deger.get("start"))
    end = _parse(deger.get("end"))
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_t <= end
    # gece-aşırı: start..gece yarısı veya gece yarısı..end
    return now_t >= start or now_t <= end


async def is_user_quiet_now(user_id: int, *, now: Optional[datetime] = None) -> bool:
    """Kullanıcının /preferences sessiz saat ayarına göre şu an sessiz mi.

    Çapraz-modül bağımlılık (geçici, dokümante): PreferenceService henüz
    v2'ye taşınmadı (bkz. CLAUDE.md).
    """
    try:
        from app.core.services.preference_service import PreferenceService

        items = await PreferenceService().get_preferences(
            user_id, "bildirim", "quiet_hours"
        )
    except Exception:  # noqa: BLE001 — pref okunamazsa sessiz değil say
        return False
    if not items:
        return False
    first = items[0]
    deger = (
        first.get("deger") if isinstance(first, dict) else getattr(first, "deger", None)
    )
    if not isinstance(deger, dict):
        return False
    # HH:MM ayarları kullanıcı-yerel zaman diliminde girilir (Türkiye UTC+3).
    # UTC anını yerel saate çevirerek karşılaştır.
    utc_now = now or datetime.now(timezone.utc)
    current = utc_now.astimezone(_APP_TZ).time()
    return is_within_quiet_hours(deger, current)
