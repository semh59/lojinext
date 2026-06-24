"""AracService coverage tests — real DB, no mocked UnitOfWork.

Previously these patched UnitOfWork with an AsyncMock and asserted on inner repo
calls (`arac_repo.update.assert_called_once_with(...)`, mock return values). That
verifies *that a repo method was called*, not the persisted business outcome —
the P0-class blind spot. Here the service runs against the real test DB
(db_session monkeypatches AsyncSessionLocal, so AracService's internal
`UnitOfWork()` uses the test session) and we assert the real rows (created /
reactivated / soft- or hard-deleted / filtered). Only the event bus stays a
MagicMock — it is external infra.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import insert, select

from app.core.entities.models import AracCreate, AracUpdate
from app.core.services.arac_service import AracService
from app.database.models import Arac
from app.database.unit_of_work import UnitOfWork
from app.tests._helpers.seed import seed_sefer, seed_sofor

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service() -> AracService:
    # event_bus is external infra → MagicMock is legitimate; the UoW/DB is real.
    return AracService(event_bus=MagicMock())


def _arac_create(**overrides):
    defaults = dict(plaka="34 TEST 001", marka="VOLVO", model="FH16", yil=2022)
    defaults.update(overrides)
    return AracCreate(**defaults)


def _arac_update(**overrides):
    return AracUpdate(**overrides)


async def _seed_arac(
    db_session, plaka: str, *, aktif: bool = True, marka: str = "Mercedes"
) -> int:
    res = await db_session.execute(
        insert(Arac).values(plaka=plaka, marka=marka, model="Actros", aktif=aktif)
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _get_arac(db_session, arac_id: int):
    row = (
        await db_session.execute(select(Arac).where(Arac.id == arac_id))
    ).scalar_one_or_none()
    if row is not None:
        await db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# create_arac
# ---------------------------------------------------------------------------


class TestCreateArac:
    async def test_create_new_vehicle_returns_id(self, db_session):
        result = await _service().create_arac(_arac_create(plaka="34 NEW 001"))
        assert isinstance(result, int)
        row = await _get_arac(db_session, result)
        assert row is not None and row.plaka == "34 NEW 001" and row.aktif is True

    async def test_create_raises_when_plaka_already_active(self, db_session):
        await _seed_arac(db_session, "34 TEST 001", aktif=True)
        with pytest.raises(ValueError, match="already exists"):
            await _service().create_arac(_arac_create(plaka="34 TEST 001"))

    async def test_create_reactivates_passive_vehicle(self, db_session):
        seeded = await _seed_arac(db_session, "34 TEST 001", aktif=False)
        result = await _service().create_arac(_arac_create(plaka="34 TEST 001"))
        assert result == seeded  # existing id reused, no new insert
        row = await _get_arac(db_session, seeded)
        assert row.aktif is True

    async def test_create_with_explicit_uow(self, db_session):
        async with UnitOfWork() as uow:
            result = await _service().create_arac(
                _arac_create(plaka="34 UOW 001"), uow=uow
            )
        assert isinstance(result, int)
        assert (await _get_arac(db_session, result)) is not None


# ---------------------------------------------------------------------------
# update_arac
# ---------------------------------------------------------------------------


class TestUpdateArac:
    async def test_update_returns_false_for_empty_update(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001")
        result = await _service().update_arac(aid, _arac_update())
        assert result is False

    async def test_update_raises_when_plaka_belongs_to_another(self, db_session):
        await _seed_arac(db_session, "06 XYZ 789")
        aid = await _seed_arac(db_session, "34 TEST 001")
        with pytest.raises(ValueError, match="another vehicle"):
            await _service().update_arac(aid, _arac_update(plaka="06 XYZ 789"))

    async def test_update_success_without_status_change(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001")
        result = await _service().update_arac(aid, _arac_update(notlar="Updated note"))
        assert result is True
        row = await _get_arac(db_session, aid)
        assert row.notlar == "Updated note"

    async def test_update_status_change_persists(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001", aktif=True)
        result = await _service().update_arac(aid, _arac_update(aktif=False))
        assert result is True
        row = await _get_arac(db_session, aid)
        assert row.aktif is False  # status change is the real outcome

    async def test_update_with_explicit_uow(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001")
        async with UnitOfWork() as uow:
            result = await _service().update_arac(
                aid, _arac_update(notlar="via uow"), uow=uow
            )
        assert result is True
        assert (await _get_arac(db_session, aid)).notlar == "via uow"


# ---------------------------------------------------------------------------
# delete_arac
# ---------------------------------------------------------------------------


class TestDeleteArac:
    async def test_delete_returns_false_when_not_found(self, db_session):
        assert await _service().delete_arac(999999) is False

    async def test_delete_active_vehicle_sets_passive(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001", aktif=True)
        result = await _service().delete_arac(aid)
        assert result is True
        row = await _get_arac(db_session, aid)
        assert row is not None and row.aktif is False  # soft delete

    async def test_delete_passive_vehicle_hard_deletes(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001", aktif=False)
        result = await _service().delete_arac(aid)
        assert result is True
        assert await _get_arac(db_session, aid) is None  # row removed

    async def test_delete_passive_raises_on_dependent_data(self, db_session):
        """Hard-deleting a passive vehicle with a dependent trip → ValueError (real FK)."""
        aid = await _seed_arac(db_session, "34 TEST 001", aktif=False)
        sofor = await seed_sofor(db_session, ad_soyad="Dep Sofor")
        await seed_sefer(db_session, arac_id=aid, sofor_id=sofor.id)
        await db_session.commit()
        with pytest.raises(ValueError, match="cannot be permanently deleted"):
            await _service().delete_arac(aid)


# ---------------------------------------------------------------------------
# delete_all_vehicles
# ---------------------------------------------------------------------------


class TestDeleteAllVehicles:
    async def test_delete_all_returns_count(self, db_session):
        await _seed_arac(db_session, "34 AAA 001")
        await _seed_arac(db_session, "34 AAA 002")
        await _seed_arac(db_session, "34 AAA 003")
        result = await _service().delete_all_vehicles()
        assert result == 3
        rows = (await db_session.execute(select(Arac))).scalars().all()
        assert rows == []

    async def test_delete_all_raises_on_dependencies(self, db_session):
        """A dependent trip blocks the bulk hard delete → ValueError (real FK)."""
        aid = await _seed_arac(db_session, "34 AAA 001")
        sofor = await seed_sofor(db_session, ad_soyad="Dep Sofor")
        await seed_sefer(db_session, arac_id=aid, sofor_id=sofor.id)
        await db_session.commit()
        with pytest.raises(ValueError, match="dependencies"):
            await _service().delete_all_vehicles()


# ---------------------------------------------------------------------------
# get_all_paged / get_all_vehicles
# ---------------------------------------------------------------------------


class TestGetAllPaged:
    async def test_returns_dict_with_items_and_total(self, db_session):
        await _seed_arac(db_session, "34 TEST 001", marka="VOLVO")
        result = await _service().get_all_paged()
        assert "items" in result and "total" in result
        assert result["total"] >= 1
        assert any(i.plaka == "34 TEST 001" for i in result["items"])

    async def test_get_all_vehicles_delegates_to_paged(self, db_session):
        await _seed_arac(db_session, "34 TEST 001")
        result = await _service().get_all_vehicles()
        assert isinstance(result, list)
        assert len(result) >= 1

    async def test_get_all_paged_with_marka_filter(self, db_session):
        await _seed_arac(db_session, "34 VOL 001", marka="VOLVO")
        await _seed_arac(db_session, "34 MER 001", marka="Mercedes")
        result = await _service().get_all_paged(marka="VOLVO")
        plakalar = {i.plaka for i in result["items"]}
        assert "34 VOL 001" in plakalar
        assert "34 MER 001" not in plakalar


# ---------------------------------------------------------------------------
# get_vehicle_stats / get_by_id
# ---------------------------------------------------------------------------


class TestGetVehicleStats:
    async def test_returns_none_when_not_found(self, db_session):
        assert await _service().get_vehicle_stats(9999) is None

    async def test_get_by_id_returns_none_when_missing(self, db_session):
        assert await _service().get_by_id(9999) is None

    async def test_get_by_id_returns_seeded_vehicle(self, db_session):
        aid = await _seed_arac(db_session, "34 TEST 001")
        result = await _service().get_by_id(aid)
        assert result is not None


# ---------------------------------------------------------------------------
# bulk_add_arac
# ---------------------------------------------------------------------------


class TestBulkAddArac:
    async def test_empty_list_returns_zero(self):
        assert await _service().bulk_add_arac([]) == 0

    async def test_skips_existing_plates(self, db_session):
        await _seed_arac(db_session, "34 TEST 001", aktif=True)
        result = await _service().bulk_add_arac([_arac_create(plaka="34 TEST 001")])
        # Plate already present → not inserted again.
        assert result == 0

    async def test_adds_new_vehicles(self, db_session):
        result = await _service().bulk_add_arac(
            [_arac_create(plaka="34 NEW 001"), _arac_create(plaka="34 NEW 002")]
        )
        assert result == 2
        rows = (await db_session.execute(select(Arac))).scalars().all()
        assert {r.plaka for r in rows} == {"34 NEW 001", "34 NEW 002"}
