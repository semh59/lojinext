"""POST /feedback endpoint (Faz 11)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

pytestmark = pytest.mark.unit


def _client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _override_user():
    from app.main import app
    from v2.modules.auth_rbac.public import get_current_active_user

    fake = MagicMock()
    fake.id = 1
    fake.aktif = True
    fake.kullanici_adi = "operator1"

    async def _fake():
        return fake

    app.dependency_overrides[get_current_active_user] = _fake
    return app


async def test_feedback_returns_202_and_calls_notifier():
    app = await _override_user()
    with patch(
        "v2.modules.ai_assistant.api.feedback_routes.notify_feedback",
        new=AsyncMock(return_value=True),
    ) as mock_notify:
        try:
            async with _client() as client:
                resp = await client.post(
                    "/api/v1/feedback/",
                    json={"message": "harika araç", "page": "/route-lab"},
                )
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 202
    mock_notify.assert_awaited_once()
    kwargs = mock_notify.await_args.kwargs
    assert kwargs["message"] == "harika araç"
    assert kwargs["page"] == "/route-lab"
    assert kwargs["username"] == "operator1"


async def test_feedback_still_202_when_ops_delivery_fails():
    app = await _override_user()
    with patch(
        "v2.modules.ai_assistant.api.feedback_routes.notify_feedback",
        new=AsyncMock(return_value=False),
    ):
        try:
            async with _client() as client:
                resp = await client.post("/api/v1/feedback/", json={"message": "x"})
        finally:
            app.dependency_overrides.clear()
    assert resp.status_code == 202


async def test_feedback_rejects_empty_message():
    app = await _override_user()
    try:
        async with _client() as client:
            resp = await client.post("/api/v1/feedback/", json={"message": ""})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422
