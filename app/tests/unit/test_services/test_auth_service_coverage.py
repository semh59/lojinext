"""AuthService comprehensive unit tests — targets missing lines.

Covers:
- authenticate: happy path, wrong password, locked account, inactive user,
  failed-login counter, lockout after 5 failures
- refresh_session: happy path, bad token, user not found, no matching session,
  expired session
- revoke_session
- request_password_reset: found and not-found
- reset_password: happy path, not found, expired token
"""

import datetime
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(ip="127.0.0.1", user_agent="pytest-client"):
    req = MagicMock()
    req.client.host = ip
    req.headers.get = MagicMock(return_value=user_agent)
    return req


def _make_uow():
    """Return an AsyncMock UoW that can be used as async context manager."""
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.commit = AsyncMock()
    uow.session = MagicMock()
    uow.session.add = MagicMock()
    return uow


def _make_user(
    *,
    email="test@example.com",
    user_id=1,
    aktif=True,
    kilitli_kadar=None,
    basarisiz_giris_sayisi=0,
    sifre_hash=None,
    rol_ad="user",
):
    """Return a minimal mock user object."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.aktif = aktif
    user.kilitli_kadar = kilitli_kadar
    user.basarisiz_giris_sayisi = basarisiz_giris_sayisi
    # Default to a bcrypt hash that matches password "correct_password"
    user.sifre_hash = sifre_hash or "$2b$12$fake_hash_placeholder"
    rol = MagicMock()
    rol.ad = rol_ad
    user.rol = rol
    user.son_giris = None
    user.son_giris_ip = None
    user.sifre_sifir_token = None
    user.sifre_sifir_son = None
    user.sifre_hash = sifre_hash or "$2b$12$fake_hash_placeholder"
    return user


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------


class TestAuthServiceAuthenticate:
    async def test_happy_path_returns_tokens(self):
        """Successful login returns (access_token, refresh_token)."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        dummy_access = "access.token.here"
        dummy_refresh = "refresh.token.here"
        dummy_access_payload = {"exp": 9999999999}
        dummy_refresh_payload = {"exp": 9999999999}

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.verify_password",
                return_value=True,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_access_token",
                return_value=dummy_access,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_refresh_token",
                return_value=dummy_refresh,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_token",
                return_value=dummy_access_payload,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value=dummy_refresh_payload,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.hash_token",
                return_value="hashed",
            ),
        ):
            service = AuthService(uow=uow)
            result = await service.authenticate(
                "test@example.com", "correct_password", _make_request()
            )

        assert result == (dummy_access, dummy_refresh)
        uow.commit.assert_called()

    async def test_wrong_password_raises_401(self):
        """Wrong password raises 401 HTTPException."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        with patch(
            "app.core.services.auth_service.jwt_handler.verify_password",
            return_value=False,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.authenticate(
                    "test@example.com", "wrong_password", _make_request()
                )

        assert exc_info.value.status_code == 401
        assert "Hatali" in exc_info.value.detail

    async def test_wrong_password_increments_counter(self):
        """Failed login increments basarisiz_giris_sayisi and commits."""
        from app.core.services.auth_service import AuthService

        user = _make_user(basarisiz_giris_sayisi=0)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        with patch(
            "app.core.services.auth_service.jwt_handler.verify_password",
            return_value=False,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException):
                await service.authenticate("test@example.com", "bad", _make_request())

        assert user.basarisiz_giris_sayisi == 1
        uow.commit.assert_called_once()

    async def test_lockout_after_five_failures(self):
        """5th failed attempt sets kilitli_kadar."""
        from app.core.services.auth_service import AuthService

        user = _make_user(basarisiz_giris_sayisi=4)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        with patch(
            "app.core.services.auth_service.jwt_handler.verify_password",
            return_value=False,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.authenticate("test@example.com", "bad", _make_request())

        assert exc_info.value.status_code == 401
        assert user.kilitli_kadar is not None

    async def test_locked_account_raises_401(self):
        """Locked account raises 401 with lockout message."""
        from app.core.services.auth_service import AuthService

        future = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=29)
        user = _make_user(kilitli_kadar=future)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        service = AuthService(uow=uow)
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate("test@example.com", "any", _make_request())

        assert exc_info.value.status_code == 401
        assert "kilitlenmistir" in exc_info.value.detail

    async def test_expired_lock_resets_counter(self):
        """Past kilitli_kadar clears lockout and proceeds normally."""
        from app.core.services.auth_service import AuthService

        past = datetime.datetime.now(timezone.utc) - datetime.timedelta(minutes=1)
        user = _make_user(kilitli_kadar=past, basarisiz_giris_sayisi=5)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        dummy_access = "access.token"
        dummy_refresh = "refresh.token"

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.verify_password",
                return_value=True,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_access_token",
                return_value=dummy_access,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_refresh_token",
                return_value=dummy_refresh,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.hash_token",
                return_value="hashed",
            ),
        ):
            service = AuthService(uow=uow)
            result = await service.authenticate(
                "test@example.com", "pw", _make_request()
            )

        assert result[0] == dummy_access
        # Counter was reset when lock expired
        assert user.basarisiz_giris_sayisi == 0

    async def test_inactive_user_raises_403(self):
        """Inactive user (aktif=False) raises 403 after password check passes."""
        from app.core.services.auth_service import AuthService

        user = _make_user(aktif=False)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        with patch(
            "app.core.services.auth_service.jwt_handler.verify_password",
            return_value=True,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.authenticate("test@example.com", "pw", _make_request())

        assert exc_info.value.status_code == 403

    async def test_nonexistent_user_raises_401(self):
        """Unknown email raises 401 (constant-time, no info leak)."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=None)

        with patch(
            "app.core.services.auth_service.jwt_handler.verify_password",
            return_value=False,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.authenticate("unknown@example.com", "pw", _make_request())

        assert exc_info.value.status_code == 401

    async def test_no_client_ip_uses_fallback(self):
        """Request without client still succeeds; IP defaults to 0.0.0.0."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        req = MagicMock()
        req.client = None
        req.headers.get = MagicMock(return_value="agent")

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.verify_password",
                return_value=True,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_access_token",
                return_value="access",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_refresh_token",
                return_value="refresh",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.hash_token",
                return_value="h",
            ),
        ):
            service = AuthService(uow=uow)
            access, _ = await service.authenticate("test@example.com", "pw", req)

        assert access == "access"
        assert user.son_giris_ip == "0.0.0.0"

    async def test_previous_failures_reset_on_success(self):
        """basarisiz_giris_sayisi > 0 is cleared on successful login."""
        from app.core.services.auth_service import AuthService

        user = _make_user(basarisiz_giris_sayisi=3)
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.verify_password",
                return_value=True,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_access_token",
                return_value="access",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_refresh_token",
                return_value="refresh",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.hash_token",
                return_value="h",
            ),
        ):
            service = AuthService(uow=uow)
            await service.authenticate("test@example.com", "pw", _make_request())

        assert user.basarisiz_giris_sayisi == 0
        assert user.kilitli_kadar is None


# ---------------------------------------------------------------------------
# refresh_session
# ---------------------------------------------------------------------------


class TestAuthServiceRefreshSession:
    async def test_happy_path_returns_new_tokens(self):
        """Valid refresh token returns new (access, refresh) pair.

        decode_refresh_token is called twice in refresh_session:
          1. initial decode to extract 'sub' from the incoming token
          2. decode the newly created refresh token to get its 'exp'
        side_effect list covers both calls.
        """
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        future = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=7)
        session_obj = MagicMock()
        session_obj.refresh_token_hash = "stored_hash"
        session_obj.refresh_bitis = future

        uow.session_repo.get_active_sessions = AsyncMock(return_value=[session_obj])

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                side_effect=[
                    {"sub": "test@example.com"},  # first call: decode incoming token
                    {"exp": 9999999999},  # second call: decode new refresh token
                ],
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.verify_token_hash",
                return_value=True,
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_access_token",
                return_value="new_access",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.create_refresh_token",
                return_value="new_refresh",
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.decode_token",
                return_value={"exp": 9999999999},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.hash_token",
                return_value="new_hash",
            ),
        ):
            service = AuthService(uow=uow)
            access, refresh = await service.refresh_session("old_refresh_token")

        assert access == "new_access"
        assert refresh == "new_refresh"
        uow.commit.assert_called_once()

    async def test_invalid_refresh_token_raises_401(self):
        """Non-decodable refresh token raises 401."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()

        with patch(
            "app.core.services.auth_service.jwt_handler.decode_refresh_token",
            side_effect=Exception("bad token"),
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.refresh_session("garbage")

        assert exc_info.value.status_code == 401
        assert "Invalid refresh token" in exc_info.value.detail

    async def test_user_not_found_raises_401(self):
        """Refresh with unknown user raises 401."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=None)

        with patch(
            "app.core.services.auth_service.jwt_handler.decode_refresh_token",
            return_value={"sub": "ghost@example.com"},
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.refresh_session("token")

        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail

    async def test_no_matching_session_raises_401(self):
        """No session matching token hash raises 401."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)
        uow.session_repo.get_active_sessions = AsyncMock(return_value=[])

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"sub": "test@example.com"},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.verify_token_hash",
                return_value=False,
            ),
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.refresh_session("token")

        assert exc_info.value.status_code == 401

    async def test_no_matching_session_emits_reuse_signal(self):
        """A validly-decoded refresh token matching no active session emits a
        refresh_token_reuse security signal so theft is detectable."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)
        uow.session_repo.get_active_sessions = AsyncMock(return_value=[])

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"sub": "test@example.com"},
            ),
            patch("app.infrastructure.monitoring.emit") as mock_emit,
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException):
                await service.refresh_session("token")

        assert mock_emit.called
        emitted = mock_emit.call_args.args[0]
        assert emitted.category == "refresh_token_reuse"

    async def test_expired_session_raises_401(self):
        """Session past refresh_bitis raises 401."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        past = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)
        session_obj = MagicMock()
        session_obj.refresh_token_hash = "stored_hash"
        session_obj.refresh_bitis = past

        uow.session_repo.get_active_sessions = AsyncMock(return_value=[session_obj])

        with (
            patch(
                "app.core.services.auth_service.jwt_handler.decode_refresh_token",
                return_value={"sub": "test@example.com"},
            ),
            patch(
                "app.core.services.auth_service.jwt_handler.verify_token_hash",
                return_value=True,
            ),
        ):
            service = AuthService(uow=uow)
            with pytest.raises(HTTPException) as exc_info:
                await service.refresh_session("token")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# revoke_session
