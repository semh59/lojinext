"""Reports v2 RV2.PWA — VAPID config check testleri."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_vapid_configured_requires_all_three_keys(monkeypatch):
    """3 anahtar veya flag eksikse VAPID configured döndürmemeli."""
    from app.config import settings as app_settings
    from v2.modules.notification.domain.vapid import vapid_configured

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "x")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)
    assert vapid_configured() is False

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", False)
    assert vapid_configured() is False

    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)
    assert vapid_configured() is True
