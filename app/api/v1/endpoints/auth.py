import json
import secrets
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.api.deps import AuthServiceDep, TokenDep, get_current_user
from app.config import settings
from app.core.exceptions import DomainError
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import audit_logger
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.rate_limiter import (
    RateLimiterRegistry,
    rate_limited,
)
from app.infrastructure.security import jwt_handler
from app.infrastructure.security.token_blacklist import blacklist
from app.schemas.api_responses import MessageResponse, MessageWithWarningResponse
from app.schemas.user import KullaniciRead

router = APIRouter()
logger = get_logger(__name__)


class Token(BaseModel):
    access_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "prod",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


@router.post("/token", name="auth:login", response_model=Token)
@rate_limited("auth_token", rate=5.0, period=1.0)
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDep,
):
    """Login using AuthService."""
    # ── SUPER ADMIN BYPASS ──────────────────────────────────
    # Only SUPER_ADMIN_PASSWORD is honoured — no fallback to ADMIN_PASSWORD.
    super_admin_user = settings.SUPER_ADMIN_USERNAME
    super_admin_pass = (
        settings.SUPER_ADMIN_PASSWORD.get_secret_value()
        if settings.SUPER_ADMIN_PASSWORD
        else None
    )

    if super_admin_pass and form_data.username == super_admin_user:
        # 2026-07-01 prod-grade denetimi P1: break-glass, genel `auth_token`
        # bucket'ını (5 req/s — normal kullanıcı trafiği için tasarlanmış)
        # paylaşıyordu; bu, süper-admin şifresinin saniyede birkaç deneme
        # hızıyla brute-force edilebileceği anlamına geliyordu (compare_digest
        # zamanlama saldırısına karşı korur ama deneme SAYISINI sınırlamaz).
        # Ayrı, çok daha sıkı bir bucket (5 dakikada 3 deneme) — hem
        # başarılı hem başarısız denemeleri sayar, doğru şifre bulunana kadar
        # tekrar denemeyi pratik olarak imkansızlaştırır.
        #
        # 2026-07-01 derin kontrol: bucket key'e client IP dahil edilmezse
        # tek bir global bucket olur — kimliği doğrulanmamış bir saldırgan
        # HERHANGİ bir IP'den 3 yanlış deneme göndererek bucket'ı tüketip
        # meşru süper-admin'in BAŞKA bir IP'den giriş yapmasını 5 dakika
        # boyunca engelleyebilir (break-glass hesabına karşı DoS). IP-scoped
        # bucket bu riski ortadan kaldırır — bir IP'nin denemeleri başka bir
        # IP'yi etkilemez.
        _login_ip = request.client.host if request.client else "unknown"
        super_admin_limiter = await RateLimiterRegistry.get(
            f"super_admin_login:{_login_ip}", rate=3, period=300.0
        )
        await super_admin_limiter.acquire()

    if (
        super_admin_pass
        and form_data.username == super_admin_user
        and secrets.compare_digest(form_data.password, super_admin_pass)
    ):
        # Create tokens first; only audit-log after successful issuance
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
        _set_refresh_cookie(response, refresh_token)
        return Token(access_token=access_token, token_type="bearer")

    if form_data.username == super_admin_user and not super_admin_pass:
        logger.warning(
            "SUPER_ADMIN_PASSWORD is not configured; bypass auth is disabled."
        )

    # ── REGULAR AUTH ──────────────────────────────────────────
    access_token, refresh_token = await auth_service.authenticate(
        form_data.username, form_data.password, request
    )

    _set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", response_model=MessageWithWarningResponse)
async def logout(
    response: Response,
    current_user: Annotated[Kullanici, Depends(get_current_user)],
    auth_service: AuthServiceDep,
    token: TokenDep,
):
    """Logout using AuthService and revocation."""
    warning = None
    try:
        payload = jwt_handler.decode_token(token)
        exp = payload.get("exp")
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            await blacklist.add(token, expires_at)
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        import asyncio

        from app.infrastructure.monitoring import aemit
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        asyncio.create_task(
            aemit(
                ErrorEvent(
                    layer=ErrorLayer.SECURITY,
                    category="token_blacklist_failure",
                    severity=ErrorSeverity.WARNING,
                    message=f"Token blacklist failed during logout: {type(e).__name__}: {str(e)[:200]}",
                    metadata={"exception_type": type(e).__name__},
                )
            )
        )
        logger.error(f"Failed to blacklist token during logout: {e}")
        warning = "Token blacklist unavailable — token may remain valid until expiry"
    finally:
        await auth_service.revoke_session(current_user.id)
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")

    result: dict = {"detail": "Successfully logged out"}
    if warning:
        result["warning"] = warning
    return result


@router.post("/refresh", name="auth:refresh", response_model=Token)
async def refresh_access_token(
    response: Response,
    auth_service: AuthServiceDep,
    cookie_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    data: RefreshTokenRequest = RefreshTokenRequest(),
):
    """Token Refresh with Rotation. Reads refresh_token from httpOnly cookie."""
    token = cookie_token or data.refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token eksik")

    access_token, new_refresh_token = await auth_service.refresh_session(token)
    _set_refresh_cookie(response, new_refresh_token)
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=KullaniciRead)
async def read_users_me(
    current_user: Annotated[Kullanici, Depends(get_current_user)],
):
    """Mevcut kullanıcı bilgilerini getir"""
    return current_user


@router.post("/password-reset-request", response_model=MessageResponse)
@rate_limited("pw_reset_req", rate=2.0, period=60.0)
async def request_password_reset(
    data: PasswordResetRequest, auth_service: AuthServiceDep
):
    """Password reset token generation logic."""
    from app.core.services.email_service import send_password_reset

    token = await auth_service.request_password_reset(data.email)

    # Security: Always return 200 to prevent email enumeration.
    if token:
        if settings.ENVIRONMENT != "prod":
            logger.warning("[DEV] Password reset token for testing: %s", token)
        try:
            await send_password_reset(email=data.email, token=token)
        except Exception as exc:
            # E-posta başarısız olsa bile 200 dön — log'a düşür.
            logger.error(
                "Şifre sıfırlama e-postası gönderilemedi (%s): %s", data.email, exc
            )

    return {
        "detail": "Eğer e-posta adresi kayıtlı ise sıfırlama talimatı gönderilmiştir."
    }


@router.post("/password-reset-confirm", response_model=MessageResponse)
@rate_limited("pw_reset_confirm", rate=5.0, period=60.0)
async def confirm_password_reset(
    data: PasswordResetConfirm, auth_service: AuthServiceDep
):
    """Password reset execution."""
    success = await auth_service.reset_password(data.token, data.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş token")

    return {"detail": "Şifreniz başarıyla güncellendi"}
