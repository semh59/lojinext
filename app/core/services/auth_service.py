import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status

from app.database.models import KullaniciOturumu
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security import jwt_handler

logger = get_logger(__name__)


class AuthService:
    """Authentication and session management service.

    TYPE: PER-REQUEST
    SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
    DEPENDS_ON: UoW.session
    CREATED_BY: app/api/deps.py::deps.get_auth_service()
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def authenticate(
        self, email: str, password: str, request: Request
    ) -> Tuple[str, str]:
        """Authenticate user and create session.

        NOT: ``self.uow`` FastAPI'nin ``get_uow()`` bağımlılığı tarafından
        ZATEN ``async with`` içinde açılmış olarak enjekte edilir (bkz.
        ``app/api/deps.py::get_auth_service``) — burada ikinci kez
        ``async with self.uow:`` yapmak AYNI instance'ı yeniden `__aenter__`
        ile açar ve `_owns` bayrağını `False`'a bozar, dış (get_uow'un
        sahip olduğu) çıkışta `session.close()` hiç çağrılmaz — connection
        pool leak'ine yol açar (bkz. TASKS/bug-connection-pool-leak-under-load.md).
        ``self.uow`` doğrudan kullanılmalı, tekrar `async with` edilmemeli.
        """
        user = await self.uow.kullanici_repo.get_by_email(email)

        if user and user.kilitli_kadar:
            now = datetime.now(timezone.utc)
            if now < user.kilitli_kadar:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Cok fazla basarisiz deneme. Hesabiniz gecici olarak "
                        "kilitlenmistir. Lutfen 30 dakika sonra tekrar deneyin."
                    ),
                )
            user.basarisiz_giris_sayisi = 0
            user.kilitli_kadar = None

        dummy_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6L6s57Wy60Q2i9ki"
        hash_to_check = user.sifre_hash if user else dummy_hash

        # bcrypt.checkpw() is CPU-bound and synchronous — running it inline
        # blocks the single-threaded event loop for ~100-300ms per call.
        # Under concurrent logins (all sharing one asyncio event loop) this
        # serializes EVERY in-flight request (including unrelated ones —
        # confirmed live: a GET /health/ request stalled 62s behind a
        # pileup of blocked bcrypt calls), which cascades into DB pool
        # pre-ping timeouts and connection churn that reads as more
        # connection-pool-leak symptoms (bkz.
        # TASKS/bug-connection-pool-leak-under-load.md). Offloading to a
        # worker thread keeps the event loop free to serve other requests
        # while bcrypt runs (the `not user or` short-circuit above is
        # pre-existing, unrelated to this fix, not touched here).
        if not user or not await asyncio.to_thread(
            jwt_handler.verify_password, password, hash_to_check
        ):
            logger.warning(f"Failed login attempt: {email}")
            if user:
                now = datetime.now(timezone.utc)
                user.basarisiz_giris_sayisi += 1
                if user.basarisiz_giris_sayisi >= 5:
                    user.kilitli_kadar = now + timedelta(minutes=30)
                await self.uow.commit()
            # 2026-07-01 prod-grade denetimi P1: başarısız giriş denemeleri
            # önceden yalnız dosya loguna düşüyordu, admin_audit_log'a hiç
            # yazılmıyordu — saldırı tespiti/trace UI'da görünmüyordu.
            try:
                from app.infrastructure.audit.audit_logger import (
                    log_audit_event,
                )

                await log_audit_event(
                    action="auth.failed_login",
                    module="auth",
                    entity_id=email,
                    user_id=user.id if user else None,
                    basarili=False,
                )
            except Exception as audit_exc:  # pragma: no cover
                logger.warning("Failed-login audit log failed: %s", audit_exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hatali e-posta veya sifre",
            )

        if user.basarisiz_giris_sayisi > 0:
            user.basarisiz_giris_sayisi = 0
            user.kilitli_kadar = None

        if not user.aktif:
            raise HTTPException(status_code=403, detail="Kullanici hesabi pasif")

        # Extract primitives inside session context — rol is a lazy relationship
        user_email = user.email
        user_id = user.id
        role_name = user.rol.ad if user.rol else "user"

        access_token = jwt_handler.create_access_token(
            data={"sub": user_email, "role": role_name}
        )
        refresh_token = jwt_handler.create_refresh_token(
            data={"sub": user_email, "uid": user_id}
        )

        access_payload = jwt_handler.decode_token(access_token)
        refresh_payload = jwt_handler.decode_refresh_token(refresh_token)

        client_ip = request.client.host if request.client else "0.0.0.0"
        db_session = KullaniciOturumu(
            kullanici_id=user_id,
            access_token_hash=jwt_handler.hash_token(access_token),
            refresh_token_hash=jwt_handler.hash_token(refresh_token),
            ip_adresi=client_ip,
            tarayici=request.headers.get("user-agent"),
            access_bitis=datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc),
            refresh_bitis=datetime.fromtimestamp(
                refresh_payload["exp"], tz=timezone.utc
            ),
        )
        self.uow.session.add(db_session)

        user.son_giris = datetime.now(timezone.utc)
        user.son_giris_ip = client_ip

        await self.uow.commit()

        logger.info(f"Successful login: {user_email}")
        return access_token, refresh_token

    async def refresh_session(self, refresh_token: str) -> Tuple[str, str]:
        """Refresh access token and rotate refresh token."""
        try:
            payload = jwt_handler.decode_refresh_token(refresh_token)
            email = payload.get("sub")
        except Exception as e:
            from app.infrastructure.monitoring import emit
            from app.infrastructure.monitoring.models import (
                ErrorEvent,
                ErrorLayer,
                ErrorSeverity,
            )

            emit(
                ErrorEvent(
                    layer=ErrorLayer.SECURITY,
                    category="jwt_refresh_failure",
                    severity=ErrorSeverity.ERROR,
                    message=f"Refresh token decode failed: {type(e).__name__}: {str(e)[:200]}",
                    metadata={"exception_type": type(e).__name__},
                )
            )
            logger.error(f"Refresh token error: {e}")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await self.uow.kullanici_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        sessions = await self.uow.session_repo.get_active_sessions(user.id)
        target_session = None
        for session in sessions:
            if jwt_handler.verify_token_hash(refresh_token, session.refresh_token_hash):
                target_session = session
                break

        if target_session is None:
            # The refresh token decoded cleanly (valid signature, unexpired,
            # correct aud/typ) yet matches no active session — it was
            # superseded by a rotation, or its session was revoked / logged
            # out, and is now being replayed. Surface it as a refresh-token
            # reuse signal so theft patterns are detectable. (Full reuse
            # detection that revokes the live session family needs token
            # lineage tracking — ARCH-018 follow-up.)
            from app.infrastructure.monitoring import emit
            from app.infrastructure.monitoring.models import (
                ErrorEvent,
                ErrorLayer,
                ErrorSeverity,
            )

            emit(
                ErrorEvent(
                    layer=ErrorLayer.SECURITY,
                    category="refresh_token_reuse",
                    severity=ErrorSeverity.WARNING,
                    message=(
                        "Superseded/replayed refresh token presented "
                        "(valid signature, no active session match)."
                    ),
                    metadata={"user_id": user.id},
                )
            )
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        if target_session.refresh_bitis < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        # Rotate tokens (One-time use refresh tokens)
        new_access_token = jwt_handler.create_access_token(
            data={"sub": user.email, "role": user.rol.ad if user.rol else "user"}
        )
        new_refresh_token = jwt_handler.create_refresh_token(
            data={"sub": user.email, "uid": user.id}
        )

        # Update session with new hashes and expiration
        target_session.access_token_hash = jwt_handler.hash_token(new_access_token)
        target_session.refresh_token_hash = jwt_handler.hash_token(new_refresh_token)

        access_payload = jwt_handler.decode_token(new_access_token)
        refresh_payload = jwt_handler.decode_refresh_token(new_refresh_token)

        target_session.access_bitis = datetime.fromtimestamp(
            access_payload["exp"], tz=timezone.utc
        )
        target_session.refresh_bitis = datetime.fromtimestamp(
            refresh_payload["exp"], tz=timezone.utc
        )
        target_session.son_aktivite = datetime.now(timezone.utc)

        await self.uow.commit()

        return new_access_token, new_refresh_token

    async def revoke_session(self, user_id: int):
        """Immediately deactivate all active sessions for a user."""
        await self.uow.session_repo.deactivate_all(user_id)
        await self.uow.commit()
        logger.info(f"Revoked all sessions for user id: {user_id}")

    async def request_password_reset(self, email: str) -> Optional[str]:
        """Generate reset token and store in DB."""
        import secrets

        user = await self.uow.kullanici_repo.get_by_email(email)
        if not user:
            return None

        token = secrets.token_urlsafe(32)
        # Store SHA-256 hash, never plaintext (AUDIT-022)
        user.sifre_sifir_token = jwt_handler.hash_token(token)
        user.sifre_sifir_son = datetime.now(timezone.utc) + timedelta(hours=1)

        await self.uow.commit()

        logger.info(f"Password reset requested for: {email}")
        return token  # plaintext returned to caller for email delivery

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Verify token and update password."""
        user = await self.uow.kullanici_repo.get_by_reset_token(token)
        if not user:
            return False
        if user.sifre_sifir_son and datetime.now(timezone.utc) > user.sifre_sifir_son:
            logger.warning(f"Expired reset token used for user id: {user.id}")
            return False

        user.sifre_hash = jwt_handler.get_password_hash(new_password)
        user.sifre_sifir_token = None
        user.sifre_sifir_son = None
        user.sifre_degisim_tarihi = datetime.now(timezone.utc)

        await self.uow.session_repo.deactivate_all(user.id)
        await self.uow.commit()

        logger.info(f"Password successfully reset for user id: {user.id}")
        return True
