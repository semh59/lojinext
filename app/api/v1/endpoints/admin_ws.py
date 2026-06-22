import json
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import DomainError
from app.core.services.security_service import Permission, SecurityService
from app.database.connection import AsyncSessionLocal
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.token_blacklist import blacklist

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # user_email -> list of websockets
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        str_message = json.dumps(message)
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_text(str_message)
                except DomainError:
                    raise
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"WebSocket send error for user {user_id}: {e}")
                    self.disconnect(connection, user_id)

    async def broadcast(self, message: dict):
        str_message = json.dumps(message)
        for user_id, connections in list(self.user_connections.items()):
            for connection in connections:
                try:
                    await connection.send_text(str_message)
                except DomainError:
                    raise
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"WebSocket broadcast error: {e}")
                    self.disconnect(connection, user_id)


training_ws_manager = ConnectionManager()
notification_ws_manager = ConnectionManager()


async def verify_ws_ticket(ticket: str) -> Optional[str]:
    """Look up a short-lived WS ticket in Redis and return the owner's email."""
    from app.infrastructure.cache.redis_pubsub import get_redis_val

    email = await get_redis_val(f"ws_ticket:{ticket}")
    return email or None


async def verify_ws_token(token: str) -> Optional[str]:
    """Verify JWT for WebSocket — checks blacklist, aud/iss, and returns email."""
    if await blacklist.is_blacklisted(token):
        return None
    try:
        from app.infrastructure.security.jwt_handler import get_decode_key

        payload = jwt.decode(
            token,
            get_decode_key(),
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except jwt.PyJWTError:
        return None


async def _resolve_ws_identity(websocket: WebSocket) -> Optional[str]:
    """Prefer ?ticket= (short-lived, no JWT in URL) over ?token= (legacy)."""
    ticket = websocket.query_params.get("ticket")
    if ticket:
        return await verify_ws_ticket(ticket)
    token = websocket.query_params.get("token")
    if token:
        return await verify_ws_token(token)
    return None


async def _is_admin_email(email: str) -> bool:
    """Look up user by email and verify ADMIN permission.

    The synthetic super-admin (env ``SUPER_ADMIN_USERNAME``) has no ``kullanicilar``
    row, so the DB lookup would reject it → WS handshake 403. Grant it directly.
    """
    super_u = settings.SUPER_ADMIN_USERNAME
    if email and email in (super_u, f"{super_u}@lojinext.internal"):
        # deps.py resolves the synthetic super-admin to a virtual user whose
        # email is "{username}@lojinext.internal" (when username has no '@'),
        # which is what the WS ticket stores — match both forms.
        return True
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Kullanici)
            .options(selectinload(Kullanici.rol))
            .where(Kullanici.email == email, Kullanici.aktif.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        return SecurityService.has_permission(user, Permission.ADMIN)


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

    await training_ws_manager.connect(websocket, email)
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


@router.websocket("/live")
async def notifications_ws(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notifications.
    Accepts ?ticket= (preferred) or legacy ?token=.
    """
    email = await _resolve_ws_identity(websocket)
    if not email:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await _is_admin_email(email):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_ws_manager.connect(websocket, email)
    logger.info(f"User {email} connected to live notifications.")

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        notification_ws_manager.disconnect(websocket, email)
        logger.info(f"User {email} disconnected from live notifications.")
