"""Coverage tests for app/api/v1/endpoints/auth.py.

Covers: login (super-admin bypass + regular), logout, refresh, /me,
password-reset-request, password-reset-confirm.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ─── helpers ─────────────────────────────────────────────────────────────────


def _make_fake_auth_service(
    *,
    authenticate=None,
    refresh_session=None,
    revoke_session=None,
    request_password_reset=None,
    reset_password=None,
):
    svc = AsyncMock()
    if authenticate is not None:
        svc.authenticate = authenticate
    else:
        svc.authenticate = AsyncMock(return_value=("access_tok", "refresh_tok"))
    if refresh_session is not None:
        svc.refresh_session = refresh_session
    else:
        svc.refresh_session = AsyncMock(return_value=("new_access", "new_refresh"))
    if revoke_session is not None:
        svc.revoke_session = revoke_session
    else:
        svc.revoke_session = AsyncMock()
    if request_password_reset is not None:
        svc.request_password_reset = request_password_reset
    else:
        svc.request_password_reset = AsyncMock(return_value="reset-token-xyz")
    if reset_password is not None:
        svc.reset_password = reset_password
    else:
        svc.reset_password = AsyncMock(return_value=True)
    return svc


@contextmanager
def _override_auth_service(fake_svc):
    """Context manager to monkeypatch the free-function auth_service module.

    ``v2.modules.auth_rbac.api.auth_routes`` calls ``auth_service.<fn>(...)``
    directly (no FastAPI DI factory anymore — the ``AuthService`` class and
    its ``get_auth_service`` dependency were removed in the B.1 free-function
    migration). Patch each of the 5 use-case functions on the module object
    that ``auth_routes`` imported, so every call site sees the fake.
    """
    from v2.modules.auth_rbac.api import auth_routes

    originals = {
        name: getattr(auth_routes.auth_service, name)
        for name in (
            "authenticate",
            "refresh_session",
            "revoke_session",
            "request_password_reset",
            "reset_password",
        )
    }
    for name in originals:
        fake_fn = getattr(fake_svc, name)

        async def _bound(*args, _fake_fn=fake_fn, uow=None, **kwargs):
            return await _fake_fn(*args, **kwargs)

        setattr(auth_routes.auth_service, name, _bound)
    try:
        yield
    finally:
        for name, fn in originals.items():
            setattr(auth_routes.auth_service, name, fn)


# ─── POST /auth/token — super-admin bypass ───────────────────────────────────


async def test_login_super_admin_bypass(async_client):
    """Super-admin credentials bypass regular DB auth and return a token."""
    from app.config import settings

    username = settings.SUPER_ADMIN_USERNAME
    try:
        password = settings.SUPER_ADMIN_PASSWORD.get_secret_value()
    except Exception:
        pytest.skip("SUPER_ADMIN_PASSWORD not configured")

    resp = await async_client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


async def test_login_wrong_super_admin_password_falls_through(async_client):
    """Wrong password for super-admin → falls through to regular auth → non-200."""
    from app.config import settings
    from v2.modules.shared_kernel.exceptions import DomainError

    fake_svc = _make_fake_auth_service(
        authenticate=AsyncMock(side_effect=DomainError("bad credentials"))
    )

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/token",
            data={
                "username": settings.SUPER_ADMIN_USERNAME,
                "password": "wrong_password_xyz",  # pragma: allowlist secret
            },
        )
    # Either DomainError → 400 or auth service raises → non-200
    assert resp.status_code in (400, 401, 422, 500)


async def test_super_admin_login_rate_limited_after_repeated_attempts(async_client):
    """2026-07-01 prod-grade denetimi P1: break-glass süper-admin girişi
    önceden genel `auth_token` bucket'ını (5 req/s) paylaşıyordu — bu,
    şifrenin saniyede birkaç deneme hızıyla brute-force edilebileceği
    anlamına geliyordu. Artık ayrı, çok sıkı bir bucket (5 dakikada 3
    deneme) var; bu bucket hem başarılı hem başarısız denemeleri sayar.
    """
    from app.config import settings
    from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry

    username = settings.SUPER_ADMIN_USERNAME
    try:
        settings.SUPER_ADMIN_PASSWORD.get_secret_value()  # type: ignore[union-attr]
    except Exception:
        pytest.skip("SUPER_ADMIN_PASSWORD not configured")

    # Clean slate: testler arası state sızmasını önle (bucket key artık
    # "super_admin_login:{ip}" formatında — prefix ile temizle).
    def _clear_super_admin_buckets():
        for k in [
            k
            for k in RateLimiterRegistry._limiters
            if k.startswith("super_admin_login")
        ]:
            RateLimiterRegistry._limiters.pop(k, None)

    _clear_super_admin_buckets()
    try:
        for _ in range(3):
            resp = await async_client.post(
                "/api/v1/auth/token",
                data={
                    "username": username,
                    "password": "wrong_password_xyz",  # pragma: allowlist secret
                },
            )
            assert resp.status_code != 429

        resp = await async_client.post(
            "/api/v1/auth/token",
            data={
                "username": username,
                "password": "wrong_password_xyz",  # pragma: allowlist secret
            },
        )
        assert resp.status_code == 429
    finally:
        _clear_super_admin_buckets()


async def test_super_admin_rate_limit_is_scoped_per_ip(db_session):
    """2026-07-01 derin kontrol bulgusu: bucket global (tüm IP'ler ortak)
    olduğunda, kimliği doğrulanmamış bir saldırgan HERHANGİ bir IP'den 3
    yanlış şifre denemesiyle bucket'ı tüketip meşru süper-admin'in
    başka bir IP'den giriş yapmasını 5 dakika boyunca engelleyebilirdi
    (break-glass hesabına karşı DoS). Artık bucket key'e client IP dahil —
    bir IP'nin denemeleri başka bir IP'yi etkilememeli.

    `db_session` fixture'ı doğrudan istenir: bu test kendi `AsyncClient`
    örneklerini kurduğu için `async_client` fixture'ının sağladığı
    DB-izolasyon monkeypatch'lerinden (gerçek DATABASE_URL yerine test DB'si)
    otomatik yararlanamaz.
    """
    from httpx import ASGITransport, AsyncClient

    from app.config import settings
    from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry
    from app.main import app

    username = settings.SUPER_ADMIN_USERNAME
    try:
        settings.SUPER_ADMIN_PASSWORD.get_secret_value()  # type: ignore[union-attr]
    except Exception:
        pytest.skip("SUPER_ADMIN_PASSWORD not configured")

    attacker_keys = [
        k for k in RateLimiterRegistry._limiters if k.startswith("super_admin_login")
    ]
    for k in attacker_keys:
        RateLimiterRegistry._limiters.pop(k, None)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("203.0.113.9", 1234)),
            base_url="http://test",
        ) as attacker_client:
            for _ in range(3):
                resp = await attacker_client.post(
                    "/api/v1/auth/token",
                    data={
                        "username": username,
                        "password": "wrong_password_xyz",  # pragma: allowlist secret
                    },
                )
                assert resp.status_code != 429
            # Attacker's 4th attempt from the SAME ip should now be limited.
            resp = await attacker_client.post(
                "/api/v1/auth/token",
                data={
                    "username": username,
                    "password": "wrong_password_xyz",  # pragma: allowlist secret
                },
            )
            assert resp.status_code == 429

        # A DIFFERENT ip (the real super-admin, elsewhere) must be unaffected.
        async with AsyncClient(
            transport=ASGITransport(app=app, client=("198.51.100.7", 1234)),
            base_url="http://test",
        ) as victim_client:
            resp = await victim_client.post(
                "/api/v1/auth/token",
                data={
                    "username": username,
                    "password": "wrong_password_xyz",  # pragma: allowlist secret
                },
            )
            assert resp.status_code != 429
    finally:
        attacker_keys = [
            k
            for k in RateLimiterRegistry._limiters
            if k.startswith("super_admin_login")
        ]
        for k in attacker_keys:
            RateLimiterRegistry._limiters.pop(k, None)


async def test_regular_user_login_unaffected_by_super_admin_rate_limit(async_client):
    """Süper-admin'e özel sıkı rate-limit, normal kullanıcı girişini etkilememeli."""
    from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry

    RateLimiterRegistry._limiters.pop("super_admin_login", None)
    fake_svc = _make_fake_auth_service()

    with _override_auth_service(fake_svc):
        for _ in range(3):
            resp = await async_client.post(
                "/api/v1/auth/token",
                data={
                    "username": "someuser@test.com",
                    "password": "SomePass1",  # pragma: allowlist secret
                },
            )
            assert resp.status_code == 200


