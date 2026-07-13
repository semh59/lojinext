"""Reports v2 RV2.PWA — VAPID yapılandırma kontrolü (saf, I/O'suz)."""

from __future__ import annotations

from app.config import settings


def vapid_configured() -> bool:
    return bool(
        settings.VAPID_PUBLIC_KEY
        and settings.VAPID_PRIVATE_KEY
        and settings.VAPID_SUBJECT
        and settings.PUSH_NOTIFICATION_ENABLED
    )
