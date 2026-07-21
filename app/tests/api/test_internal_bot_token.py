"""GET /internal/bot-token/{servis_adi} — Telegram bot token bootstrap.

Real DB (not mocked): the property under test — this endpoint serves the
plaintext ONLY for telegram_driver_bot/telegram_ops_bot, never for
mapbox/openroute/groq even though they share the same entegrasyon_ayarlari
table — is exactly the kind of security boundary a mock could make look
true without it actually holding.
"""

import pytest
from sqlalchemy import update

from app.config import settings
from app.database.models import EntegrasyonAyari
from app.database.unit_of_work import UnitOfWork
from v2.modules.admin_platform.application.integration_secrets import (
    KNOWN_SERVICES,
    set_integration_secret,
)

pytestmark = pytest.mark.integration

BASE = "/api/v1/internal/bot-token"

# Real _require_internal_token dependency is exercised as-is (not mocked
# away) — same shared-secret header the real bot containers send.
_AUTH_HEADERS = (
    {"X-Internal-Token": settings.INTERNAL_API_SECRET}
    if settings.INTERNAL_API_SECRET
    else {}
)


@pytest.fixture(autouse=True)
async def _reset_entegrasyon_rows(db_session):
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
async def test_returns_token_when_configured(async_client):
    await set_integration_secret(
        "telegram_driver_bot", "123456:AAF-real-token-value", user_id=0
    )
    resp = await async_client.get(f"{BASE}/telegram_driver_bot", headers=_AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {"token": "123456:AAF-real-token-value"}


@pytest.mark.asyncio
async def test_404_when_not_configured(async_client):
    resp = await async_client.get(f"{BASE}/telegram_ops_bot", headers=_AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_404_for_non_bot_service_even_if_configured(async_client):
    """mapbox/openroute/groq must NEVER be servable through this endpoint,
    even though they live in the same table and are otherwise configured."""
    await set_integration_secret("mapbox", "should-never-leak-here", user_id=0)
    resp = await async_client.get(f"{BASE}/mapbox", headers=_AUTH_HEADERS)
    assert resp.status_code == 404
    assert "should-never-leak-here" not in resp.text


@pytest.mark.asyncio
async def test_404_for_unknown_service_name(async_client):
    resp = await async_client.get(f"{BASE}/not-a-real-service", headers=_AUTH_HEADERS)
    assert resp.status_code == 404
