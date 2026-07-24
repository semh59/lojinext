"""Reports v2 RV2.PWA — send_push_to_user use-case testleri."""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

pytestmark = pytest.mark.unit

# ── Fake DB layer ─────────────────────────────────────────────────────


class _FakeScalarsResult:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def scalars(self):
        return _FakeScalarsResult(self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, subs: List[Any]) -> None:
        self.subs = subs
        self.deleted: list[Any] = []
        self.updated: list[dict] = []
        self.added: list[Any] = []

    async def execute(self, query: Any):
        # FAZ2 (schema-per-module): PushSubscription now compiles to
        # "DELETE FROM notification.push_subscriptions ..." — match the
        # bare table name suffix, not a schema-qualified literal.
        text = str(query).lower()
        if "delete from" in text and "push_subscriptions" in text:
            self.deleted.append(query)
            return _FakeResult([])
        if "update" in text and "push_subscriptions" in text:
            self.updated.append({"q": str(query)})
            return _FakeResult([])
        # SELECT
        return _FakeResult(self.subs)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        return None


class _FakeUoW:
    def __init__(self, subs: List[Any]) -> None:
        self.session = _FakeSession(subs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


# ── Fake subscription objects ─────────────────────────────────────────


class _FakeSub:
    def __init__(
        self,
        sub_id: int,
        endpoint: str,
        p256dh: str = "p256dh-key",
        auth: str = "auth-key",
        user_id: int = 7,
    ) -> None:
        self.id = sub_id
        self.endpoint = endpoint
        self.p256dh = p256dh
        self.auth = auth
        self.user_id = user_id
        self.last_used_at: Optional[Any] = None
        self.user_agent: Optional[str] = None


@pytest.mark.asyncio
async def test_send_push_skipped_when_vapid_not_configured(monkeypatch):
    """VAPID ayarsızsa send_push_to_user 0 sent döndürür ve DB'ye dokunmaz."""
    from app.config import settings as app_settings
    from v2.modules.notification.application import send_push_to_user as mod

    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", False)

    result = await mod.send_push_to_user(user_id=99, title="t", body="b")
    assert result.sent == 0
    assert result.expired == 0
    assert result.failed == 0


@pytest.mark.asyncio
async def test_send_push_expired_subscription_deleted(monkeypatch):
    """410 Gone alındığında expired counter artar, kayıt silinir."""
    from app.config import settings as app_settings
    from v2.modules.notification.application import send_push_to_user as mod

    # VAPID configured
    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)

    subs = [_FakeSub(1, "https://push/a"), _FakeSub(2, "https://push/b")]
    fake_uow = _FakeUoW(subs)

    # send_webpush stub: ilki expired, ikincisi başarılı
    call_count = {"n": 0}

    async def fake_send_webpush(sub, payload):
        call_count["n"] += 1
        if sub.id == 1:
            return (False, True)  # expired
        return (True, False)

    monkeypatch.setattr(mod, "send_webpush", fake_send_webpush)

    result = await mod.send_push_to_user(user_id=7, title="x", body="y", uow=fake_uow)

    assert result.sent == 1
    assert result.expired == 1
    assert result.failed == 0
    # delete sql çağrıldı
    assert len(fake_uow.session.deleted) == 1
    # update last_used_at çağrıldı (used_ids=[2])
    assert len(fake_uow.session.updated) == 1


@pytest.mark.asyncio
async def test_send_push_failed_subscription_not_deleted(monkeypatch):
    """non-410 hatası → failed counter artar ama kayıt silinmez."""
    from app.config import settings as app_settings
    from v2.modules.notification.application import send_push_to_user as mod

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)

    subs = [_FakeSub(1, "https://push/a")]
    fake_uow = _FakeUoW(subs)

    async def fake_send_webpush(sub, payload):
        return (False, False)  # transient failure

    monkeypatch.setattr(mod, "send_webpush", fake_send_webpush)

    result = await mod.send_push_to_user(user_id=7, title="x", body="y", uow=fake_uow)

    assert result.sent == 0
    assert result.expired == 0
    assert result.failed == 1
    # delete çağrılmadı
    assert len(fake_uow.session.deleted) == 0
