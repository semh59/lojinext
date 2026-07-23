"""Shared per-user WebSocket connection registry.

`app/infrastructure/websocket/connection_manager.py`'den dalga 17
(platform_infra) denetiminde taşındı.

Used by admin_ws.py's ``/training`` stream and the notification module's
``/live`` stream — two functionally unrelated broadcast channels that share
the same connect/disconnect/send bookkeeping. Extracted here (rather than
duplicated or owned by one of the two modules) so neither module depends on
the other's internals.
"""

from __future__ import annotations

import json

from fastapi import HTTPException, WebSocket, status

from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.exceptions import DomainError

logger = get_logger(__name__)

_MAX_CONNECTIONS_PER_USER = 5


class ConnectionManager:
    def __init__(self):
        # user_email -> list of websockets
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """Accept the connection unless the user already has
        ``_MAX_CONNECTIONS_PER_USER`` open sockets on this manager.

        2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 21): eskiden
        bağlantı sayısı hiç sınırlanmıyordu — aynı kullanıcı sınırsız WS
        bağlantısı açabiliyordu (reconnect storm/DoS). Limit aşılırsa
        bağlantı kabul edilmeden 1008 (Policy Violation) ile kapatılır.

        Returns:
            True — bağlantı kabul edildi. False — limit aşıldığı için
            reddedildi (çağıran receive döngüsüne girmemeli).
        """
        if len(self.user_connections.get(user_id, [])) >= _MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        return True

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