# ─── POST /auth/token — regular auth ─────────────────────────────────────────


async def test_login_regular_user_success(async_client):
    """Regular user auth succeeds → returns access_token."""
    fake_svc = _make_fake_auth_service()

    _pw = "SomePass1"  # pragma: allowlist secret
    _creds = {"username": "someuser@test.com", "password": _pw}
    with _override_auth_service(fake_svc):
        resp = await async_client.post("/api/v1/auth/token", data=_creds)
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "access_tok"
    assert data["token_type"] == "bearer"


async def test_login_regular_user_wrong_credentials(async_client):
    """Auth service raises DomainError → propagated as error response."""
    from v2.modules.shared_kernel.exceptions import DomainError

    fake_svc = _make_fake_auth_service(
        authenticate=AsyncMock(side_effect=DomainError("bad credentials"))
    )

    _pw = "BadPass1"  # pragma: allowlist secret
    _creds = {"username": "baduser@test.com", "password": _pw}
    with _override_auth_service(fake_svc):
        resp = await async_client.post("/api/v1/auth/token", data=_creds)
    # DomainError is caught by exception handler → non-200 (400/401/422/500)
    assert resp.status_code != 200


async def test_login_missing_username_returns_422(async_client):
    """Missing form fields → 422 validation error."""
    _pw = "SomePass1"  # pragma: allowlist secret
    resp = await async_client.post("/api/v1/auth/token", data={"password": _pw})
    assert resp.status_code == 422