# ---------------------------------------------------------------------------


class TestAuthServiceRevokeSession:
    async def test_revoke_deactivates_all_sessions(self):
        """revoke_session calls deactivate_all and commits."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()
        uow.session_repo.deactivate_all = AsyncMock()

        service = AuthService(uow=uow)
        await service.revoke_session(user_id=42)

        uow.session_repo.deactivate_all.assert_called_once_with(42)
        uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# request_password_reset
# ---------------------------------------------------------------------------


class TestAuthServiceRequestPasswordReset:
    async def test_returns_token_for_known_email(self):
        """Known email gets a reset token stored and returned."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=user)

        service = AuthService(uow=uow)
        token = await service.request_password_reset("test@example.com")

        assert token is not None
        assert isinstance(token, str) and len(token) > 10
        # AUDIT-022: DB'de düz-metin token DEĞİL, SHA-256 hash'i saklanır; düz-metin
        # yalnız çağırana (e-posta için) döner.
        from app.core.services.auth_service import jwt_handler

        assert user.sifre_sifir_token != token
        assert user.sifre_sifir_token == jwt_handler.hash_token(token)
        uow.commit.assert_called_once()

    async def test_returns_none_for_unknown_email(self):
        """Unknown email returns None without raising."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()
        uow.kullanici_repo.get_by_email = AsyncMock(return_value=None)

        service = AuthService(uow=uow)
        result = await service.request_password_reset("nobody@example.com")

        assert result is None
        uow.commit.assert_not_called()


# ---------------------------------------------------------------------------
# reset_password
# ---------------------------------------------------------------------------


class TestAuthServiceResetPassword:
    async def test_valid_token_resets_password(self):
        """Valid token resets password and returns True."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        user.sifre_sifir_son = datetime.datetime.now(timezone.utc) + datetime.timedelta(
            hours=1
        )
        uow = _make_uow()
        uow.kullanici_repo.get_by_reset_token = AsyncMock(return_value=user)
        uow.session_repo.deactivate_all = AsyncMock()

        with patch(
            "app.core.services.auth_service.jwt_handler.get_password_hash",
            return_value="new_hash_value",
        ):
            service = AuthService(uow=uow)
            result = await service.reset_password("valid_token", "newpassword123")

        assert result is True
        assert user.sifre_hash == "new_hash_value"
        assert user.sifre_sifir_token is None
        uow.session_repo.deactivate_all.assert_called_once_with(user.id)
        uow.commit.assert_called_once()

    async def test_invalid_token_returns_false(self):
        """Unknown token returns False without raising."""
        from app.core.services.auth_service import AuthService

        uow = _make_uow()
        uow.kullanici_repo.get_by_reset_token = AsyncMock(return_value=None)

        service = AuthService(uow=uow)
        result = await service.reset_password("bad_token", "newpassword")

        assert result is False
        uow.commit.assert_not_called()

    async def test_expired_token_returns_false(self):
        """Expired reset token returns False."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        user.sifre_sifir_son = datetime.datetime.now(timezone.utc) - datetime.timedelta(
            hours=2
        )
        uow = _make_uow()
        uow.kullanici_repo.get_by_reset_token = AsyncMock(return_value=user)

        service = AuthService(uow=uow)
        result = await service.reset_password("expired_token", "newpassword")

        assert result is False
        uow.commit.assert_not_called()

    async def test_no_expiry_set_skips_check(self):
        """Token with sifre_sifir_son=None skips expiry check and resets password."""
        from app.core.services.auth_service import AuthService

        user = _make_user()
        user.sifre_sifir_son = None
        uow = _make_uow()
        uow.kullanici_repo.get_by_reset_token = AsyncMock(return_value=user)
        uow.session_repo.deactivate_all = AsyncMock()

        with patch(
            "app.core.services.auth_service.jwt_handler.get_password_hash",
            return_value="hashed_new",
        ):
            service = AuthService(uow=uow)
            result = await service.reset_password("token_no_expiry", "newpassword")

        assert result is True
