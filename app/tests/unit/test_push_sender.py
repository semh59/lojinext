"""Reports v2 RV2.PWA — Push sender + endpoint testleri."""

from __future__ import annotations

import sys
import types
from typing import Any, List, Optional

import pytest

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
        text = str(query).lower()
        if "delete from push_subscriptions" in text:
            self.deleted.append(query)
            return _FakeResult([])
        if "update push_subscriptions" in text:
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


# ── _vapid_configured + send tests ────────────────────────────────────


def test_vapid_configured_requires_all_three_keys(monkeypatch):
    """3 anahtar veya flag eksikse VAPID configured döndürmemeli."""
    from app.config import settings as app_settings
    from app.core.services.push_sender import _vapid_configured

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "x")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)
    assert _vapid_configured() is False

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", False)
    assert _vapid_configured() is False

    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)
    assert _vapid_configured() is True


@pytest.mark.asyncio
async def test_send_push_skipped_when_vapid_not_configured(monkeypatch):
    """VAPID ayarsızsa send_push_to_user 0 sent döndürür ve DB'ye dokunmaz."""
    from app.config import settings as app_settings
    from app.core.services import push_sender

    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", False)

    result = await push_sender.send_push_to_user(user_id=99, title="t", body="b")
    assert result.sent == 0
    assert result.expired == 0
    assert result.failed == 0


@pytest.mark.asyncio
async def test_send_push_expired_subscription_deleted(monkeypatch):
    """410 Gone alındığında expired counter artar, kayıt silinir."""
    from app.config import settings as app_settings
    from app.core.services import push_sender

    # VAPID configured
    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)

    subs = [_FakeSub(1, "https://push/a"), _FakeSub(2, "https://push/b")]
    fake_uow = _FakeUoW(subs)

    # _do_send stub: ilki expired, ikincisi başarılı
    call_count = {"n": 0}

    async def fake_do_send(sub, payload):
        call_count["n"] += 1
        if sub.id == 1:
            return (False, True)  # expired
        return (True, False)

    monkeypatch.setattr(push_sender, "_do_send", fake_do_send)

    result = await push_sender.send_push_to_user(
        user_id=7, title="x", body="y", uow=fake_uow
    )

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
    from app.core.services import push_sender

    monkeypatch.setattr(app_settings, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(app_settings, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(app_settings, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(app_settings, "PUSH_NOTIFICATION_ENABLED", True)

    subs = [_FakeSub(1, "https://push/a")]
    fake_uow = _FakeUoW(subs)

    async def fake_do_send(sub, payload):
        return (False, False)  # transient failure

    monkeypatch.setattr(push_sender, "_do_send", fake_do_send)

    result = await push_sender.send_push_to_user(
        user_id=7, title="x", body="y", uow=fake_uow
    )

    assert result.sent == 0
    assert result.expired == 0
    assert result.failed == 1
    # delete çağrılmadı
    assert len(fake_uow.session.deleted) == 0


@pytest.mark.asyncio
async def test_do_send_handles_410_gone(monkeypatch):
    """_do_send 410 Gone → (False, True) döndürmeli."""
    from app.core.services import push_sender

    # Fake pywebpush — sys.modules üzerinden inject
    class _FakeResp:
        status_code = 410

    class _FakeWebPushException(Exception):
        def __init__(self, msg: str, response=None):
            super().__init__(msg)
            self.response = response

    def fake_webpush(**kwargs):
        raise _FakeWebPushException("expired", response=_FakeResp())

    fake_module = types.ModuleType("pywebpush")
    fake_module.WebPushException = _FakeWebPushException  # type: ignore[attr-defined]
    fake_module.webpush = fake_webpush  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pywebpush", fake_module)

    sub = _FakeSub(1, "https://push/x")
    ok, gone = await push_sender._do_send(sub, {"title": "t"})
    assert ok is False
    assert gone is True


@pytest.mark.asyncio
async def test_do_send_handles_success(monkeypatch):
    """_do_send başarılı → (True, False) döndürmeli."""
    from app.core.services import push_sender

    class _Dummy(Exception):
        pass

    def fake_webpush(**kwargs):
        return None  # başarı

    fake_module = types.ModuleType("pywebpush")
    fake_module.WebPushException = _Dummy  # type: ignore[attr-defined]
    fake_module.webpush = fake_webpush  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pywebpush", fake_module)

    sub = _FakeSub(1, "https://push/y")
    ok, gone = await push_sender._do_send(sub, {"title": "t"})
    assert ok is True
    assert gone is False
