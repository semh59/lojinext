"""Shared WebSocket admin-auth helpers.

Used by both admin_ws.py's ``/training`` stream and the notification
module's ``/live`` stream. See connection_manager.py for why this is a
shared infra module rather than owned by either.
"""

from __future__ import annotations

from typing import Optional

import jwt
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from v2.modules.auth_rbac.public import (
    Kullanici,
    Permission,
    SecurityService,
    blacklist,
)
from v2.modules.platform_infra.database.connection import AsyncSessionLocal


async def verify_ws_ticket(ticket: str) -> Optional[str]:
    """Look up a short-lived WS ticket in Redis and return the owner's email."""
    from v2.modules.platform_infra.cache.redis_pubsub import get_redis_val

    email = await get_redis_val(f"ws_ticket:{ticket}")
    return email or None


async def verify_ws_token(token: str) -> Optional[str]:
    """Verify JWT for WebSocket — checks blacklist, aud/iss, and returns email."""
    if await blacklist.is_blacklisted(token):
        return None
    try:
        from v2.modules.auth_rbac.public import get_decode_key

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


async def resolve_ws_identity(websocket: WebSocket) -> Optional[str]:
    """Prefer ?ticket= (short-lived, no JWT in URL) over ?token= (legacy)."""
    ticket = websocket.query_params.get("ticket")
    if ticket:
        return await verify_ws_ticket(ticket)
    token = websocket.query_params.get("token")
    if token:
        return await verify_ws_token(token)
    return None


async def is_admin_email(email: str) -> bool:
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
        from app.infrastructure.security.pii_encryption import blind_index

        result = await session.execute(
            select(Kullanici)
            .options(selectinload(Kullanici.rol))
            .where(
                Kullanici.email_bidx == blind_index(email), Kullanici.aktif.is_(True)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            return False
        return SecurityService.has_permission(user, Permission.ADMIN)
