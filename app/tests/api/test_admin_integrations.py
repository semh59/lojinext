"""Admin-configurable external API keys (2026-07-10 multi-tenant epic).

Write-only by design: PUT accepts a plaintext key and stores it encrypted;
every GET response must carry `configured: bool` + audit metadata only —
never the plaintext value, not even to an admin. These tests assert that
contract directly against a real DB (not mocked), since "the value must
never appear in a response" is exactly the kind of property a mock could
accidentally make look true without it actually holding.
"""

import pytest

from app.core.services.integration_secrets import KNOWN_SERVICES
from app.database.models import EntegrasyonAyari
from app.database.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _reset_entegrasyon_rows(db_session):
    """set_integration_secret() commits through its own UnitOfWork, not the
    per-test db_session transaction — so it is NOT rolled back automatically
    between tests. mapbox/openroute/groq are fixed, globally-shared row
    identifiers (unlike most test fixtures' per-test-unique data), so a test
    here that configures "mapbox" would otherwise leak into every other test
    file that also touches MapboxClient/OpenRouteClient/GroqService for the
    rest of the pytest session. Reset before AND after to be resilient to
    whatever ran before this file too.

    db_session dependency (unused directly) is what actually triggers the
    session-scoped schema setup (Base.metadata.create_all) before this
    autouse fixture's own UnitOfWork() touches the table — without it,
    fixture ordering can run this before the schema exists."""
    from sqlalchemy import update

    async def _clear():
        async with UnitOfWork() as uow:
            await uow.session.execute(
                update(EntegrasyonAyari)
                .where(EntegrasyonAyari.servis_adi.in_(KNOWN_SERVICES))
                .values(
                    deger_sifreli=None, guncelleyen_id=None, guncellenme_tarihi=None
                )
            )
            await uow.commit()

    await _clear()
    yield
    await _clear()


@pytest.mark.asyncio
async def test_list_integrations_default_unconfigured(async_client, admin_auth_headers):
    """Fresh DB — every known service (incl. the 2 Telegram bot tokens)
    reports configured=false."""
    response = await async_client.get(
        "/api/v1/admin/integrations/", headers=admin_auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    names = {item["servis_adi"] for item in body}
    assert names == {
        "mapbox",
        "openroute",
        "groq",
        "telegram_driver_bot",
        "telegram_ops_bot",
    }
    assert all(item["configured"] is False for item in body)

    by_name = {item["servis_adi"]: item for item in body}
    # env_fallback_configured only applies to the 3 API-key services.
    for servis in ("mapbox", "openroute", "groq"):
        assert isinstance(by_name[servis]["env_fallback_configured"], bool)
    for servis in ("telegram_driver_bot", "telegram_ops_bot"):
        assert by_name[servis]["env_fallback_configured"] is None
    assert all(item["guncellenme_tarihi"] is None for item in body)


@pytest.mark.asyncio
async def test_update_key_then_status_never_leaks_value(
    async_client, admin_auth_headers
):
    """Set a real-looking key, then confirm the response (PUT AND any
    subsequent GET) never contains it anywhere — only configured/metadata."""
    secret_value = (
        "sk-super-secret-value-should-never-appear-anywhere"  # pragma: allowlist secret
    )

    put_resp = await async_client.put(
        "/api/v1/admin/integrations/mapbox",
        json={"api_key": secret_value},
        headers=admin_auth_headers,
    )
    assert put_resp.status_code == 200
    assert secret_value not in put_resp.text
    put_body = put_resp.json()
    assert put_body["servis_adi"] == "mapbox"
    assert put_body["configured"] is True
    assert put_body["guncellenme_tarihi"] is not None

    get_resp = await async_client.get(
        "/api/v1/admin/integrations/", headers=admin_auth_headers
    )
    assert secret_value not in get_resp.text
    mapbox_status = next(
        item for item in get_resp.json() if item["servis_adi"] == "mapbox"
    )
    assert mapbox_status["configured"] is True
    # No "value"/"api_key"/"deger" field of any kind in the response shape.
    assert set(mapbox_status.keys()) == {
        "servis_adi",
        "configured",
        "guncellenme_tarihi",
        "guncelleyen_id",
        "container_running",
        "container_health",
        "env_fallback_configured",
    }
    # mapbox isn't a bot service — container fields never populate for it.
    assert mapbox_status["container_running"] is None
    # env_fallback_configured is a bool for mapbox, never the secret itself.
    assert isinstance(mapbox_status["env_fallback_configured"], bool)
    assert mapbox_status["container_health"] is None


@pytest.mark.asyncio
async def test_update_telegram_bot_token_through_same_generic_endpoint(
    async_client, admin_auth_headers
):
    """No dedicated endpoint for bot tokens — same PUT/GET contract as
    mapbox/openroute/groq, including the never-leaks-the-value property."""
    secret_value = "123456:AAF-fake-telegram-bot-token"  # pragma: allowlist secret

    put_resp = await async_client.put(
        "/api/v1/admin/integrations/telegram_driver_bot",
        json={"api_key": secret_value},
        headers=admin_auth_headers,
    )
    assert put_resp.status_code == 200
    assert secret_value not in put_resp.text
    assert put_resp.json()["configured"] is True

    get_resp = await async_client.get(
        "/api/v1/admin/integrations/", headers=admin_auth_headers
    )
    assert secret_value not in get_resp.text


@pytest.mark.asyncio
async def test_update_unknown_service_404(async_client, admin_auth_headers):
    response = await async_client.put(
        "/api/v1/admin/integrations/not_a_real_service",
        json={"api_key": "whatever"},  # pragma: allowlist secret
        headers=admin_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_requires_permission(async_client, normal_auth_headers):
    """A non-admin (no konfig_duzenle yetki) must be rejected — this is a
    write path for third-party API credentials, not a read-only listing."""
    response = await async_client.put(
        "/api/v1/admin/integrations/mapbox",
        json={"api_key": "whatever"},  # pragma: allowlist secret
        headers=normal_auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_requires_permission(async_client, normal_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/integrations/", headers=normal_auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_rejected(async_client):
    response = await async_client.get("/api/v1/admin/integrations/")
    assert response.status_code == 401
