"""notify_feedback best-effort davranışı (Faz 11)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.notifications import telegram_notifier as tn

pytestmark = pytest.mark.unit


class _Ctx:
    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *a):
        return False


async def test_notify_feedback_posts_to_webhook():
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    with patch.object(tn, "get_monitored_client", lambda timeout=None: _Ctx(client)):
        ok = await tn.notify_feedback(
            message="harika", username="admin", page="/route-lab"
        )
    assert ok is True
    args, kwargs = client.post.call_args
    assert args[0].endswith("/webhook/feedback")
    assert kwargs["json"]["message"] == "harika"
    assert kwargs["json"]["username"] == "admin"
    assert kwargs["json"]["page"] == "/route-lab"


async def test_notify_feedback_returns_false_when_ops_down():
    client = MagicMock()
    client.post = AsyncMock(side_effect=Exception("conn refused"))
    with (
        patch.object(tn, "get_monitored_client", lambda timeout=None: _Ctx(client)),
        patch.object(tn.asyncio, "sleep", AsyncMock()),
    ):
        ok = await tn.notify_feedback(message="x")
    assert ok is False
    assert client.post.call_count == 2  # 2 deneme
