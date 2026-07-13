"""Live-notification WebSocket broadcast channel.

Uses the shared ``ConnectionManager`` (app/infrastructure/websocket —
also used by admin_ws.py's unrelated ``/training`` stream, see that
module's docstring for why the connection bookkeeping is shared but the
managers are separate instances per channel).
"""

from __future__ import annotations

from app.infrastructure.websocket.connection_manager import ConnectionManager

notification_ws_manager = ConnectionManager()
