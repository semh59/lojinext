"""
Shared WebSocket infra coverage tests.

Targets app/infrastructure/websocket/{connection_manager,ws_auth}.py — used
by both admin_ws.py's /training stream and the notification module's /live
stream. Split out of the old (pre-dalga-2) test_admin_ws_coverage.py, which
tested these via the admin_ws module before the shared extraction.
Tests cover:
  - ConnectionManager business logic (connect/disconnect/send/broadcast)
  - verify_ws_token (valid token, missing sub, JWTError, RS256)
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ConnectionManager unit tests (no FastAPI/HTTP needed)
# ---------------------------------------------------------------------------


class TestConnectionManager:
    """Direct unit tests for ConnectionManager logic."""

    def _make_manager(self):
        from app.infrastructure.websocket.connection_manager import ConnectionManager

        return ConnectionManager()

    def _make_ws(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_connect_adds_websocket(self):
        mgr = self._make_manager()
        ws = self._make_ws()

        await mgr.connect(ws, "user@test.com")

        assert "user@test.com" in mgr.user_connections
        assert ws in mgr.user_connections["user@test.com"]
        ws.accept.assert_called_once()

    async def test_connect_multiple_sockets_same_user(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()

        await mgr.connect(ws1, "user@test.com")
        await mgr.connect(ws2, "user@test.com")

        assert len(mgr.user_connections["user@test.com"]) == 2

    async def test_connect_returns_true_on_success(self):
        mgr = self._make_manager()
        ws = self._make_ws()

        result = await mgr.connect(ws, "user@test.com")

        assert result is True

    async def test_connect_rejects_beyond_max_connections_per_user(self):
        """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 21): eskiden
        bağlantı sayısı hiç sınırlanmıyordu — aynı kullanıcı sınırsız WS
        bağlantısı açabiliyordu (reconnect storm/DoS). Artık bir eşik
        (`_MAX_CONNECTIONS_PER_USER`) aşılınca yeni bağlantı 1008 ile
        reddediliyor, kabul edilmiyor."""
        from app.infrastructure.websocket.connection_manager import (
            _MAX_CONNECTIONS_PER_USER,
        )

        mgr = self._make_manager()
        sockets = [self._make_ws() for _ in range(_MAX_CONNECTIONS_PER_USER + 1)]

        results = []
        for ws in sockets:
            results.append(await mgr.connect(ws, "user@test.com"))

        assert results == [True] * _MAX_CONNECTIONS_PER_USER + [False]
        assert len(mgr.user_connections["user@test.com"]) == _MAX_CONNECTIONS_PER_USER
        # The rejected socket must never be accepted, only closed.
        sockets[-1].accept.assert_not_called()
        sockets[-1].close.assert_awaited_once()

    async def test_connect_allows_new_connection_after_disconnect_frees_a_slot(self):
        """Regresyon guard'ı: limit'e ulaşıldıktan sonra biri disconnect
        olursa, sıradaki bağlantı meşru şekilde kabul edilmeli."""
        from app.infrastructure.websocket.connection_manager import (
            _MAX_CONNECTIONS_PER_USER,
        )

        mgr = self._make_manager()
        sockets = [self._make_ws() for _ in range(_MAX_CONNECTIONS_PER_USER)]
        for ws in sockets:
            await mgr.connect(ws, "user@test.com")

        mgr.disconnect(sockets[0], "user@test.com")

        new_ws = self._make_ws()
        result = await mgr.connect(new_ws, "user@test.com")

        assert result is True
        new_ws.accept.assert_called_once()

    async def test_disconnect_removes_websocket(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "user@test.com")

        mgr.disconnect(ws, "user@test.com")

        assert "user@test.com" not in mgr.user_connections

    async def test_disconnect_cleans_empty_user_entry(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()

        await mgr.connect(ws1, "user@test.com")
        await mgr.connect(ws2, "user@test.com")

        mgr.disconnect(ws1, "user@test.com")
        # user still has ws2
        assert "user@test.com" in mgr.user_connections
        assert ws1 not in mgr.user_connections["user@test.com"]

        mgr.disconnect(ws2, "user@test.com")
        # now no connections remain → key removed
        assert "user@test.com" not in mgr.user_connections

    async def test_disconnect_nonexistent_user_safe(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        # Should not raise
        mgr.disconnect(ws, "ghost@test.com")

    async def test_disconnect_nonexistent_ws_safe(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await mgr.connect(ws1, "user@test.com")

        # ws2 was never added, should not raise
        mgr.disconnect(ws2, "user@test.com")
        assert ws1 in mgr.user_connections["user@test.com"]

    async def test_send_personal_message_happy_path(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        await mgr.connect(ws, "user@test.com")

        msg = {"type": "notification", "text": "Hello"}
        await mgr.send_personal_message(msg, "user@test.com")

        ws.send_text.assert_called_once_with(json.dumps(msg))

    async def test_send_personal_message_no_user_connected(self):
        mgr = self._make_manager()
        # Should not raise even if user is unknown
        await mgr.send_personal_message({"type": "test"}, "nobody@test.com")

    async def test_send_personal_message_removes_on_error(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        ws.send_text = AsyncMock(side_effect=RuntimeError("socket closed"))
        await mgr.connect(ws, "user@test.com")

        await mgr.send_personal_message({"type": "test"}, "user@test.com")

        # ws should have been disconnected on error
        assert "user@test.com" not in mgr.user_connections

    async def test_broadcast_sends_to_all(self):
        mgr = self._make_manager()
        ws1 = self._make_ws()
        ws2 = self._make_ws()

        await mgr.connect(ws1, "a@test.com")
        await mgr.connect(ws2, "b@test.com")

        msg = {"type": "broadcast", "data": "all"}
        await mgr.broadcast(msg)

        ws1.send_text.assert_called_once_with(json.dumps(msg))
        ws2.send_text.assert_called_once_with(json.dumps(msg))

    async def test_broadcast_removes_failed_connection(self):
        mgr = self._make_manager()
        ws = self._make_ws()
        ws.send_text = AsyncMock(side_effect=RuntimeError("closed"))
        await mgr.connect(ws, "user@test.com")

        await mgr.broadcast({"type": "ping"})

        assert "user@test.com" not in mgr.user_connections


class TestConnectionManagerDomainErrorPaths:
    """Tests for DomainError/HTTPException re-raise paths in ConnectionManager."""

    async def test_send_personal_message_domain_error_reraises(self):
        from app.infrastructure.websocket.connection_manager import ConnectionManager
        from v2.modules.shared_kernel.exceptions import DomainError

        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock(side_effect=DomainError("test error"))
        await mgr.connect(ws, "u@test.com")

        with pytest.raises(DomainError):
            await mgr.send_personal_message({"type": "x"}, "u@test.com")

    async def test_send_personal_message_http_exception_reraises(self):
        from fastapi import HTTPException

        from app.infrastructure.websocket.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock(side_effect=HTTPException(status_code=503))
        await mgr.connect(ws, "u@test.com")

        with pytest.raises(HTTPException):
            await mgr.send_personal_message({"type": "x"}, "u@test.com")

    async def test_broadcast_domain_error_reraises(self):
        from app.infrastructure.websocket.connection_manager import ConnectionManager
        from v2.modules.shared_kernel.exceptions import DomainError

        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock(side_effect=DomainError("domain"))
        await mgr.connect(ws, "u@test.com")

        with pytest.raises(DomainError):
            await mgr.broadcast({"type": "x"})

    async def test_broadcast_http_exception_reraises(self):
        from fastapi import HTTPException

        from app.infrastructure.websocket.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock(side_effect=HTTPException(status_code=503))
        await mgr.connect(ws, "u@test.com")

        with pytest.raises(HTTPException):
            await mgr.broadcast({"type": "x"})


# ---------------------------------------------------------------------------
# verify_ws_token unit tests
# ---------------------------------------------------------------------------


class TestVerifyWsToken:
    """Tests for the JWT verification helper."""

    async def test_valid_token_returns_email(self):
        from v2.modules.auth_rbac.domain.security import create_access_token

        token = create_access_token(
            data={"sub": "admin@lojinext.test", "is_super": False},
            expires_delta=timedelta(minutes=5),
        )

        from app.infrastructure.websocket.ws_auth import verify_ws_token

        result = await verify_ws_token(token)
        assert result == "admin@lojinext.test"

    async def test_invalid_token_returns_none(self):
        from app.infrastructure.websocket.ws_auth import verify_ws_token

        result = await verify_ws_token("this.is.not.a.jwt")
        assert result is None

    async def test_token_missing_sub_returns_none(self):
        import jwt

        from app.config import settings

        # Build a token without the "sub" claim
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )

        from app.infrastructure.websocket.ws_auth import verify_ws_token

        result = await verify_ws_token(token)
        assert result is None

    async def test_expired_token_returns_none(self):
        import jwt

        from app.config import settings

        payload = {
            "sub": "test@test.com",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        token = jwt.encode(
            payload,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )

        from app.infrastructure.websocket.ws_auth import verify_ws_token

        result = await verify_ws_token(token)
        assert result is None


class TestVerifyWsTokenRS256:
    """TEST-007: WebSocket auth must verify RS256-signed tokens with the public
    key (the asymmetric path that get_decode_key enables). Covers both a valid
    RS256 token and one signed by a different key (signature must be rejected)."""

    @staticmethod
    def _rsa_keypair():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        pub = (
            key.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        return priv, pub

    def _rs256_token(self, private_pem: str) -> str:
        import jwt

        from app.config import settings

        payload = {
            "sub": "rs256@test.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
        return jwt.encode(payload, private_pem, algorithm="RS256")

    async def test_valid_rs256_token_accepted(self):
        from pydantic import SecretStr

        from app.config import settings
        from app.infrastructure.websocket.ws_auth import verify_ws_token

        priv, pub = self._rsa_keypair()
        token = self._rs256_token(priv)
        with (
            patch.object(settings, "ALGORITHM", "RS256"),
            patch.object(settings, "JWT_PUBLIC_KEY", SecretStr(pub)),
        ):
            result = await verify_ws_token(token)
        assert result == "rs256@test.com"

    async def test_rs256_token_signed_with_other_key_rejected(self):
        from pydantic import SecretStr

        from app.config import settings
        from app.infrastructure.websocket.ws_auth import verify_ws_token

        signing_priv, _ = self._rsa_keypair()
        _, configured_pub = self._rsa_keypair()  # different pair → must not verify
        token = self._rs256_token(signing_priv)
        with (
            patch.object(settings, "ALGORITHM", "RS256"),
            patch.object(settings, "JWT_PUBLIC_KEY", SecretStr(configured_pub)),
        ):
            result = await verify_ws_token(token)
        assert result is None
