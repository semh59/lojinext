import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from v2.modules.admin_platform.api.admin_ws_routes import training_ws_manager
from v2.modules.auth_rbac.domain.jwt_handler import create_access_token

client = TestClient(app)


@pytest.mark.asyncio
async def test_ws_connection_unauthorized():
    """Verify that WS rejects connections without token."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/admin/ws/training"):
            pass
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_ws_connection_authorized(client):
    """Verify successful secure WS connection with token.

    Uses the `client` fixture (wires setup_test_db: real schema + seeded
    super-admin Kullanici row) so the WS endpoint's `_is_admin_email` DB
    lookup resolves the super-admin to an ADMIN-permission user.
    """
    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "typ": "access", "is_super": True}
    )

    with client.websocket_connect(
        f"/api/v1/admin/ws/training?token={token}"
    ) as websocket:
        websocket.send_text("ping")
        data = websocket.receive_json()
        assert data["type"] == "pong"


@pytest.mark.asyncio
async def test_ws_broadcast():
    """Verifies that manager correctly broadcasts to connected agents."""
    mock_ws = AsyncMock()
    training_ws_manager.user_connections = {"test@example.com": [mock_ws]}

    test_msg = {"event": "progress", "value": 45}
    await training_ws_manager.broadcast(test_msg)

    mock_ws.send_text.assert_called_once()
    sent_data = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent_data["value"] == 45

    training_ws_manager.user_connections = {}