# ─── POST /auth/logout ────────────────────────────────────────────────────────


async def test_logout_no_auth_returns_401(async_client):
    resp = await async_client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


async def test_logout_success(async_client, admin_auth_headers):
    """Authenticated logout → 200 with success detail."""
    fake_svc = _make_fake_auth_service()

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/logout",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "detail" in data


async def test_logout_blacklist_failure_returns_warning(
    async_client, admin_auth_headers, monkeypatch
):
    """If blacklist.add raises, logout still succeeds with a warning."""
    fake_svc = _make_fake_auth_service()

    # Patch blacklist.add to raise
    async def _bad_add(_token, _exp):
        raise RuntimeError("Redis down")

    monkeypatch.setattr(
        "v2.modules.auth_rbac.infrastructure.token_blacklist.blacklist.add",
        _bad_add,
    )

    with _override_auth_service(fake_svc):
        # Patch monitoring.aemit so it doesn't crash
        with patch("app.infrastructure.monitoring.aemit", new_callable=AsyncMock):
            resp = await async_client.post(
                "/api/v1/auth/logout",
                headers=admin_auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "warning" in data or "detail" in data


# ─── POST /auth/refresh ───────────────────────────────────────────────────────


async def test_refresh_no_token_returns_401(async_client):
    """No cookie or body token → 401."""
    resp = await async_client.post("/api/v1/auth/refresh", json={})
    assert resp.status_code == 401


async def test_refresh_success_from_body(async_client):
    """Valid refresh_token in JSON body → 200 with new access_token."""
    fake_svc = _make_fake_auth_service()

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid_refresh_token_xyz"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "new_access"


async def test_refresh_invalid_token_returns_401(async_client):
    """Invalid/expired refresh token → 401."""
    from fastapi import HTTPException

    fake_svc = _make_fake_auth_service(
        refresh_session=AsyncMock(
            side_effect=HTTPException(status_code=401, detail="Invalid token")
        )
    )

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "expired_token"},
        )
    assert resp.status_code == 401


# ─── GET /auth/me ────────────────────────────────────────────────────────────


async def test_me_requires_auth(async_client):
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(async_client, admin_auth_headers):
    """Super-admin token → /me returns user info."""
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Super admin virtual user has email containing the username
    assert "email" in data or "ad_soyad" in data


# ─── POST /auth/password-reset-request ───────────────────────────────────────


async def test_password_reset_request_success(async_client):
    """Always returns 200 (even for unknown email — anti-enumeration)."""
    fake_svc = _make_fake_auth_service(
        request_password_reset=AsyncMock(return_value=None)
    )

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "unknown@example.com"},
        )
    assert resp.status_code == 200


async def test_password_reset_request_invalid_email_returns_422(async_client):
    """Non-email string → 422 validation error."""
    resp = await async_client.post(
        "/api/v1/auth/password-reset-request",
        json={"email": "not-an-email"},
    )
    assert resp.status_code == 422


async def test_password_reset_request_with_token_in_dev(async_client, monkeypatch):
    """Non-prod env returns token in response body when auth service returns one."""
    from app.config import settings

    fake_svc = _make_fake_auth_service(
        request_password_reset=AsyncMock(return_value="dev-reset-token")
    )

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "user@example.com"},
        )
    assert resp.status_code == 200
    data = resp.json()
    # dev env includes token
    assert "token" in data or "detail" in data


# ─── POST /auth/password-reset-confirm ───────────────────────────────────────


async def test_password_reset_confirm_success(async_client):
    """Valid token + new password → 200."""
    fake_svc = _make_fake_auth_service(reset_password=AsyncMock(return_value=True))
    _new_pw = "NewPass123"  # pragma: allowlist secret
    _body = {"token": "valid-reset-token", "new_password": _new_pw}
    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/password-reset-confirm", json=_body
        )
    assert resp.status_code == 200
    assert "detail" in resp.json()


async def test_password_reset_confirm_invalid_token_returns_400(async_client):
    """Invalid/expired reset token → 400."""
    fake_svc = _make_fake_auth_service(reset_password=AsyncMock(return_value=False))
    _new_pw = "NewPass123"  # pragma: allowlist secret
    _body = {"token": "expired-token", "new_password": _new_pw}
    with _override_auth_service(fake_svc):
        resp = await async_client.post(
            "/api/v1/auth/password-reset-confirm", json=_body
        )
    assert resp.status_code == 400
