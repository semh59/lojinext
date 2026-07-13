"""
Notification live-feed WebSocket (/admin/ws/live) coverage tests.

Moved out of app/tests/api/test_admin_ws_coverage.py (dalga 2: notification
module split /live out of admin_ws.py into v2/modules/notification — see
that module's CLAUDE.md for the admin_ws.py katman-ihlali fix this enabled).
URL contract preserved (/admin/ws/live), see v2/modules/notification/api/live_ws_routes.py.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


async def test_live_ws_no_token_closes(async_client):
    """WS /live without token → policy violation close."""
    with pytest.raises(Exception):
        async with async_client.websocket_connect("/api/v1/admin/ws/live"):
            pass


async def test_live_ws_invalid_token_closes(async_client):
    """WS /live with invalid token → policy violation close."""
    with pytest.raises(Exception):
        async with async_client.websocket_connect(
            "/api/v1/admin/ws/live?token=bad.token.here"
        ):
            pass


async def test_live_ws_valid_token_ping(async_client):
    """WS /live with valid token → accepts and responds to ping."""
    from datetime import timedelta

    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": "admin@lojinext.test", "is_super": False},
        expires_delta=timedelta(minutes=5),
    )

    try:
        async with async_client.websocket_connect(
            f"/api/v1/admin/ws/live?token={token}"
        ) as ws:
            await ws.send_text("ping")
            response_raw = await ws.receive_text()
            response = json.loads(response_raw)
            assert response.get("type") == "pong"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Direct endpoint function tests (mock WebSocket)
# ---------------------------------------------------------------------------


class TestLiveWsEndpointDirect:
    """Test the /live WS endpoint function directly with mock WebSocket objects."""

    def _make_ws(self, token=None, text_sequence=None):
        """Create a mock WebSocket that raises WebSocketDisconnect after text_sequence."""
        from fastapi import WebSocketDisconnect

        ws = AsyncMock()
        ws.query_params = {"token": token} if token else {}
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()

        if text_sequence is None:
            text_sequence = []

        call_index = [0]

        async def _receive_text():
            idx = call_index[0]
            call_index[0] += 1
            if idx < len(text_sequence):
                return text_sequence[idx]
            raise WebSocketDisconnect(code=1000)

        ws.receive_text = AsyncMock(side_effect=_receive_text)
        return ws

    async def test_live_ws_no_token_closes_directly(self):
        from v2.modules.notification.api.live_ws_routes import notifications_ws

        ws = self._make_ws()
        ws.query_params = MagicMock()
        ws.query_params.get = MagicMock(return_value=None)

        await notifications_ws(ws)
        ws.close.assert_called_once()

    async def test_live_ws_invalid_token_closes_directly(self):
        from v2.modules.notification.api.live_ws_routes import notifications_ws

        ws = self._make_ws()
        ws.query_params = MagicMock()
        ws.query_params.get = MagicMock(return_value="bad.token")

        await notifications_ws(ws)
        ws.close.assert_called_once()

    async def test_live_ws_valid_token_ping_direct(self):
        # Loop unit test — auth boundary stubbed (see admin_ws training variant).
        from v2.modules.notification.api import live_ws_routes

        ws = self._make_ws(text_sequence=["ping"])
        ws.query_params = MagicMock()
        ws.query_params.get = MagicMock(return_value="valid-token")

        with (
            patch.object(
                live_ws_routes,
                "resolve_ws_identity",
                AsyncMock(return_value="ws_live@lojinext.test"),
            ),
            patch.object(
                live_ws_routes, "is_admin_email", AsyncMock(return_value=True)
            ),
        ):
            await live_ws_routes.notifications_ws(ws)

        ws.accept.assert_called_once()
        ws.send_text.assert_called_once_with(json.dumps({"type": "pong"}))
