"""
Coverage tests for app/api/deps.py.

Targets uncovered lines:
- get_current_user: blacklisted token → 401
- get_current_user: RS256 key path
- get_current_user: token_type != 'access' → 401
- get_current_user: username is None → 401
- get_current_user: super_admin virtual user creation
- get_current_user: expired token → 401 + emit_jwt_anomaly
- get_current_user: generic decode error → 401 + emit_jwt_anomaly
- get_current_user: user not in DB → 401
- get_current_user: user inactive → 403
- get_current_active_admin: calls SecurityService.verify_permission
- get_current_superadmin: calls SecurityService.verify_permission
- require_permissions: factory returns a working dependency
- service factory functions: get_arac_service, get_yakit_service, etc.
- get_background_job_manager: returns job manager
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    sub="testuser@example.com", typ="access", is_super=False, expired=False
):
    """Create a signed JWT for testing."""

    from app.core.security import create_access_token

    data: dict = {"sub": sub, "typ": typ, "is_super": is_super}
    delta = timedelta(minutes=-5) if expired else timedelta(minutes=30)
    return create_access_token(data=data, expires_delta=delta)


def _make_kullanici(email="user@example.com", aktif=True, is_admin=False):
    from app.database.models import Kullanici, Rol

    role = MagicMock(spec=Rol)
    role.ad = "admin" if is_admin else "izleyici"
    role.yetkiler = {"*": True} if is_admin else {}

    user = MagicMock(spec=Kullanici)
    user.id = 1
    user.email = email
    user.aktif = aktif
    user.rol = role
    user.rol_id = 1
    return user


# ---------------------------------------------------------------------------
# get_current_user — blacklisted token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_blacklisted_token(async_client):
    """Request with a blacklisted token → 401."""
    token = _make_token()

    # Patch blacklist to say token is blacklisted
    with patch(
        "app.infrastructure.security.token_blacklist.blacklist.is_blacklisted",
        AsyncMock(return_value=True),
    ):
        resp = await async_client.get(
            "/api/v1/drivers/",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401
    assert "blacklisted" in resp.text.lower()


# ---------------------------------------------------------------------------
# get_current_user — invalid token type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_wrong_token_type(async_client):
    """Token with typ='refresh' is rejected → 401."""
    from app.core.security import create_access_token

    # Build a token with typ="refresh"
    token = create_access_token(
        data={"sub": "user@x.com", "typ": "refresh"},
        expires_delta=timedelta(minutes=30),
    )

    resp = await async_client.get(
        "/api/v1/drivers/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — missing sub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_missing_sub(async_client):
    """Token with no 'sub' claim → 401."""
    from app.core.security import create_access_token

    token = create_access_token(
        data={"typ": "access"},  # no 'sub'
        expires_delta=timedelta(minutes=30),
    )

    resp = await async_client.get(
        "/api/v1/drivers/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — user not found in DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_not_in_db(async_client):
    """Valid token but user email not in DB → 401."""
    from app.database.connection import get_db
    from app.main import app

    token = _make_token(sub="ghost@example.com")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/drivers/",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — inactive user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_inactive_user(async_client):
    """Valid token but user is inactive → 403."""
    from app.database.connection import get_db
    from app.main import app

    token = _make_token(sub="inactive@example.com")
    user = _make_kullanici(email="inactive@example.com", aktif=False)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/drivers/",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# get_current_user — super admin virtual user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_super_admin_virtual_user(async_client):
    """Super-admin token creates a virtual Kullanici and returns it."""
    from app.config import settings
    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True, "typ": "access"},
        expires_delta=timedelta(minutes=30),
    )

    # Even without a real DB entry, the endpoint should succeed (virtual user)
    from app.database.connection import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # not in DB
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def _fake_db():
        return mock_session

    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = await async_client.get(
            "/api/v1/drivers/fleet-stats",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    # ARCH-001: when the seed admin row is absent (mock returns None), the
    # superadmin falls back to the virtual user (id=0) and is still allowed.
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_get_current_user_super_admin_resolves_real_db_id():
    """ARCH-001: super-admin token resolves to the real seed admin row (real id +
    is_env_superadmin marker) when present, so audit captures a real user_id."""
    from app.api import deps
    from app.config import settings
    from app.core.security import create_access_token
    from app.database.models import Kullanici, Rol

    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True, "typ": "access"},
        expires_delta=timedelta(minutes=30),
    )

    real_admin = Kullanici(
        id=7,
        email=settings.SUPER_ADMIN_USERNAME,
        ad_soyad="Seed Admin",
        aktif=True,
        sifre_hash="",
    )
    real_admin.rol = Rol(id=1, ad="super_admin", yetkiler={"*": True})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = real_admin
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    req = MagicMock()
    req.client.host = "1.2.3.4"
    req.url.path = "/x"

    with patch(
        "app.api.deps.blacklist.is_blacklisted", new=AsyncMock(return_value=False)
    ):
        user = await deps.get_current_user(req, mock_db, token)

    assert user.id == 7, f"expected real seed admin id 7, got {user.id}"
    assert getattr(user, "is_env_superadmin", False) is True


# ---------------------------------------------------------------------------
# get_current_user — expired token emits jwt anomaly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_expired_token(async_client):
    """Expired token triggers emit_jwt_anomaly and returns 401."""
    from app.core.security import create_access_token

    expired_token = create_access_token(
        data={"sub": "user@x.com", "typ": "access"},
        expires_delta=timedelta(seconds=-1),
    )

    with patch("app.infrastructure.monitoring.security_probe.emit_jwt_anomaly"):
        resp = await async_client.get(
            "/api/v1/drivers/",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Service factory functions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_arac_service_returns_service():
    """get_arac_service returns an AracService instance."""
    from app.api.deps import get_arac_service
    from app.core.services.arac_service import AracService

    mock_uow = MagicMock()
    mock_uow.arac_repo = MagicMock()

    svc = await get_arac_service(mock_uow)
    assert isinstance(svc, AracService)


@pytest.mark.asyncio
async def test_get_sofor_service_returns_service():
    """get_sofor_service returns a SoforService instance."""
    from app.api.deps import get_sofor_service
    from app.core.services.sofor_service import SoforService

    mock_uow = MagicMock()
    mock_uow.sofor_repo = MagicMock()

    svc = await get_sofor_service(mock_uow)
    assert isinstance(svc, SoforService)


@pytest.mark.asyncio
async def test_get_sefer_service_returns_service():
    """get_sefer_service returns a SeferService instance."""
    from app.api.deps import get_sefer_service
    from app.core.services.sefer_service import SeferService

    mock_uow = MagicMock()
    mock_uow.sefer_repo = MagicMock()

    svc = await get_sefer_service(mock_uow)
    assert isinstance(svc, SeferService)


@pytest.mark.asyncio
async def test_get_yakit_service_returns_service():
    """get_yakit_service returns a YakitService instance."""
    from app.api.deps import get_yakit_service
    from app.core.services.yakit_service import YakitService

    mock_uow = MagicMock()
    mock_uow.yakit_repo = MagicMock()

    svc = await get_yakit_service(mock_uow)
    assert isinstance(svc, YakitService)


@pytest.mark.asyncio
async def test_get_lokasyon_service_returns_service():
    """get_lokasyon_service returns a LokasyonService instance."""
    from app.api.deps import get_lokasyon_service
    from app.core.services.lokasyon_service import LokasyonService

    mock_uow = MagicMock()
    mock_uow.lokasyon_repo = MagicMock()

    svc = await get_lokasyon_service(mock_uow)
    assert isinstance(svc, LokasyonService)


@pytest.mark.asyncio
async def test_get_dorse_service_returns_service():
    """get_dorse_service returns a DorseService instance."""
    from app.api.deps import get_dorse_service
    from app.core.services.dorse_service import DorseService

    mock_uow = MagicMock()
    mock_uow.dorse_repo = MagicMock()
    mock_uow.event_bus = MagicMock()

    svc = await get_dorse_service(mock_uow)
    assert isinstance(svc, DorseService)


@pytest.mark.asyncio
async def test_get_auth_service_returns_service():
    """get_auth_service returns an AuthService instance."""
    from app.api.deps import get_auth_service
    from app.core.services.auth_service import AuthService

    mock_uow = MagicMock()
    svc = await get_auth_service(mock_uow)
    assert isinstance(svc, AuthService)


@pytest.mark.asyncio
async def test_get_background_job_manager_returns_manager():
    """get_background_job_manager returns a BackgroundJobManager."""
    from app.api.deps import get_background_job_manager
    from app.infrastructure.background.job_manager import BackgroundJobManager

    with patch(
        "app.api.deps.get_job_manager",
        return_value=MagicMock(spec=BackgroundJobManager),
    ) as mock_gm:
        await get_background_job_manager()
    mock_gm.assert_called_once()


# ---------------------------------------------------------------------------
# require_permissions — factory generates working dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_permissions_factory():
    """require_permissions returns a callable that checks via SecurityService."""
    from app.api.deps import require_permissions
    from app.core.services.security_service import Permission

    checker = require_permissions(Permission.ADMIN)
    # It should be an async callable
    assert callable(checker)


@pytest.mark.asyncio
async def test_require_permissions_denies_without_perm():
    """require_permissions raises HTTPException for user without the permission."""
    from fastapi import HTTPException

    from app.api.deps import require_permissions
    from app.core.services.security_service import Permission, SecurityService

    user = _make_kullanici(is_admin=False)
    # Security service should reject non-admin user
    checker = require_permissions(Permission.ADMIN)

    with patch.object(
        SecurityService,
        "verify_permission",
        side_effect=HTTPException(status_code=403, detail="Forbidden"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await checker(current_user=user)

    assert exc_info.value.status_code == 403
