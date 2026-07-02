"""Integration tests for admin users endpoint — /api/v1/admin/users/"""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

BASE = "/api/v1/admin/users"


# ---------------------------------------------------------------------------
# POST /api/v1/admin/users/ — create user
# ---------------------------------------------------------------------------


async def test_create_user_admin_returns_201(
    async_client, admin_auth_headers, db_session
):
    """Admin can create a new user and gets 201 back."""
    from sqlalchemy import select

    from app.database.models import Rol

    # Ensure a role exists so we can reference it
    result = await db_session.execute(select(Rol).limit(1))
    role = result.scalar_one_or_none()
    if role is None:
        role = Rol(ad="test-rol", yetkiler={"sefer:read": True})
        db_session.add(role)
        await db_session.commit()

    payload = {
        "email": "newadminuser@lojinext.test",
        "ad_soyad": "Yeni Kullanici",
        "rol_id": role.id,
        "sifre": "Guclu1234!",
        "aktif": True,
    }
    response = await async_client.post(
        f"{BASE}/", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["email"] == payload["email"]
    assert body["ad_soyad"] == payload["ad_soyad"]
    assert "id" in body


async def test_create_user_sets_olusturan_id(
    async_client, admin_auth_headers, db_session
):
    """
    When admin creates a user the ``olusturan_id`` column should reflect
    the creator. The virtual super-admin has id=0, which service maps to None;
    the important thing is the endpoint does NOT crash and the user is created.
    """
    from sqlalchemy import select

    from app.database.models import Kullanici, Rol
    from app.infrastructure.security.pii_encryption import blind_index

    result = await db_session.execute(select(Rol).limit(1))
    role = result.scalar_one_or_none()
    if role is None:
        role = Rol(ad="test-rol-2", yetkiler={"sefer:read": True})
        db_session.add(role)
        await db_session.commit()

    payload = {
        "email": "olusturan_check@lojinext.test",
        "ad_soyad": "Olusturan Check",
        "rol_id": role.id,
        "sifre": "Guclu1234!",
        "aktif": True,
    }
    response = await async_client.post(
        f"{BASE}/", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 201, response.text

    # Verify row is in DB
    row = await db_session.execute(
        select(Kullanici).where(Kullanici.email_bidx == blind_index(payload["email"]))
    )
    user = row.scalar_one_or_none()
    assert user is not None
    # Super-admin (id=0) maps to olusturan_id=None in service logic
    assert user.olusturan_id is None


async def test_create_user_invalid_role_never_succeeds(
    async_client, admin_auth_headers
):
    """Var olmayan rol_id ile kullanıcı oluşturmak 400 döndürmelidir."""
    payload = {
        "email": "badroluser@lojinext.test",
        "ad_soyad": "Bad Rol User",
        "rol_id": 999999,
        "sifre": "Guclu1234!",
        "aktif": True,
    }
    response = await async_client.post(
        f"{BASE}/", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 400
    data = response.json()
    assert "rol" in data.get("detail", "").lower() or "error" in data


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users/ — list users
# ---------------------------------------------------------------------------


async def test_list_users_admin_gets_200(async_client, admin_auth_headers):
    """Admin can list users and gets 200 with a list payload."""
    response = await async_client.get(f"{BASE}/", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


async def test_list_users_normal_user_gets_403(async_client, normal_auth_headers):
    """Normal user (lacking kullanici_goruntule permission) gets 403."""
    response = await async_client.get(f"{BASE}/", headers=normal_auth_headers)
    assert response.status_code == 403, response.text


async def test_list_users_no_auth_gets_401(async_client):
    """Unauthenticated request is rejected with 401."""
    response = await async_client.get(f"{BASE}/")
    assert response.status_code == 401, response.text
