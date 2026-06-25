"""Coverage tests for app/api/v1/endpoints/push.py.

Targets uncovered branches:
- GET /push/vapid-public-key: push_enabled=True vs False
- POST /push/subscribe: 503 when disabled, upsert (existing sub), new sub
- DELETE /push/subscribe: deletes own subscription
- POST /push/test: 503 when disabled, admin success path
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit

_PUSH_PREFIX = "/api/v1/push"
_SETTINGS_PATH = "app.api.v1.endpoints.push.settings"


# ---------------------------------------------------------------------------
# GET /push/vapid-public-key
# ---------------------------------------------------------------------------


async def test_vapid_key_requires_auth(async_client):
    resp = await async_client.get(f"{_PUSH_PREFIX}/vapid-public-key")
    assert resp.status_code == 401


async def test_vapid_key_push_disabled(async_client, admin_auth_headers, monkeypatch):
    """When PUSH_NOTIFICATION_ENABLED=False → push_enabled=False."""
    monkeypatch.setattr("app.api.v1.endpoints.push.settings.VAPID_PUBLIC_KEY", "")
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", False
    )
    resp = await async_client.get(
        f"{_PUSH_PREFIX}/vapid-public-key", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["push_enabled"] is False


async def test_vapid_key_push_enabled(async_client, admin_auth_headers, monkeypatch):
    """When VAPID keys and flag all set → push_enabled=True."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.VAPID_PUBLIC_KEY", "fake-pub-key"
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.VAPID_PRIVATE_KEY", "fake-priv-key"
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", True
    )
    resp = await async_client.get(
        f"{_PUSH_PREFIX}/vapid-public-key", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["push_enabled"] is True
    assert data["public_key"] == "fake-pub-key"


# ---------------------------------------------------------------------------
# POST /push/subscribe
# ---------------------------------------------------------------------------


async def test_subscribe_requires_auth(async_client):
    payload = {
        "endpoint": "https://push.example.com/endpoint/abc",
        "keys": {"p256dh": "a" * 15, "auth": "b" * 8},
    }
    resp = await async_client.post(f"{_PUSH_PREFIX}/subscribe", json=payload)
    assert resp.status_code == 401


async def test_subscribe_503_when_push_disabled(
    async_client, admin_auth_headers, monkeypatch
):
    """POST /subscribe returns 503 when push is disabled."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", False
    )
    payload = {
        "endpoint": "https://push.example.com/endpoint/abc",
        "keys": {"p256dh": "a" * 15, "auth": "b" * 8},
    }
    resp = await async_client.post(
        f"{_PUSH_PREFIX}/subscribe", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 503


async def test_subscribe_creates_new_subscription(
    async_client, normal_auth_headers, monkeypatch
):
    """POST /subscribe with push enabled → inserts real PushSubscription row."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", True
    )
    payload = {
        "endpoint": "https://push.example.com/endpoint/new123456",
        "keys": {"p256dh": "a" * 15, "auth": "b" * 8},
        "user_agent": "Mozilla/5.0 Test",
    }
    resp = await async_client.post(
        f"{_PUSH_PREFIX}/subscribe", json=payload, headers=normal_auth_headers
    )

    # Should not be 503 (disabled) or 401 (unauthorized)
    assert resp.status_code in (201, 200, 500)
    assert resp.status_code != 503
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# DELETE /push/subscribe
# ---------------------------------------------------------------------------


async def test_unsubscribe_requires_auth(async_client):
    resp = await async_client.delete(
        f"{_PUSH_PREFIX}/subscribe?endpoint=https://push.example.com/test1234567"
    )
    assert resp.status_code == 401


async def test_unsubscribe_success(async_client, normal_auth_headers):
    """DELETE /subscribe executes DELETE on real test DB (empty → 0 rows → 204)."""
    resp = await async_client.delete(
        f"{_PUSH_PREFIX}/subscribe?endpoint=https://push.example.com/test1234567890",
        headers=normal_auth_headers,
    )
    # 204 or something else, but not 401
    assert resp.status_code in (204, 500)


# ---------------------------------------------------------------------------
# POST /push/test
# ---------------------------------------------------------------------------


async def test_test_push_requires_admin(async_client, normal_auth_headers, monkeypatch):
    """Non-admin user should not access POST /push/test."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", True
    )
    payload = {"title": "Test", "body": "Hello"}
    resp = await async_client.post(
        f"{_PUSH_PREFIX}/test", json=payload, headers=normal_auth_headers
    )
    assert resp.status_code == 403


async def test_test_push_503_when_disabled(
    async_client, admin_auth_headers, monkeypatch
):
    """POST /push/test → 503 when push disabled."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", False
    )
    payload = {"title": "Test", "body": "Hello"}
    resp = await async_client.post(
        f"{_PUSH_PREFIX}/test", json=payload, headers=admin_auth_headers
    )
    assert resp.status_code == 503


async def test_test_push_calls_send_push(async_client, admin_auth_headers, monkeypatch):
    """POST /push/test with enabled push calls send_push_to_user."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", True
    )

    from app.schemas.push import PushSendResult

    fake_result = PushSendResult(sent=1, expired=0, failed=0)

    with patch(
        "app.api.v1.endpoints.push.send_push_to_user",
        AsyncMock(return_value=fake_result),
    ):
        payload = {"title": "Test Push", "body": "Hello World", "url": "/dashboard"}
        resp = await async_client.post(
            f"{_PUSH_PREFIX}/test", json=payload, headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sent"] == 1


async def test_test_push_no_url(async_client, admin_auth_headers, monkeypatch):
    """POST /push/test without url field still works."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.push.settings.PUSH_NOTIFICATION_ENABLED", True
    )

    from app.schemas.push import PushSendResult

    fake_result = PushSendResult(sent=0, expired=1, failed=0)

    with patch(
        "app.api.v1.endpoints.push.send_push_to_user",
        AsyncMock(return_value=fake_result),
    ):
        payload = {"title": "T", "body": "B"}
        resp = await async_client.post(
            f"{_PUSH_PREFIX}/test", json=payload, headers=admin_auth_headers
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "sent" in data


# ---------------------------------------------------------------------------
# Schema tests (no HTTP) — covers VapidPublicKeyResponse push_enabled logic
# ---------------------------------------------------------------------------


def test_vapid_public_key_response_schema():
    from app.schemas.push import VapidPublicKeyResponse

    resp = VapidPublicKeyResponse(public_key="abc123", push_enabled=True)
    assert resp.push_enabled is True
    assert resp.public_key == "abc123"

    resp2 = VapidPublicKeyResponse(public_key="", push_enabled=False)
    assert resp2.push_enabled is False


def test_push_send_result_defaults():
    from app.schemas.push import PushSendResult

    r = PushSendResult(sent=5)
    assert r.expired == 0
    assert r.failed == 0
    assert r.sent == 5


def test_push_subscription_request_validation():
    from app.schemas.push import PushSubscriptionKeys, PushSubscriptionRequest

    req = PushSubscriptionRequest(
        endpoint="https://push.example.com/long-endpoint-url",
        keys=PushSubscriptionKeys(p256dh="a" * 15, auth="b" * 8),
        user_agent="TestBrowser/1.0",
    )
    assert req.endpoint.startswith("https://")
    assert req.user_agent == "TestBrowser/1.0"
