"""integration_secrets.py — multi-tenant API key management (2026-07-10).

Real DB (not mocked): the property under test — ciphertext in, plaintext
only ever recoverable through get_integration_secret(), never through
get_integration_statuses() — is exactly the kind of thing a mock could
make look true without it actually holding.
"""

import pytest
from sqlalchemy import select, update

from v2.modules.admin_platform.application.integration_secrets import (
    KNOWN_SERVICES,
    get_integration_secret,
    get_integration_statuses,
    set_integration_secret,
)
from v2.modules.admin_platform.public import EntegrasyonAyari
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
async def _reset_rows(db_session):
    # db_session dependency (unused directly) is what actually triggers the
    # session-scoped schema setup (Base.metadata.create_all) — without it,
    # UnitOfWork() below hits a DB with no tables yet.
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


async def test_get_secret_falls_back_to_env_when_unconfigured():
    value = await get_integration_secret("mapbox", "env-fallback-value")
    assert value == "env-fallback-value"


async def test_get_secret_falls_back_to_none_when_no_fallback_given():
    assert await get_integration_secret("mapbox", None) is None


async def test_set_then_get_returns_db_value_not_env_fallback():
    await set_integration_secret("groq", "gsk-real-key-123", user_id=0)
    value = await get_integration_secret("groq", "should-not-be-returned")
    assert value == "gsk-real-key-123"


async def test_set_unknown_service_raises_value_error():
    with pytest.raises(ValueError, match="Bilinmeyen"):
        await set_integration_secret("not-a-real-service", "x", user_id=0)


async def test_set_stores_ciphertext_not_plaintext_in_db():
    """The DB row itself must never carry the plaintext — this is the
    property that makes 'nobody can read it back' actually true, not just
    a property of the read-path API."""
    await set_integration_secret("openroute", "super-secret-plaintext", user_id=0)
    async with UnitOfWork() as uow:
        row = await uow.session.scalar(
            select(EntegrasyonAyari).where(EntegrasyonAyari.servis_adi == "openroute")
        )
    assert row is not None
    assert row.deger_sifreli is not None
    assert "super-secret-plaintext" not in row.deger_sifreli


async def test_synthetic_superadmin_id_stored_as_null_not_zero():
    """Super-admin's synthetic id (<=0) has no row in kullanicilar — storing
    it verbatim would violate the guncelleyen_id FK (mirrors the same
    admin_audit_log convention documented in CLAUDE.md)."""
    await set_integration_secret("mapbox", "x", user_id=0)
    async with UnitOfWork() as uow:
        row = await uow.session.scalar(
            select(EntegrasyonAyari).where(EntegrasyonAyari.servis_adi == "mapbox")
        )
    assert row is not None
    assert row.guncelleyen_id is None


async def test_statuses_never_expose_the_value():
    await set_integration_secret("mapbox", "top-secret-value", user_id=0)
    statuses = await get_integration_statuses()
    mapbox = next(s for s in statuses if s["servis_adi"] == "mapbox")
    assert mapbox["configured"] is True
    assert "top-secret-value" not in str(mapbox)
    assert set(mapbox.keys()) == {
        "servis_adi",
        "configured",
        "guncellenme_tarihi",
        "guncelleyen_id",
    }


async def test_statuses_cover_all_known_services_even_with_no_rows():
    statuses = await get_integration_statuses()
    assert {s["servis_adi"] for s in statuses} == set(KNOWN_SERVICES)
    assert all(s["configured"] is False for s in statuses)
