"""Real-DB regression tests: create/update/delete use-cases in
location/fleet/fuel/driver now write to the transactional outbox
(``outbox_events``) instead of only carrying the previously-dead
``@publishes(EventType.X)`` decorator (dedektif denetimi, 2026-07-16 —
see TASKS/STATUS.md "Event-bus wiring").

No mocked UoW/session — each use-case opens its own real ``UnitOfWork``
against the test DB (``db_session`` fixture monkeypatches
``AsyncSessionLocal``), matching the existing outbox test convention in
``test_outbox_service_coverage.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.tests._helpers.seed import seed_arac, seed_lokasyon, seed_sofor
from v2.modules.driver.application.add_sofor import add_sofor
from v2.modules.driver.application.delete_sofor import delete_sofor
from v2.modules.driver.application.update_sofor import update_sofor
from v2.modules.fleet.application.create_vehicle import create_vehicle
from v2.modules.fleet.application.delete_vehicle import delete_vehicle
from v2.modules.fleet.application.update_vehicle import update_vehicle
from v2.modules.fleet.schemas import AracCreate, AracUpdate
from v2.modules.fuel.application.add_yakit import add_yakit
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.update_yakit import update_yakit
from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.update_location import update_location
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonCreate, LokasyonUpdate
from v2.modules.shared_kernel.infrastructure.outbox import OutboxEvent

pytestmark = pytest.mark.integration


async def _last_outbox(db_session, event_type: str) -> OutboxEvent:
    row = (
        (
            await db_session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.event_type == event_type)
                .order_by(OutboxEvent.id.desc())
            )
        )
        .scalars()
        .first()
    )
    assert row is not None, f"no outbox row for {event_type}"
    return row


class TestFleetOutboxWiring:
    async def test_create_vehicle_writes_arac_added(self, db_session):
        vehicle_id = await create_vehicle(AracCreate(plaka="34EVT001", marka="MAN"))

        row = await _last_outbox(db_session, "arac_added")
        assert row.payload == {"result": vehicle_id}

    async def test_update_vehicle_writes_arac_updated(self, db_session):
        arac = await seed_arac(db_session, plaka="34EVT002")
        await db_session.commit()

        ok = await update_vehicle(arac.id, AracUpdate(marka="Volvo"))

        assert ok is True
        row = await _last_outbox(db_session, "arac_updated")
        assert row.payload == {"result": arac.id}

    async def test_delete_vehicle_writes_arac_deleted(self, db_session):
        arac = await seed_arac(db_session, plaka="34EVT003")
        await db_session.commit()

        ok = await delete_vehicle(arac.id)

        assert ok is True
        row = await _last_outbox(db_session, "arac_deleted")
        assert row.payload == {"result": arac.id}


class TestFuelOutboxWiring:
    async def test_add_yakit_writes_yakit_added(self, db_session):
        from datetime import date

        from v2.modules.fuel.domain.entities import YakitAlimiCreate

        arac = await seed_arac(db_session, plaka="34EVT004")
        await db_session.commit()

        yakit_id = await add_yakit(
            YakitAlimiCreate(
                tarih=date(2026, 6, 1),
                arac_id=arac.id,
                fiyat_tl="45.50",
                litre=200.0,
                km_sayac=100,
                depo_durumu="Doldu",
            )
        )

        row = await _last_outbox(db_session, "yakit_added")
        assert row.payload == {"result": yakit_id, "arac_id": arac.id}

    async def test_update_yakit_writes_yakit_updated(self, db_session):
        from app.tests._helpers.seed import seed_yakit
        from v2.modules.fuel.schemas import YakitUpdate

        arac = await seed_arac(db_session, plaka="34EVT005")
        yakit = await seed_yakit(db_session, arac_id=arac.id, km_sayac=100, litre=50.0)
        await db_session.commit()

        ok = await update_yakit(yakit.id, YakitUpdate(istasyon="Shell"))

        assert ok is True
        row = await _last_outbox(db_session, "yakit_updated")
        assert row.payload == {"result": yakit.id, "arac_id": arac.id}

    async def test_delete_yakit_writes_yakit_deleted(self, db_session):
        from app.tests._helpers.seed import seed_yakit

        arac = await seed_arac(db_session, plaka="34EVT006")
        yakit = await seed_yakit(db_session, arac_id=arac.id, km_sayac=100, litre=50.0)
        await db_session.commit()

        ok = await delete_yakit(yakit.id)

        assert ok is True
        row = await _last_outbox(db_session, "yakit_deleted")
        assert row.payload == {"result": yakit.id, "arac_id": arac.id}


class TestDriverOutboxWiring:
    async def test_add_sofor_writes_sofor_added(self, db_session):
        sofor_id = await add_sofor(ad_soyad="Event Test Sofor")

        row = await _last_outbox(db_session, "sofor_added")
        assert row.payload == {"result": sofor_id}

    async def test_update_sofor_writes_sofor_updated(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Update Test Sofor")
        await db_session.commit()

        ok = await update_sofor(sofor.id, notlar="updated")

        assert ok is True
        row = await _last_outbox(db_session, "sofor_updated")
        assert row.payload == {"result": sofor.id}

    async def test_delete_sofor_writes_sofor_deleted(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="Delete Test Sofor")
        await db_session.commit()

        ok = await delete_sofor(sofor.id)

        assert ok is True
        row = await _last_outbox(db_session, "sofor_deleted")
        assert row.payload == {"result": sofor.id}


class TestLocationOutboxWiring:
    async def test_create_location_writes_lokasyon_added(self, db_session):
        repo = LokasyonRepository(db_session)

        lokasyon_id = await create_location(
            repo,
            LokasyonCreate(
                cikis_yeri="Izmir Event", varis_yeri="Bursa Event", mesafe_km=300.0
            ),
        )

        row = await _last_outbox(db_session, "lokasyon_added")
        assert row.payload == {"result": lokasyon_id}

    async def test_update_location_writes_lokasyon_updated(self, db_session):
        lok = await seed_lokasyon(
            db_session, cikis_yeri="Update Event A", varis_yeri="Update Event B"
        )
        await db_session.commit()
        repo = LokasyonRepository(db_session)

        ok = await update_location(repo, lok.id, LokasyonUpdate(mesafe_km=500.0))

        assert ok is True
        row = await _last_outbox(db_session, "lokasyon_updated")
        assert row.payload == {"result": lok.id}

    async def test_delete_location_writes_lokasyon_deleted(self, db_session):
        lok = await seed_lokasyon(
            db_session, cikis_yeri="Delete Event A", varis_yeri="Delete Event B"
        )
        await db_session.commit()
        repo = LokasyonRepository(db_session)

        ok = await delete_location(repo, lok.id)

        assert ok is True
        row = await _last_outbox(db_session, "lokasyon_deleted")
        assert row.payload == {"result": lok.id}


class TestRelayDispatchesRealHandlersWithoutCrashing:
    """Once relayed, the newly-wired subscribers (cache invalidation,
    model-training counter, RAG sync) must not raise on the payload shapes
    written above — a bad payload should degrade silently (per-handler
    try/except in EventBus.publish_async), never break the relay."""

    async def test_relay_processes_arac_added_with_real_subscribers(self, db_session):
        from v2.modules.platform_infra.cache.cache_invalidation import (
            setup_cache_invalidation,
        )
        from v2.modules.platform_infra.events.event_bus import get_event_bus
        from v2.modules.shared_kernel.infrastructure.outbox import OutboxService

        bus = get_event_bus()
        bus.reset_all_for_tests()
        setup_cache_invalidation()

        vehicle_id = await create_vehicle(AracCreate(plaka="34EVT100", marka="MAN"))
        assert vehicle_id

        count = await OutboxService().relay_pending_events()

        assert count >= 1
        row = await _last_outbox(db_session, "arac_added")
        assert row.processed is True
        bus.reset_all_for_tests()
