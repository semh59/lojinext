"""Vehicle reactivate / delete / deactivate tests — real DB, no mocked UoW.

Previously these mocked the UnitOfWork and asserted on inner repo calls
(`mock_uow.arac_repo.update.assert_called_once()`), which verifies *that a method
was called* rather than *the business outcome*. That is the P0-class blind spot: a
contract bug inside the repo/service would still satisfy a call-count assertion.

Here the use-case functions run against the real test DB (db_session monkeypatches
AsyncSessionLocal, so their internal `UnitOfWork()` uses the test session) and we
assert the real persisted outcome (the row's aktif flag, its absence after a hard
delete, etc.).

Dalga 3 (B.1 free-function refactor): AracService class deleted — no
constructor-injected event_bus to mock (the @publishes decorator is
documented dead code, see v2/modules/fleet/events.py). test_service_exists /
test_basic_initialization removed — no class/constructor-injected repo left
to assert on.
"""

import pytest
from sqlalchemy import insert, select

from v2.modules.fleet.application.bulk_add_vehicles import bulk_add_vehicles
from v2.modules.fleet.application.create_vehicle import create_vehicle
from v2.modules.fleet.application.delete_vehicle import delete_vehicle
from v2.modules.fleet.application.list_vehicles import (
    get_all_vehicles_paged,
    get_vehicle_by_id,
)
from v2.modules.fleet.application.update_vehicle import update_vehicle
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.fleet.schemas import AracCreate

pytestmark = pytest.mark.integration


async def _seed_arac(db_session, plaka: str, *, aktif: bool = True) -> int:
    res = await db_session.execute(
        insert(Arac).values(plaka=plaka, marka="Mercedes", model="Actros", aktif=aktif)
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _get_arac(db_session, arac_id: int):
    return (
        await db_session.execute(select(Arac).where(Arac.id == arac_id))
    ).scalar_one_or_none()


class TestVehicleReactivate:
    async def test_create_arac_reactivates_passive_vehicle(self, db_session):
        """create_vehicle re-activates an existing passive vehicle instead of inserting."""
        plaka = "34 XYZ 999"
        seeded_id = await _seed_arac(db_session, plaka, aktif=False)

        data = AracCreate(
            plaka=plaka, marka="Mercedes", model="Actros", yil=2020, tank_kapasitesi=600
        )
        result = await create_vehicle(data)

        # Returns the existing id (no new insert)…
        assert result == seeded_id
        # …and the real row is now active — the business outcome, not a mock call.
        row = await _get_arac(db_session, seeded_id)
        assert row is not None and row.aktif is True

    async def test_create_arac_raises_for_existing_active_plate(self, db_session):
        """create_vehicle raises for a duplicate ACTIVE vehicle plate."""
        plaka = "34 ABC 1234"
        await _seed_arac(db_session, plaka, aktif=True)

        data = AracCreate(
            plaka=plaka, marka="Mercedes", model="Actros", yil=2020, tank_kapasitesi=600
        )
        with pytest.raises(ValueError, match="already exists"):
            await create_vehicle(data)

    async def test_delete_arac_active_vehicle_deactivates(self, db_session):
        """delete_vehicle on an active vehicle sets aktif=False (soft delete)."""
        arac_id = await _seed_arac(db_session, "34 ABC 100", aktif=True)

        result = await delete_vehicle(arac_id)

        assert result is True
        row = await _get_arac(db_session, arac_id)
        assert row is not None and row.aktif is False

    async def test_delete_arac_passive_vehicle_hard_deletes(self, db_session):
        """delete_vehicle on a passive vehicle performs a hard delete (row removed)."""
        arac_id = await _seed_arac(db_session, "34 DEF 200", aktif=False)

        result = await delete_vehicle(arac_id)

        assert result is True
        assert await _get_arac(db_session, arac_id) is None

    async def test_delete_arac_not_found_returns_false(self, db_session):
        """delete_vehicle returns False when the vehicle does not exist."""
        result = await delete_vehicle(999999)
        assert result is False

    async def test_get_all_paged_returns_dict(self, db_session):
        """get_all_vehicles_paged returns a dict with 'items' and 'total' against a real DB."""
        result = await get_all_vehicles_paged()
        assert "items" in result
        assert "total" in result

    async def test_bulk_add_arac_empty_list(self):
        """bulk_add_vehicles returns 0 when given an empty list (no UoW needed)."""
        result = await bulk_add_vehicles([])
        assert result == 0

    async def test_edge_case_get_by_id_returns_none(self, db_session):
        """get_vehicle_by_id returns None for a non-existent arac_id."""
        result = await get_vehicle_by_id(999999)
        assert result is None

    async def test_update_arac_rejects_generic_patch_on_passive_vehicle(
        self, db_session
    ):
        """update_vehicle must NOT silently mutate a passive (soft-deleted) vehicle.

        2026-07-01 prod-grade denetimi bug: `_update_vehicle_impl` sadece `get_by_id`
        ile veriyi çekip `update()` çağırıyordu; get_by_id soft-delete filtresiz
        olduğu için pasif bir araç, create_vehicle'ın reaktivasyon akışını bypass
        ederek doğrudan PATCH ile sessizce güncellenebiliyordu.
        """
        from v2.modules.fleet.schemas import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 300", aktif=False)

        update = AracUpdate(marka="ChangedBrand")
        success = await update_vehicle(arac_id, update)

        assert success is False
        row = await _get_arac(db_session, arac_id)
        assert row.marka != "ChangedBrand"  # untouched — still the seeded value

    async def test_update_arac_allows_explicit_reactivation_of_passive_vehicle(
        self, db_session
    ):
        """An explicit `aktif=True` PATCH on a passive vehicle IS a legitimate
        reactivation and must still succeed."""
        from v2.modules.fleet.schemas import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 301", aktif=False)

        update = AracUpdate(aktif=True, marka="ReactivatedBrand")
        success = await update_vehicle(arac_id, update)

        assert success is True
        row = await _get_arac(db_session, arac_id)
        assert row.aktif is True
        assert row.marka == "ReactivatedBrand"

    async def test_update_arac_active_vehicle_unaffected(self, db_session):
        """Updating an active vehicle behaves exactly as before."""
        from v2.modules.fleet.schemas import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 302", aktif=True)

        update = AracUpdate(marka="StillActiveBrand")
        success = await update_vehicle(arac_id, update)

        assert success is True
        row = await _get_arac(db_session, arac_id)
        assert row.marka == "StillActiveBrand"
