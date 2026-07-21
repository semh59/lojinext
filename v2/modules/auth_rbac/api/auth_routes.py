from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.api.deps import TokenDep, UOWDep, get_current_user
from app.config import settings
from app.core.exceptions import DomainError
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.rate_limiter import rate_limited
from v2.modules.auth_rbac.application import auth_service
from v2.modules.auth_rbac.domain import jwt_handler
from v2.modules.auth_rbac.infrastructure.token_blacklist import blacklist
from v2.modules.auth_rbac.schemas import KullaniciRead
from v2.modules.shared_kernel.schemas.api_responses import (
    MessageResponse,
    MessageWithWarningResponse,
)

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
    uow: UOWDep,
):
    """Login using auth_service.authenticate."""
    # ── SUPER ADMIN BYPASS ──────────────────────────────────
    # Break-glass path (rate-limit + token issuance + audit log) lives in
    # application/auth_service.py::authenticate_super_admin — every other
    # flow in this file already delegates to application/, this one used to
    # be the sole exception (2026-07-17 B.1 detective audit finding).
    super_admin_result = await auth_service.authenticate_super_admin(
        form_data.username, form_data.password, request
    )
    if super_admin_result:
        access_token, refresh_token = super_admin_result
        _set_refresh_cookie(response, refresh_token)
        return Token(access_token=access_token, token_type="bearer")

    # ── REGULAR AUTH ──────────────────────────────────────────
    access_token, refresh_token = await auth_service.authenticate(
        form_data.username, form_data.password, request, uow=uow
    )

    _set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", response_model=MessageWithWarningResponse)
async def logout(
    response: Response,
    current_user: Annotated[Kullanici, Depends(get_current_user)],
    uow: UOWDep,
    token: TokenDep,
):
    """Logout using auth_service.revoke_session and token blacklisting."""
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
        await auth_service.revoke_session(current_user.id, uow=uow)
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")

    result: dict = {"detail": "Successfully logged out"}
    if warning:
        result["warning"] = warning
    return result


@router.post("/refresh", name="auth:refresh", response_model=Token)
async def refresh_access_token(
    response: Response,
    uow: UOWDep,
    cookie_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
    data: RefreshTokenRequest = RefreshTokenRequest(),
):
    """Token Refresh with Rotation. Reads refresh_token from httpOnly cookie."""
    token = cookie_token or data.refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token eksik")

    access_token, new_refresh_token = await auth_service.refresh_session(token, uow=uow)
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
async def request_password_reset(data: PasswordResetRequest, uow: UOWDep):
    """Password reset token generation logic."""
    from v2.modules.notification.public import send_password_reset

    token = await auth_service.request_password_reset(data.email, uow=uow)

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
async def confirm_password_reset(data: PasswordResetConfirm, uow: UOWDep):
    """Password reset execution."""
    success = await auth_service.reset_password(data.token, data.new_password, uow=uow)
    if not success:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş token")

    return {"detail": "Şifreniz başarıyla güncellendi"}
