"""Sessiz saat helper testleri."""

from datetime import time

import pytest

from v2.modules.notification.application.quiet_hours import is_within_quiet_hours

pytestmark = pytest.mark.unit


def _prefs(enabled, start, end):
    return {"enabled": enabled, "start": start, "end": end}


def test_disabled_never_quiet():
    assert is_within_quiet_hours(_prefs(False, "22:00", "07:00"), time(23, 0)) is False


def test_overnight_range_inside():
    p = _prefs(True, "22:00", "07:00")
    assert is_within_quiet_hours(p, time(23, 30)) is True
    assert is_within_quiet_hours(p, time(6, 0)) is True


def test_overnight_range_outside():
    p = _prefs(True, "22:00", "07:00")
    assert is_within_quiet_hours(p, time(12, 0)) is False


def test_same_day_range():
    p = _prefs(True, "09:00", "17:00")
    assert is_within_quiet_hours(p, time(10, 0)) is True
    assert is_within_quiet_hours(p, time(20, 0)) is False


def test_malformed_prefs_safe():
    assert is_within_quiet_hours({}, time(3, 0)) is False
    assert is_within_quiet_hours({"enabled": True, "start": "x"}, time(3, 0)) is False


@pytest.mark.asyncio
async def test_send_push_skipped_during_quiet_hours(monkeypatch):
    """respect_quiet_hours=True + kullanıcı sessizse push atlanır (DB'ye dokunmadan)."""
    from unittest.mock import AsyncMock

    from app.config import settings as s
    from v2.modules.notification.application import send_push_to_user as send_push_mod

    monkeypatch.setattr(s, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(s, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(s, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(s, "PUSH_NOTIFICATION_ENABLED", True)
    monkeypatch.setattr(
        "v2.modules.notification.application.quiet_hours.is_user_quiet_now",
        AsyncMock(return_value=True),
    )

    result = await send_push_mod.send_push_to_user(
        7, title="t", body="b", respect_quiet_hours=True
    )
    assert result.sent == 0
    assert result.expired == 0
    assert result.failed == 0
