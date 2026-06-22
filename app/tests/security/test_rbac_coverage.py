"""
Layer 4 — RBAC Coverage
Verifies that permission-gated endpoints return 403 for an unprivileged user,
401 for expired/missing tokens, and 200 for properly authorized users.
"""

from datetime import timedelta

import pytest

pytestmark = pytest.mark.integration


# ── Admin endpoint 403 matrix ────────────────────────────────────────────────

ADMIN_ENDPOINTS_403 = [
    # (method, path, body)
    ("GET", "/api/v1/admin/health/", None),
    ("GET", "/api/v1/admin/users/", None),
    ("GET", "/api/v1/admin/ml/queue", None),
    ("GET", "/api/v1/admin/maintenance/alerts", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS_403)
async def test_admin_endpoint_returns_403_for_normal_user(
    async_client, normal_auth_headers, method, path, body
):
    """Unprivileged izleyici user must receive 403 on every permission-gated endpoint."""
    if method == "GET":
        r = await async_client.get(path, headers=normal_auth_headers)
    else:
        r = await async_client.post(path, json=body or {}, headers=normal_auth_headers)

    assert r.status_code == 403, (
        f"{method} {path} returned {r.status_code} for normal user "
        f"(expected 403). Body: {r.text[:200]}"
    )


# ── Write endpoints 403 for normal user ──────────────────────────────────────

WRITE_ENDPOINTS_403 = [
    (
        "POST",
        "/api/v1/vehicles/",
        {
            "plaka": "06 ZZ 9999",
            "marka": "Test",
            "model": "X",
            "yil": 2020,
            "tank_kapasitesi": 500,
            "hedef_tuketim": 30.0,
        },
    ),
    (
        "POST",
        "/api/v1/drivers/",
        {
            "ad_soyad": "Unauthorized Sofor",
            "ehliyet_sinifi": "E",
            "ise_baslama": "2024-01-01",
            "aktif": True,
        },
    ),
    (
        "POST",
        "/api/v1/trips/",
        {
            "tarih": "2024-01-01",
            "arac_id": 1,
            "sofor_id": 1,
            "guzergah_id": 1,
            "cikis_yeri": "A",
            "varis_yeri": "B",
            "mesafe_km": 100.0,
            "net_kg": 0,
            "durum": "Planlandı",
        },
    ),
    (
        "POST",
        "/api/v1/fuel/",
        {
            "tarih": "2024-01-01",
            "arac_id": 1,
            "litre": "100.00",
            "fiyat_tl": "40.00",
            "toplam_tutar": "4000.00",
            "km_sayac": 100000,
            "depo_durumu": "Dolu",
            "durum": "Bekliyor",
        },
    ),
    (
        "POST",
        "/api/v1/locations/",
        {"cikis_yeri": "A", "varis_yeri": "B", "mesafe_km": 100.0, "zorluk": "Normal"},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", WRITE_ENDPOINTS_403)
async def test_write_endpoint_returns_403_for_normal_user(
    async_client, normal_auth_headers, method, path, body
):
    """Normal user (izleyici) must receive 403 on POST/write endpoints."""
    r = await async_client.post(path, json=body, headers=normal_auth_headers)
    assert r.status_code == 403, (
        f"POST {path} returned {r.status_code} for normal user "
        f"(expected 403). Body: {r.text[:200]}"
    )


# ── Missing token → 401 ───────────────────────────────────────────────────────

PROTECTED_ENDPOINTS = [
    "/api/v1/vehicles/",
    "/api/v1/drivers/",
    "/api/v1/trips/",
    "/api/v1/fuel/",
    "/api/v1/locations/",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
async def test_missing_token_returns_401(async_client, path):
    """No Authorization header → 401 on all protected endpoints."""
    r = await async_client.get(path)
    assert r.status_code == 401, (
        f"GET {path} without token returned {r.status_code} (expected 401)"
    )


# ── Expired JWT → 401 ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_token_returns_401(async_client):
    """JWT with past exp claim must be rejected with 401."""
    from app.config import settings
    from app.core.security import create_access_token

    expired_token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True},
        expires_delta=timedelta(seconds=-120),  # beyond the 60-second leeway
    )
    headers = {"Authorization": f"Bearer {expired_token}"}

    r = await async_client.get("/api/v1/vehicles/", headers=headers)
    assert r.status_code == 401, f"Expired token was accepted (got {r.status_code})"


# ── Malformed Bearer token → 401 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_bearer_token_returns_401(async_client):
    """Garbage JWT string must be rejected with 401."""
    headers = {"Authorization": "Bearer not.a.valid.jwt"}
    r = await async_client.get("/api/v1/vehicles/", headers=headers)
    assert r.status_code == 401, f"Malformed token was accepted (got {r.status_code})"


# ── Refresh without cookie → 401/422, never 500 ───────────────────────────────


@pytest.mark.asyncio
async def test_refresh_without_cookie_never_500(async_client):
    """POST /auth/refresh with no cookie must return 401 or 422, never 500."""
    r = await async_client.post("/api/v1/auth/refresh")
    assert r.status_code != 500, (
        f"Refresh without cookie returned 500. Body: {r.text[:200]}"
    )
    assert r.status_code in (
        401,
        422,
    ), f"Refresh without cookie returned {r.status_code} (expected 401 or 422)"


# ── Positive: normal user CAN read trips ─────────────────────────────────────


@pytest.mark.asyncio
async def test_normal_user_can_read_trips(async_client, normal_auth_headers):
    """izleyici role has sefer:read — GET /trips/ must return 200."""
    r = await async_client.get("/api/v1/trips/", headers=normal_auth_headers)
    assert r.status_code == 200, (
        f"Normal user read trips returned {r.status_code}: {r.text[:200]}"
    )


# ── Positive: admin reaches health endpoint ───────────────────────────────────


@pytest.mark.asyncio
async def test_admin_user_can_reach_health(async_client, admin_auth_headers):
    """Super-admin token must receive 200 on /admin/health/."""
    r = await async_client.get("/api/v1/admin/health/", headers=admin_auth_headers)
    assert r.status_code == 200, (
        f"Admin health returned {r.status_code}: {r.text[:200]}"
    )
