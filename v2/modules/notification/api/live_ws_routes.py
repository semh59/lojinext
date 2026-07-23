"""Notification live-feed WebSocket.

URL kontratı KORUNDU: /admin/ws/live (frontend NotificationContext.tsx +
useMonitoringSocket.ts bunu bekliyor) — bu router api.py'de admin_ws.router
(/training) ile AYNI "/admin/ws" prefix'i altına mount edilir, iki ayrı
router objesi aynı path prefix'ini paylaşır (FastAPI bunu destekler).
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from v2.modules.notification.infrastructure.ws_broadcaster import (
    notification_ws_manager,
)
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.websocket.ws_auth import (
    is_admin_email,
    resolve_ws_identity,
)

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/live")
async def notifications_ws(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notifications.
    Accepts ?ticket= (preferred) or legacy ?token=.
    """
    email = await resolve_ws_identity(websocket)
    if not email:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await is_admin_email(email):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await notification_ws_manager.connect(websocket, email):
        logger.warning(f"WebSocket connection limit reached for user {email}.")
        return
    logger.info(f"User {email} connected to live notifications.")

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        notification_ws_manager.disconnect(websocket, email)
        logger.info(f"User {email} disconnected from live notifications.")
