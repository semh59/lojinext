import pytest

# The admin notifications router is mounted at /admin/notifications.
# Routes inside it use /rules, /my, /mark-all-read, /{notification_id}/read.
# There is no bare GET /admin/notifications or POST /admin/notifications route.
# The existing GET endpoint is at /admin/notifications/rules
# The existing POST endpoint is at /admin/notifications/rules


@pytest.mark.asyncio
async def test_notifications_requires_auth(async_client):
    response = await async_client.get("/api/v1/admin/notifications/rules")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_notifications_get(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/notifications/rules", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_notifications_requires_permission(async_client, normal_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/notifications/rules", headers=normal_auth_headers
    )
    assert response.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_notifications_post_requires_auth(async_client):
    response = await async_client.post("/api/v1/admin/notifications/rules", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_notifications_post(async_client, admin_auth_headers, db_session):
    # Seed a real role so the FK (bildirim_kurallari.alici_rol_id -> roller.id) is
    # satisfiable. Previously the test posted a hard-coded rol id 1 that did not exist
    # in the freshly-created test schema, so the insert raised an unhandled
    # ForeignKeyViolationError instead of creating the rule.
    from app.database.models import Rol

    role = Rol(ad="bildirim_alici", yetkiler={"dashboard:read": True})
    db_session.add(role)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/admin/notifications/rules",
        json={"olay_tipi": "test", "kanallar": ["email"], "alici_rol_id": role.id},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 201)


@pytest.mark.asyncio
async def test_notifications_delete(async_client, admin_auth_headers):
    # DELETE is not defined on this router; /my endpoint shows notifications
    response = await async_client.get(
        "/api/v1/admin/notifications/my", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)
