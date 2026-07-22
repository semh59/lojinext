"""Login/refresh/session/password-reset use-cases.

Eski ``AuthService`` sınıfı (B.1, location/notification/fleet/fuel/driver'daki
kararla aynı gerekçe) kaldırıldı — her use-case bağımsız bir fonksiyon,
opsiyonel ``uow: UnitOfWork | None = None`` alır. ``uow`` verilmezse fonksiyon
kendi ``UnitOfWork()``'ünü açar (dalga 5'in score-breakdown 500 gotcha'sını
TEKRARLAMAMAK için — bkz. driver/CLAUDE.md — burada singleton repo hiç
olmadığı için o risk zaten yok, ama tutarlılık için aynı imza deseni
korunuyor). ``app/api/deps.py::get_auth_service`` HER ZAMAN FastAPI'nin
``get_uow()`` bağımlılığından gelen zaten-açık bir ``uow`` geçirir — burada
İKİNCİ kez ``async with uow:`` yapmak dış çıkışta ``session.close()``'un hiç
çağrılmamasına yol açar (connection-pool leak, bkz.
TASKS/bug-connection-pool-leak-under-load.md) — bu yüzden verilen ``uow``
DOĞRUDAN kullanılır, tekrar ``async with`` edilmez.
"""

import asyncio
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status

from app.config import settings
from v2.modules.auth_rbac.domain import jwt_handler
from v2.modules.auth_rbac.infrastructure.models import KullaniciOturumu
from v2.modules.platform_infra.audit.audit_logger import audit_logger
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.rate_limiter import RateLimiterRegistry
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def authenticate_super_admin(
    username: str, password: str, request: Request
) -> Optional[Tuple[str, str]]:
    """Break-glass super-admin authentication (`SUPER_ADMIN_PASSWORD` env).

    Returns (access_token, refresh_token) on success, None if the super-admin
    path doesn't apply (wrong username, unconfigured, or wrong password) — the
    caller falls through to regular `authenticate()`.

    2026-07-01 prod-grade denetimi P1: genel `auth_token` bucket'ından ayrı,
    IP-scoped, çok daha sıkı bir rate-limit bucket (`super_admin_login:{ip}`)
    kullanır — hem başarılı hem başarısız denemeleri sayar.
    """
    super_admin_user = settings.SUPER_ADMIN_USERNAME
    if username != super_admin_user:
        return None

    super_admin_pass = (
        settings.SUPER_ADMIN_PASSWORD.get_secret_value()
        if settings.SUPER_ADMIN_PASSWORD
        else None
    )
    if not super_admin_pass:
        logger.warning(
            "SUPER_ADMIN_PASSWORD is not configured; bypass auth is disabled."
        )
        return None

    _login_ip = request.client.host if request.client else "unknown"
    super_admin_limiter = await RateLimiterRegistry.get(
        f"super_admin_login:{_login_ip}",
        rate=settings.SUPER_ADMIN_LOGIN_RATE,
        period=settings.SUPER_ADMIN_LOGIN_PERIOD,
    )
    await super_admin_limiter.acquire()

    if not secrets.compare_digest(password, super_admin_pass):
        return None

    access_token = jwt_handler.create_access_token(
        data={"sub": super_admin_user, "role": "super_admin", "is_super": True}
    )
    refresh_token = jwt_handler.create_refresh_token(
        data={"sub": super_admin_user, "is_super": True}
    )
    _client_ip = request.client.host if request.client else "unknown"
    audit_logger.warning(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "super_admin_login",
                "actor": super_admin_user,
                "role": "super_admin",
                "ip": _client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "path": str(request.url.path),
                "status": "success",
            }
        )
    )
    return access_token, refresh_token


async def authenticate(
    email: str, password: str, request: Request, uow: Optional[UnitOfWork] = None
) -> Tuple[str, str]:
    """Authenticate user and create session."""
    if uow is not None:
        return await _authenticate(uow, email, password, request)
    async with UnitOfWork() as owned_uow:
        result = await _authenticate(owned_uow, email, password, request)
        await owned_uow.commit()
        return result


