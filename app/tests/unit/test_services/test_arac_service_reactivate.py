"""AracService reactivate / delete / deactivate tests — real DB, no mocked UoW.

Previously these mocked the UnitOfWork and asserted on inner repo calls
(`mock_uow.arac_repo.update.assert_called_once()`), which verifies *that a method
was called* rather than *the business outcome*. That is the P0-class blind spot: a
contract bug inside the repo/service would still satisfy a call-count assertion.

Here the service runs against the real test DB (db_session monkeypatches
AsyncSessionLocal, so AracService's internal `UnitOfWork()` uses the test session)
and we assert the real persisted outcome (the row's aktif flag, its absence after a
hard delete, etc.). Only the event bus stays a MagicMock — it is external infra.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import insert, select

from app.core.entities.models import AracCreate
from app.core.services.arac_service import AracService
from app.database.models import Arac

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


def _service() -> AracService:
    # event_bus is external infra → MagicMock is legitimate; the UoW/DB is real.
    return AracService(event_bus=MagicMock())


class TestAracServiceReactivate:
    def test_service_exists(self):
        """AracService class is importable."""
        assert AracService is not None

    async def test_basic_initialization(self):
        """AracService wires the injected repo and event_bus (DI contract)."""
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = AracService(repo=mock_repo, event_bus=mock_eb)
        assert svc.repo is mock_repo
        assert svc.event_bus is mock_eb

    async def test_create_arac_reactivates_passive_vehicle(self, db_session):
        """create_arac re-activates an existing passive vehicle instead of inserting."""
        plaka = "34 XYZ 999"
        seeded_id = await _seed_arac(db_session, plaka, aktif=False)

        data = AracCreate(
            plaka=plaka, marka="Mercedes", model="Actros", yil=2020, tank_kapasitesi=600
        )
        result = await _service().create_arac(data)

        # Returns the existing id (no new insert)…
        assert result == seeded_id
        # …and the real row is now active — the business outcome, not a mock call.
        row = await _get_arac(db_session, seeded_id)
        assert row is not None and row.aktif is True

    async def test_create_arac_raises_for_existing_active_plate(self, db_session):
        """create_arac raises for a duplicate ACTIVE vehicle plate."""
        plaka = "34 ABC 1234"
        await _seed_arac(db_session, plaka, aktif=True)

        data = AracCreate(
            plaka=plaka, marka="Mercedes", model="Actros", yil=2020, tank_kapasitesi=600
        )
        with pytest.raises(ValueError, match="already exists"):
            await _service().create_arac(data)

    async def test_delete_arac_active_vehicle_deactivates(self, db_session):
        """delete_arac on an active vehicle sets aktif=False (soft delete)."""
        arac_id = await _seed_arac(db_session, "34 ABC 100", aktif=True)

        result = await _service().delete_arac(arac_id)

        assert result is True
        row = await _get_arac(db_session, arac_id)
        assert row is not None and row.aktif is False

    async def test_delete_arac_passive_vehicle_hard_deletes(self, db_session):
        """delete_arac on a passive vehicle performs a hard delete (row removed)."""
        arac_id = await _seed_arac(db_session, "34 DEF 200", aktif=False)

        result = await _service().delete_arac(arac_id)

        assert result is True
        assert await _get_arac(db_session, arac_id) is None

    async def test_delete_arac_not_found_returns_false(self, db_session):
        """delete_arac returns False when the vehicle does not exist."""
        result = await _service().delete_arac(999999)
        assert result is False

    async def test_get_all_paged_returns_dict(self, db_session):
        """get_all_paged returns a dict with 'items' and 'total' against a real DB."""
        result = await _service().get_all_paged()
        assert "items" in result
        assert "total" in result

    async def test_bulk_add_arac_empty_list(self):
        """bulk_add_arac returns 0 when given an empty list (no UoW needed)."""
        result = await _service().bulk_add_arac([])
        assert result == 0

    async def test_edge_case_get_by_id_returns_none(self, db_session):
        """get_by_id returns None for a non-existent arac_id."""
        result = await _service().get_by_id(999999)
        assert result is None

    async def test_update_arac_rejects_generic_patch_on_passive_vehicle(
        self, db_session
    ):
        """update_arac must NOT silently mutate a passive (soft-deleted) vehicle.

        2026-07-01 prod-grade denetimi bug: `_update_arac_impl` sadece `get_by_id`
        ile veriyi çekip `update()` çağırıyordu; get_by_id soft-delete filtresiz
        olduğu için pasif bir araç, create_arac'ın reaktivasyon akışını bypass
        ederek doğrudan PATCH ile sessizce güncellenebiliyordu.
        """
        from app.core.entities.models import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 300", aktif=False)

        update = AracUpdate(marka="ChangedBrand")
        success = await _service().update_arac(arac_id, update)

        assert success is False
        row = await _get_arac(db_session, arac_id)
        assert row.marka != "ChangedBrand"  # untouched — still the seeded value

    async def test_update_arac_allows_explicit_reactivation_of_passive_vehicle(
        self, db_session
    ):
        """An explicit `aktif=True` PATCH on a passive vehicle IS a legitimate
        reactivation and must still succeed."""
        from app.core.entities.models import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 301", aktif=False)

        update = AracUpdate(aktif=True, marka="ReactivatedBrand")
        success = await _service().update_arac(arac_id, update)

        assert success is True
        row = await _get_arac(db_session, arac_id)
        assert row.aktif is True
        assert row.marka == "ReactivatedBrand"

    async def test_update_arac_active_vehicle_unaffected(self, db_session):
        """Updating an active vehicle behaves exactly as before."""
        from app.core.entities.models import AracUpdate

        arac_id = await _seed_arac(db_session, "34 GHI 302", aktif=True)

        update = AracUpdate(marka="StillActiveBrand")
        success = await _service().update_arac(arac_id, update)

        assert success is True
        row = await _get_arac(db_session, arac_id)
        assert row.marka == "StillActiveBrand"
