import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.websocket.connection_manager import ConnectionManager
from app.infrastructure.websocket.ws_auth import is_admin_email, resolve_ws_identity

logger = get_logger(__name__)

router = APIRouter()


training_ws_manager = ConnectionManager()

# Kept as module-level re-exports: some call sites / tests patch these names
# on this module rather than on app.infrastructure.websocket.ws_auth.
_resolve_ws_identity = resolve_ws_identity
_is_admin_email = is_admin_email


@router.websocket("/training")
async def training_status_ws(websocket: WebSocket):
    """
    WebSocket endpoint for streaming real-time ML Training Progress.
    Accepts ?ticket= (preferred) or legacy ?token=.
    """
    email = await _resolve_ws_identity(websocket)
    if not email:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await _is_admin_email(email):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await training_ws_manager.connect(websocket, email):
        logger.warning(f"WebSocket connection limit reached for user {email}.")
        return
    logger.info(f"WebSocket User {email} connected to training monitor.")

    try:
        while True:
            # We just keep the connection open and wait for messages.
            # Client can send simple 'ping' requests
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        training_ws_manager.disconnect(websocket, email)
        logger.info(f"WebSocket User {email} disconnected from training monitor.")
