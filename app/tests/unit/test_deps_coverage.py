"""Tests for app/api/deps.py — real DB, real JWT, real Redis blacklist.

Previously these overrode get_db with an AsyncMock session, built MagicMock
Kullanici/Rol objects, and patched blacklist/job-manager internals, asserting on
status codes produced from mocked plumbing. Here the dependency functions run
for real: tokens are real signed JWTs, the user lookup hits the real test DB
(async_client shares the conftest-monkeypatched session, so rows seeded via
db_session are visible to the request), the blacklist is the real Redis-backed
one, and the service factories build real services from a real UnitOfWork.

Only genuinely framework/pure-logic objects are constructed directly (a real
Starlette Request, real Kullanici/Rol entities for the permission-logic check) —
no MagicMock, no mocked session/repo.
"""

from datetime import timedelta

import pytest
from sqlalchemy import insert

from v2.modules.auth_rbac.domain.security import create_access_token
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.platform_infra.security.pii_encryption import blind_index

pytestmark = pytest.mark.integration
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(sub="testuser@example.com", typ="access", is_super=False):
    data: dict = {"sub": sub, "typ": typ, "is_super": is_super}
    return create_access_token(data=data, expires_delta=timedelta(minutes=30))


async def _seed_user(db_session, *, email, aktif=True, is_admin=False):
    """Insert a real Rol + Kullanici and return the user id."""
    rid = (
        await db_session.execute(
            insert(Rol).values(
                ad="admin" if is_admin else "izleyici",
                yetkiler={"*": True} if is_admin else {"sefer:read": True},
            )
        )
    ).inserted_primary_key[0]
    uid = (
        await db_session.execute(
            insert(Kullanici).values(
                email=email,
                email_bidx=blind_index(email),
                sifre_hash="x",
                ad_soyad="Test User",
                rol_id=rid,
                aktif=aktif,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return uid


def _real_request(path="/x", ip="1.2.3.4"):
    """A real Starlette Request (no mock) for direct get_current_user calls."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": (ip, 0),
    }
    return Request(scope)


# ---------------------------------------------------------------------------
# get_current_user — auth flow (real DB + real Redis blacklist)
# ---------------------------------------------------------------------------


async def test_get_current_user_blacklisted_token(db_session, monkeypatch):
    """A really-blacklisted token → 401 (real blacklist + real Redis round-trip).

    conftest's autouse ``bypass_token_blacklist`` fixture monkeypatches
    is_blacklisted → False so ordinary test tokens aren't rejected. This test
    restores the REAL is_blacklisted for itself and blacklists the token through
    the real Redis-backed store, then asserts get_current_user rejects it — the
    full deps blacklist gate, end to end, no stub.
    """
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from app.api import deps
    from v2.modules.auth_rbac.infrastructure.token_blacklist import (
        TokenBlacklist,
        blacklist,
    )

    # Undo the autouse bypass for THIS test → real is_blacklisted.
    monkeypatch.setattr(
        blacklist,
        "is_blacklisted",
        TokenBlacklist.is_blacklisted.__get__(blacklist, TokenBlacklist),
    )

    token = _make_token()
    await blacklist.add(token, datetime.now(timezone.utc) + timedelta(minutes=30))
    assert await blacklist.is_blacklisted(token) is True  # real Redis round-trip

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(_real_request(), db_session, token)
    assert exc.value.status_code == 401
    assert "blacklisted" in str(exc.value.detail).lower()


async def test_get_current_user_wrong_token_type(async_client):
    """Token with typ='refresh' is rejected → 401."""
    token = create_access_token(
        data={"sub": "user@x.com", "typ": "refresh"},
        expires_delta=timedelta(minutes=30),
    )
    resp = await async_client.get(
        "/api/v1/drivers/", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


async def test_get_current_user_missing_sub(async_client):
    """Token with no 'sub' claim → 401."""
    token = create_access_token(
        data={"typ": "access"}, expires_delta=timedelta(minutes=30)
    )
    resp = await async_client.get(
        "/api/v1/drivers/", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


async def test_get_current_user_not_in_db(async_client, db_session):
    """Valid token but the user is not in the DB → 401."""
    token = _make_token(sub="ghost@example.com")
    resp = await async_client.get(
        "/api/v1/drivers/", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


async def test_get_current_user_inactive_user(async_client, db_session):
    """Valid token but the user is inactive → 403."""
    await _seed_user(db_session, email="inactive@example.com", aktif=False)
    token = _make_token(sub="inactive@example.com")
    resp = await async_client.get(
        "/api/v1/drivers/", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_get_current_user_super_admin_virtual_user(async_client, db_session):
    """Super-admin token with no seed admin row → virtual break-glass user (id=0),
    still allowed (not 401)."""
    from app.config import settings

    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True, "typ": "access"},
        expires_delta=timedelta(minutes=30),
    )
    # db_session truncates all tables per test → no seed admin row present.
    resp = await async_client.get(
        "/api/v1/drivers/fleet-stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 401


async def test_get_current_user_super_admin_resolves_real_db_id(db_session):
    """ARCH-001: super-admin token resolves to the real seeded admin row (real id +
    is_env_superadmin marker) so audit captures a real user_id."""
    from app.api import deps
    from app.config import settings

    uid = await _seed_user(
        db_session, email=settings.SUPER_ADMIN_USERNAME, is_admin=True
    )
    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True, "typ": "access"},
        expires_delta=timedelta(minutes=30),
    )

    user = await deps.get_current_user(_real_request(), db_session, token)

    assert user.id == uid
    assert user.email == settings.SUPER_ADMIN_USERNAME
    assert getattr(user, "is_env_superadmin", False) is True


async def test_get_current_user_expired_token(async_client):
    """Expired token → 401 (emit_jwt_anomaly runs for real, best-effort)."""
    expired_token = create_access_token(
        data={"sub": "user@x.com", "typ": "access"},
        expires_delta=timedelta(seconds=-1),
    )
    resp = await async_client.get(
        "/api/v1/drivers/", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Service factory functions — real UnitOfWork builds real services
# ---------------------------------------------------------------------------


async def test_service_factories_build_real_services():
    """Each get_*_service factory builds the real service from a real UoW.

    get_arac_service/get_dorse_service removed from deps.py in dalga 3 —
    fleet no longer has service classes (B.1 free-function refactor); the
    v2 routers call use-case functions directly, no DI factory to assert on.
    get_yakit_service removed from deps.py in dalga 4 for the same reason —
    fuel no longer has a YakitService class, v2 fuel routes call use-case
    functions directly.
    get_sofor_service removed from deps.py in dalga 5 for the same reason —
    driver no longer has a SoforService class, v2 driver routes call
    use-case functions directly.
    get_auth_service/AuthService removed from deps.py in dalga 6 for the same
    reason — auth_rbac no longer has an AuthService class, auth_routes.py
    calls the auth_service module's free functions directly with an
    explicit uow= kwarg (no DI factory to assert on).
    """
    from app.api import deps
    from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
    from v2.modules.trip.application.trip_service import SeferService

    async with UnitOfWork() as uow:
        assert isinstance(await deps.get_sefer_service(uow), SeferService)


async def test_get_background_job_manager_returns_manager():
    """get_background_job_manager returns the real BackgroundJobManager singleton."""
    from app.api.deps import get_background_job_manager
    from app.infrastructure.background.job_manager import BackgroundJobManager

    mgr = await get_background_job_manager()
    assert isinstance(mgr, BackgroundJobManager)


# ---------------------------------------------------------------------------
# require_permissions — factory + real permission logic
# ---------------------------------------------------------------------------


async def test_require_permissions_factory_returns_callable():
    """require_permissions returns an async callable checker."""
    from app.api.deps import require_permissions
    from v2.modules.auth_rbac.domain.security_service import Permission

    checker = require_permissions(Permission.ADMIN)
    assert callable(checker)


async def test_require_permissions_denies_without_perm():
    """A real non-admin user is denied ADMIN by the real SecurityService → 403."""
    from fastapi import HTTPException

    from app.api.deps import require_permissions
    from v2.modules.auth_rbac.domain.security_service import Permission

    # Real entities (no mock); verify_permission reads user.rol.yetkiler.
    user = Kullanici(id=1, email="user@x.com", aktif=True, sifre_hash="x")
    user.rol = Rol(id=1, ad="izleyici", yetkiler={})

    checker = require_permissions(Permission.ADMIN)
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403
