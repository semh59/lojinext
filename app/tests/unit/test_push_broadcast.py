"""Faz 4 — send_push_broadcast (filo geneli push) testleri."""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

pytestmark = pytest.mark.unit


class _FakeScalars:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self, subs: List[Any]) -> None:
        self.subs = subs
        self.deleted: list[Any] = []
        self.updated: list[Any] = []

    async def execute(self, query: Any):
        text = str(query).lower()
        if "delete from push_subscriptions" in text:
            self.deleted.append(query)
            return _FakeResult([])
        if "update push_subscriptions" in text:
            self.updated.append(query)
            return _FakeResult([])
        return _FakeResult(self.subs)


class _FakeUoW:
    def __init__(self, subs: List[Any]) -> None:
        self.session = _FakeSession(subs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeSub:
    def __init__(self, sub_id: int, user_id: int) -> None:
        self.id = sub_id
        self.endpoint = f"https://push/{sub_id}"
        self.p256dh = "p"
        self.auth = "a"
        self.user_id = user_id
        self.last_used_at: Optional[Any] = None


def _enable_vapid(monkeypatch):
    from app.config import settings as s

    monkeypatch.setattr(s, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(s, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(s, "VAPID_SUBJECT", "mailto:a@b")
    monkeypatch.setattr(s, "PUSH_NOTIFICATION_ENABLED", True)


@pytest.mark.asyncio
async def test_broadcast_skipped_when_vapid_unconfigured(monkeypatch):
    from app.config import settings as s
    from app.core.services import push_sender

    monkeypatch.setattr(s, "PUSH_NOTIFICATION_ENABLED", False)
    result = await push_sender.send_push_broadcast(title="t", body="b")
    assert result.sent == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_users_and_cleans_expired(monkeypatch):
    from app.core.services import push_sender

    _enable_vapid(monkeypatch)
    # Farklı kullanıcılara ait 3 abonelik (broadcast hepsine gitmeli)
    subs = [_FakeSub(1, user_id=7), _FakeSub(2, user_id=8), _FakeSub(3, user_id=9)]
    fake_uow = _FakeUoW(subs)

    async def fake_do_send(sub, payload):
        if sub.id == 2:
            return (False, True)  # expired (410)
        return (True, False)

    monkeypatch.setattr(push_sender, "_do_send", fake_do_send)

    result = await push_sender.send_push_broadcast(
        title="Kritik", body="3 uyarı", uow=fake_uow
    )

    assert result.sent == 2
    assert result.expired == 1
    assert result.failed == 0
    # expired olan silindi, kullanılanlar last_used güncellendi
    assert len(fake_uow.session.deleted) == 1
    assert len(fake_uow.session.updated) == 1
