"""Reports v2 RV2.PWA — webpush_client (pywebpush I/O adapter) testleri."""

from __future__ import annotations

import sys
import types
from typing import Any, Optional

import pytest

pytestmark = pytest.mark.unit


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
async def test_do_send_handles_410_gone(monkeypatch):
    """send_webpush 410 Gone → (False, True) döndürmeli."""
    from v2.modules.notification.infrastructure import webpush_client

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
    ok, gone = await webpush_client.send_webpush(sub, {"title": "t"})
    assert ok is False
    assert gone is True


@pytest.mark.asyncio
async def test_do_send_handles_success(monkeypatch):
    """send_webpush başarılı → (True, False) döndürmeli."""
    from v2.modules.notification.infrastructure import webpush_client

    class _Dummy(Exception):
        pass

    def fake_webpush(**kwargs):
        return None  # başarı

    fake_module = types.ModuleType("pywebpush")
    fake_module.WebPushException = _Dummy  # type: ignore[attr-defined]
    fake_module.webpush = fake_webpush  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pywebpush", fake_module)

    sub = _FakeSub(1, "https://push/y")
    ok, gone = await webpush_client.send_webpush(sub, {"title": "t"})
    assert ok is True
    assert gone is False
