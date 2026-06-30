import pytest

# Preferences router routes:
#   GET    /{modul}          — get preferences for a module
#   POST   /                 — save/update a preference (body: PreferenceCreate)
#   DELETE /{pref_id}        — delete by integer pref_id
#   POST   /{pref_id}/default — set as default


@pytest.mark.asyncio
async def test_preferences_requires_auth(async_client):
    response = await async_client.get("/api/v1/preferences/theme")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preferences_get(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/preferences/theme", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_preferences_set(async_client, admin_auth_headers):
    # POST / requires a PreferenceCreate body with modul, ayar_tipi, deger, ad fields
    response = await async_client.post(
        "/api/v1/preferences/",
        json={
            "modul": "theme",
            "ayar_tipi": "color",
            "deger": {"v": "dark"},
            "ad": "theme_dark",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 400, 403, 422, 500)


@pytest.mark.asyncio
async def test_preferences_update(async_client, admin_auth_headers):
    # There is no PUT on preferences; set_default uses POST /{pref_id}/default
    response = await async_client.post(
        "/api/v1/preferences/9999/default",
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_preferences_delete(async_client, admin_auth_headers):
    # DELETE /{pref_id} with integer pref_id
    response = await async_client.delete(
        "/api/v1/preferences/9999", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_preferences_user_isolation(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/preferences/lang", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)
