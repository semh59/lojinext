"""NotificationService N+1 guard — real DB, no mocked UoW/session.

Previously this mocked the UnitOfWork/repos and asserted that add_all received 5
*mock* notification objects — the real persistence was never exercised. Here the
service runs against the real test DB (seeded roles/users/rules), so we assert the
real bildirim_gecmisi rows it creates. The N+1 guarantee is preserved by spying on
the REAL get_by_rol_ids (wraps the real method, just counts calls) — not by mocking
it. Only the WebSocket manager (external delivery channel) is stubbed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import insert, select

from app.infrastructure.security.pii_encryption import blind_index
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.notification.public import BildirimGecmisi, BildirimKurali

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_kullanici_repo_has_get_by_rol_ids():
    """KullaniciRepository must expose a get_by_rol_ids bulk method."""
    from v2.modules.auth_rbac.infrastructure.kullanici_repository import (
        KullaniciRepository,
    )

    assert hasattr(KullaniciRepository, "get_by_rol_ids"), (
        "KullaniciRepository missing get_by_rol_ids method"
    )


async def _seed_role(db_session, ad: str) -> int:
    return (
        await db_session.execute(insert(Rol).values(ad=ad, yetkiler={}))
    ).inserted_primary_key[0]


async def _seed_user(db_session, email: str, rol_id: int) -> int:
    return (
        await db_session.execute(
            insert(Kullanici).values(
                email=email,
                email_bidx=blind_index(email),
                ad_soyad="N1 User",
                sifre_hash="x",
                rol_id=rol_id,
                aktif=True,
            )
        )
    ).inserted_primary_key[0]


async def _seed_rule(db_session, olay_tipi, rol_id, kanallar):
    await db_session.execute(
        insert(BildirimKurali).values(
            olay_tipi=olay_tipi, alici_rol_id=rol_id, kanallar=kanallar, aktif=True
        )
    )


async def test_notification_uses_bulk_query_not_per_rule(db_session):
    """handle_event fetches users with ONE bulk query and persists exactly the
    right notifications to the real DB (no N+1 per rule)."""
    import v2.modules.notification.application.handle_trip_events as ns_mod
    from app.infrastructure.events.event_bus import Event
    from app.infrastructure.events.event_types import EventType
    from v2.modules.auth_rbac.infrastructure.kullanici_repository import (
        KullaniciRepository,
    )

    event_type = EventType.SEFER_ADDED
    olay = event_type.value

    # 2 roles; rol1 has 2 users, rol2 has 1 user.
    rol1 = await _seed_role(db_session, "n1_rol_1")
    rol2 = await _seed_role(db_session, "n1_rol_2")
    await _seed_user(db_session, "n1a@test", rol1)
    await _seed_user(db_session, "n1b@test", rol1)
    await _seed_user(db_session, "n1c@test", rol2)
    # 3 rules for the same event: rol1/UI, rol2/UI, rol1/EMAIL.
    await _seed_rule(db_session, olay, rol1, ["UI"])
    await _seed_rule(db_session, olay, rol2, ["UI"])
    await _seed_rule(db_session, olay, rol1, ["EMAIL"])
    await db_session.commit()

    # Spy (not mock) the real bulk method: it really runs against the DB; we only
    # count calls to assert the N+1 pattern is avoided (one bulk fetch, not per-rule).
    orig = KullaniciRepository.get_by_rol_ids
    calls: list = []

    async def _spy(self, rol_ids):
        calls.append(rol_ids)
        return await orig(self, rol_ids)

    # WebSocket delivery is external infra → stub it (the DB write is what we verify).
    original_ws = ns_mod.notification_ws_manager
    ns_mod.notification_ws_manager = AsyncMock()
    try:
        with patch.object(KullaniciRepository, "get_by_rol_ids", _spy):
            await ns_mod.handle_event(Event(type=event_type, data={}))
    finally:
        ns_mod.notification_ws_manager = original_ws

    # N+1 guard: the bulk method was called exactly once (not once per rule).
    assert len(calls) == 1

    # Business outcome: real notifications persisted.
    # rol1 (2 users) × {UI rule, EMAIL rule} = 4  +  rol2 (1 user) × {UI rule} = 1  → 5
    rows = (await db_session.execute(select(BildirimGecmisi))).scalars().all()
    assert len(rows) == 5
    assert {r.olay_tipi for r in rows} == {olay}
    assert {r.kanal for r in rows} == {"UI", "EMAIL"}