async def _authenticate(
    uow: UnitOfWork, email: str, password: str, request: Request
) -> Tuple[str, str]:
    user = await uow.kullanici_repo.get_by_email(email)

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
            await uow.commit()
        # 2026-07-01 prod-grade denetimi P1: başarısız giriş denemeleri
        # önceden yalnız dosya loguna düşüyordu, admin_audit_log'a hiç
        # yazılmıyordu — saldırı tespiti/trace UI'da görünmüyordu.
        try:
            from v2.modules.platform_infra.audit.audit_logger import log_audit_event

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
        refresh_bitis=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
    )
    uow.session.add(db_session)

    user.son_giris = datetime.now(timezone.utc)
    user.son_giris_ip = client_ip

    await uow.commit()

    logger.info(f"Successful login: {user_email}")
    return access_token, refresh_token


async def refresh_session(
    refresh_token: str, uow: Optional[UnitOfWork] = None
) -> Tuple[str, str]:
    """Refresh access token and rotate refresh token."""
    if uow is not None:
        return await _refresh_session(uow, refresh_token)
    async with UnitOfWork() as owned_uow:
        return await _refresh_session(owned_uow, refresh_token)


async def _refresh_session(uow: UnitOfWork, refresh_token: str) -> Tuple[str, str]:
    try:
        payload = jwt_handler.decode_refresh_token(refresh_token)
        email = payload.get("sub")
    except Exception as e:
        from v2.modules.platform_infra.monitoring import emit
        from v2.modules.platform_infra.monitoring.models import (
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

    user = await uow.kullanici_repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    sessions = await uow.session_repo.get_active_sessions(user.id)
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
        from v2.modules.platform_infra.monitoring import emit
        from v2.modules.platform_infra.monitoring.models import (
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

    await uow.commit()

    return new_access_token, new_refresh_token


async def revoke_session(user_id: int, uow: Optional[UnitOfWork] = None) -> None:
    """Immediately deactivate all active sessions for a user."""
    if uow is not None:
        await uow.session_repo.deactivate_all(user_id)
        await uow.commit()
    else:
        async with UnitOfWork() as owned_uow:
            await owned_uow.session_repo.deactivate_all(user_id)
            await owned_uow.commit()
    logger.info(f"Revoked all sessions for user id: {user_id}")


async def request_password_reset(
    email: str, uow: Optional[UnitOfWork] = None
) -> Optional[str]:
    """Generate reset token and store in DB."""
    if uow is not None:
        return await _request_password_reset(uow, email)
    async with UnitOfWork() as owned_uow:
        return await _request_password_reset(owned_uow, email)


async def _request_password_reset(uow: UnitOfWork, email: str) -> Optional[str]:
    import secrets

    user = await uow.kullanici_repo.get_by_email(email)
    if not user:
        return None

    token = secrets.token_urlsafe(32)
    # Store SHA-256 hash, never plaintext (AUDIT-022)
    user.sifre_sifir_token = jwt_handler.hash_token(token)
    user.sifre_sifir_son = datetime.now(timezone.utc) + timedelta(hours=1)

    await uow.commit()

    logger.info(f"Password reset requested for: {email}")
    return token  # plaintext returned to caller for email delivery


async def reset_password(
    token: str, new_password: str, uow: Optional[UnitOfWork] = None
) -> bool:
    """Verify token and update password."""
    if uow is not None:
        return await _reset_password(uow, token, new_password)
    async with UnitOfWork() as owned_uow:
        return await _reset_password(owned_uow, token, new_password)


async def _reset_password(uow: UnitOfWork, token: str, new_password: str) -> bool:
    user = await uow.kullanici_repo.get_by_reset_token(token)
    if not user:
        return False
    if user.sifre_sifir_son and datetime.now(timezone.utc) > user.sifre_sifir_son:
        logger.warning(f"Expired reset token used for user id: {user.id}")
        return False

    user.sifre_hash = jwt_handler.get_password_hash(new_password)
    user.sifre_sifir_token = None
    user.sifre_sifir_son = None
    user.sifre_degisim_tarihi = datetime.now(timezone.utc)

    await uow.session_repo.deactivate_all(user.id)
    await uow.commit()

    logger.info(f"Password successfully reset for user id: {user.id}")
    return True
