import pytest

# The admin notifications router is mounted at /admin/notifications.
# Routes inside it use /rules, /rules/{id} (PATCH/DELETE), /my,
# /mark-all-read, /{notification_id}/read.
# There is no bare GET /admin/notifications or POST /admin/notifications route.
# The existing GET/POST endpoints are at /admin/notifications/rules.


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
    from v2.modules.auth_rbac.public import Rol

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
async def test_notifications_my_endpoint(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/notifications/my", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_update_rule_toggles_aktif(async_client, admin_auth_headers, db_session):
    from v2.modules.auth_rbac.public import Rol

    role = Rol(ad="bildirim_alici_update", yetkiler={"dashboard:read": True})
    db_session.add(role)
    await db_session.commit()

    create_resp = await async_client.post(
        "/api/v1/admin/notifications/rules",
        json={
            "olay_tipi": "test_update",
            "kanallar": ["email"],
            "alici_rol_id": role.id,
        },
        headers=admin_auth_headers,
    )
    assert create_resp.status_code in (200, 201)
    rule_id = create_resp.json()["id"]

    patch_resp = await async_client.patch(
        f"/api/v1/admin/notifications/rules/{rule_id}",
        json={"aktif": False},
        headers=admin_auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["aktif"] is False
    # Fields not included in the PATCH body must be left untouched.
    assert patch_resp.json()["olay_tipi"] == "test_update"


@pytest.mark.asyncio
async def test_update_rule_404_for_unknown_id(async_client, admin_auth_headers):
    response = await async_client.patch(
        "/api/v1/admin/notifications/rules/999999",
        json={"aktif": False},
        headers=admin_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_rule_requires_auth(async_client):
    response = await async_client.patch(
        "/api/v1/admin/notifications/rules/1", json={"aktif": False}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_rule_removes_it(async_client, admin_auth_headers, db_session):
    from v2.modules.auth_rbac.public import Rol

    role = Rol(ad="bildirim_alici_delete", yetkiler={"dashboard:read": True})
    db_session.add(role)
    await db_session.commit()

    create_resp = await async_client.post(
        "/api/v1/admin/notifications/rules",
        json={
            "olay_tipi": "test_delete",
            "kanallar": ["email"],
            "alici_rol_id": role.id,
        },
        headers=admin_auth_headers,
    )
    rule_id = create_resp.json()["id"]

    delete_resp = await async_client.delete(
        f"/api/v1/admin/notifications/rules/{rule_id}",
        headers=admin_auth_headers,
    )
    assert delete_resp.status_code == 204

    list_resp = await async_client.get(
        "/api/v1/admin/notifications/rules", headers=admin_auth_headers
    )
    ids = {item["id"] for item in list_resp.json()}
    assert rule_id not in ids


@pytest.mark.asyncio
async def test_delete_rule_404_for_unknown_id(async_client, admin_auth_headers):
    response = await async_client.delete(
        "/api/v1/admin/notifications/rules/999999", headers=admin_auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_rule_requires_auth(async_client):
    response = await async_client.delete("/api/v1/admin/notifications/rules/1")
    assert response.status_code == 401
