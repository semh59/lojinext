"""Per-request FastAPI dependency factories.

Bu modül, endpoint handler'larının ``Depends()`` ile bağlandığı kısa
ömürlü (request-scoped) bağımlılıkları tanımlar.

─── DI Mimarisi — iki katmanlı ─────────────────────────────────────────────
1. ``app/api/deps.py`` (bu dosya)
   • UnitOfWork aracılığıyla transaction-scoped servis örnekleri oluşturur.
   • Her istek için yeni bir servis örneği üretilir; UoW commit/rollback
     garantisi request lifecycle'ına bağlıdır.
   • Kullanım alanı: domain CRUD endpoint'leri (araç, şoför, sefer, yakıt…)

2. ``app/core/container.py``
   • Uygulama ömrü boyunca yaşayan singleton servisler tutar
     (ML motoru, AI/RAG, anomali dedektörü, hava durumu vb.).
   • UoW gerektirmeyen, durumsuz (stateless) veya pahalı başlangıç
     maliyeti olan servisler buraya aittir.
   • Endpoint'lerin doğrudan bu container'a bağlanması GEREKMEYİP
     yalnızca ``container.py`` içindeki property'ler aracılığıyla erişilir.

Kural: Transactional domain servisleri için bu modülü kullan;
       ML/AI/infrastructure singleton'ları için container'ı kullan.
────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, List, Union

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

if TYPE_CHECKING:
    from app.core.services.sefer_service import SeferService
    from app.core.services.sofor_service import SoforService
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.services.auth_service import AuthService
from app.core.services.security_service import Permission, SecurityService
from app.core.services.weather_service import WeatherService, get_weather_service
from app.database.connection import get_db
from app.database.models import Kullanici, Rol
from app.database.unit_of_work import UnitOfWork, get_uow
from app.infrastructure.background.job_manager import (
    BackgroundJobManager,
    get_job_manager,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.token_blacklist import blacklist

logger = get_logger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]
WeatherServiceDep = Annotated[WeatherService, Depends(get_weather_service)]
UOWDep = Annotated[UnitOfWork, Depends(get_uow)]


async def get_auth_service(uow: UOWDep) -> AuthService:
    return AuthService(uow)


async def get_background_job_manager() -> BackgroundJobManager:
    return get_job_manager()


async def get_sofor_service(uow: UOWDep) -> "SoforService":
    from app.core.services.sofor_service import SoforService

    return SoforService(repo=uow.sofor_repo)


async def get_sefer_service(uow: UOWDep) -> "SeferService":
    from app.core.services.sefer_service import SeferService

    return SeferService(repo=uow.sefer_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# Blacklist logic moved to top imports
async def get_current_user(
    request: Request, db: SessionDep, token: TokenDep
) -> Kullanici:
    # B-86: Deny blacklisted tokens (e.g., after logout)
    if await blacklist.is_blacklisted(token):
        logger.warning("Blacklisted token attempt detected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is blacklisted",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Phase 3 Security: Add leeway for clock skew. Verify aud/iss claims
        # so tokens issued for a different service or environment are rejected.
        if settings.ALGORITHM == "RS256" and settings.JWT_PUBLIC_KEY:
            _decode_key = settings.JWT_PUBLIC_KEY.get_secret_value()
        else:
            _decode_key = settings.SECRET_KEY.get_secret_value()
        payload = jwt.decode(
            token,
            _decode_key,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            leeway=60,  # PyJWT: leeway is a top-level kwarg, not an options key
        )
        token_type = payload.get("typ")
        username: str = payload.get("sub")
        is_super: bool = payload.get("is_super", False)

        if token_type != "access":
            logger.warning(f"Token validation failed: Invalid typ={token_type!r}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if username is None:
            logger.warning("Token validation failed: Missing subject (sub)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        if is_super and username == settings.SUPER_ADMIN_USERNAME:
            logger.info(f"Super admin access granted: {username}")

            # ARCH-001: Resolve the env break-glass superadmin to the real seed
            # admin row (email == SUPER_ADMIN_USERNAME) so audit captures a real
            # user_id instead of NULL.
            #
            # Two failure modes handled differently:
            #   DB DOWN (Exception)  → keep break-glass usable in all envs
            #   ROW MISSING (None)   → seed issue; fail in prod, warn in dev/test
            _db_down = False
            try:
                from app.infrastructure.security.pii_encryption import blind_index

                _res = await db.execute(
                    select(Kullanici)
                    .options(selectinload(Kullanici.rol))
                    .where(
                        Kullanici.email_bidx
                        == blind_index(settings.SUPER_ADMIN_USERNAME)
                    )
                )
                real_admin = _res.scalar_one_or_none()
            except Exception as _e:
                logger.error(
                    "Superadmin DB resolve failed (DB unreachable?), "
                    "using virtual id=0 break-glass: %s",
                    _e,
                )
                real_admin = None
                _db_down = True

            if isinstance(real_admin, Kullanici):
                setattr(real_admin, "is_env_superadmin", True)
                return real_admin

            # Row not found — seed migration missing or DB outage.
            if not _db_down and settings.ENVIRONMENT == "prod":
                # Production must always have seed row. Fail loudly so ops
                # knows to run `alembic upgrade head` / seed migration.
                logger.error(
                    "ARCH-001: Superadmin seed row absent in prod DB "
                    "(SUPER_ADMIN_USERNAME=%s). Run seed migration.",
                    settings.SUPER_ADMIN_USERNAME,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Superadmin account not seeded. Contact administrator.",
                )

            # Dev / test / DB-down: fall back to virtual id=0 (break-glass).
            logger.warning(
                "Superadmin row not resolvable; using virtual id=0 "
                "(audit for this session will be anonymous). "
                "db_down=%s env=%s",
                _db_down,
                settings.ENVIRONMENT,
            )
            super_role = Rol(
                id=0,
                ad="super_admin",
                yetkiler={"*": True},
                olusturma=datetime.now(timezone.utc),
            )
            virtual_user = Kullanici(
                id=0,
                email=f"{username}@lojinext.internal"
                if "@" not in username
                else username,
                ad_soyad="Super Administrator",
                rol_id=0,
                rol=super_role,
                aktif=True,
                sifre_hash="",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                son_giris=datetime.now(timezone.utc),
            )
            setattr(virtual_user, "is_env_superadmin", True)
            return virtual_user

    except jwt.ExpiredSignatureError:
        from app.infrastructure.monitoring.security_probe import emit_jwt_anomaly

        _ip = request.client.host if request.client else ""
        emit_jwt_anomaly("ExpiredSignatureError", str(request.url.path), _ip)
        logger.warning("Token signature has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        from app.infrastructure.monitoring.security_probe import emit_jwt_anomaly

        _ip = request.client.host if request.client else ""
        _exc_type = type(e).__name__
        emit_jwt_anomaly(_exc_type, str(request.url.path), _ip)
        logger.warning(f"Token decoding failed or other error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.infrastructure.security.pii_encryption import blind_index

    result = await db.execute(
        select(Kullanici)
        .options(selectinload(Kullanici.rol))
        .where(Kullanici.email_bidx == blind_index(username))
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Authenticated user not found in DB: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.aktif:
        logger.warning(f"Inactive user attempted access: {username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user


async def get_current_active_admin(
    current_user: Annotated[Kullanici, Depends(get_current_user)],
) -> Kullanici:
    """RBAC check for ADMIN level access."""
    SecurityService.verify_permission(current_user, Permission.ADMIN)
    return current_user


async def get_current_active_user(
    current_user: Annotated[Kullanici, Depends(get_current_user)],
) -> Kullanici:
    """Active user guard used by endpoints requiring only authentication."""
    return current_user


async def get_current_superadmin(
    current_user: Annotated[Kullanici, Depends(get_current_user)],
) -> Kullanici:
    """RBAC check for SUPERADMIN level access."""
    SecurityService.verify_permission(current_user, Permission.SUPERADMIN)
    return current_user


def require_permissions(required_permission: Union[Permission, str, List[str]]):
    """
    FastAPI dependency injection factory for granular RBAC controls.
    Kullanım: current_user: Kullanici = Depends(require_permissions("sefer:write"))
    """

    async def permission_checker(
        current_user: Annotated[Kullanici, Depends(get_current_user)],
    ) -> Kullanici:
        SecurityService.verify_permission(current_user, required_permission)
        return current_user

    return permission_checker
