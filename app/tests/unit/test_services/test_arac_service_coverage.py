"""
AracService coverage tests — targeting uncovered branches.
Uses mocked UnitOfWork; no live DB required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_uow(plaka_existing=None, arac_by_id=None):
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.session = MagicMock()
    mock_uow.session.add = MagicMock()
    mock_uow.session.flush = AsyncMock()

    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_plaka = AsyncMock(return_value=plaka_existing)
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac_by_id)
    mock_uow.arac_repo.update = AsyncMock(return_value=True)
    mock_uow.arac_repo.hard_delete = AsyncMock(return_value=True)
    mock_uow.arac_repo.hard_delete_all = AsyncMock(return_value=5)
    mock_uow.arac_repo.get_arac_with_stats = AsyncMock(return_value=None)
    mock_uow.arac_repo.get_all = AsyncMock(return_value=[])
    mock_uow.arac_repo.count_all = AsyncMock(return_value=0)
    mock_uow.arac_repo.get_aktif_plakalar = AsyncMock(return_value=[])
    # AUDIT-035: bulk_add_arac artık get_plaka_id_map ile TÜM plakaları (pasif dahil)
    # çekip reaktivasyon yapıyor.
    mock_uow.arac_repo.get_plaka_id_map = AsyncMock(return_value={})
    mock_uow.arac_repo.bulk_create = AsyncMock(return_value=[])

    # add() returns a mock with .id attribute
    fake_arac = MagicMock()
    fake_arac.id = 42
    mock_uow.arac_repo.add = AsyncMock(return_value=fake_arac)

    return mock_uow


def _make_arac_create(**overrides):
    from app.core.entities.models import AracCreate

    defaults = dict(plaka="34TEST001", marka="VOLVO", model="FH16", yil=2022)
    defaults.update(overrides)
    return AracCreate(**defaults)


def _make_arac_update(**overrides):
    from app.core.entities.models import AracUpdate

    return AracUpdate(**overrides)


def _make_service():
    from app.core.services.arac_service import AracService

    return AracService(repo=MagicMock(), event_bus=MagicMock())


# ---------------------------------------------------------------------------
# create_arac
# ---------------------------------------------------------------------------


class TestCreateArac:
    async def test_create_new_vehicle_returns_id(self):
        mock_uow = _make_mock_uow()
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.create_arac(_make_arac_create())

        assert result == 42

    async def test_create_raises_when_plaka_already_active(self):
        active_vehicle = {"id": 1, "plaka": "34TEST001", "aktif": True}
        mock_uow = _make_mock_uow(plaka_existing=active_vehicle)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="already exists"):
                await svc.create_arac(_make_arac_create())

    async def test_create_reactivates_passive_vehicle(self):
        passive_vehicle = {"id": 7, "plaka": "34TEST001", "aktif": False}
        mock_uow = _make_mock_uow(plaka_existing=passive_vehicle)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.create_arac(_make_arac_create())

        assert result == 7
        mock_uow.arac_repo.update.assert_called_once()

    async def test_create_with_explicit_uow(self):
        mock_uow = _make_mock_uow()
        svc = _make_service()

        # Pass explicit UoW — should use it directly without creating a new one
        result = await svc.create_arac(_make_arac_create(), uow=mock_uow)

        assert result == 42


# ---------------------------------------------------------------------------
# update_arac
# ---------------------------------------------------------------------------


class TestUpdateArac:
    async def test_update_returns_false_for_empty_update(self):
        mock_uow = _make_mock_uow(
            arac_by_id={"id": 1, "plaka": "34TEST001", "aktif": True}
        )
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.update_arac(1, _make_arac_update())

        assert result is False

    async def test_update_raises_when_plaka_belongs_to_another(self):
        other_vehicle = {"id": 99, "plaka": "06 XYZ 789"}
        mock_uow = _make_mock_uow(plaka_existing=other_vehicle)
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value={"id": 1, "aktif": True})
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="another vehicle"):
                await svc.update_arac(1, _make_arac_update(plaka="06 XYZ 789"))

    async def test_update_success_without_status_change(self):
        current = {"id": 1, "plaka": "34TEST001", "aktif": True}
        mock_uow = _make_mock_uow(arac_by_id=current)
        mock_uow.arac_repo.update = AsyncMock(return_value=True)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.update_arac(1, _make_arac_update(notlar="Updated note"))

        assert result is True

    async def test_update_logs_status_change(self):
        current = {"id": 1, "plaka": "34TEST001", "aktif": True}
        mock_uow = _make_mock_uow(arac_by_id=current)
        mock_uow.arac_repo.update = AsyncMock(return_value=True)
        svc = _make_service()

        with (
            patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow),
            patch.object(svc, "_log_vehicle_event", new_callable=AsyncMock) as mock_log,
        ):
            await svc.update_arac(1, _make_arac_update(aktif=False))

        mock_log.assert_called_once()

    async def test_update_with_explicit_uow(self):
        current = {"id": 1, "plaka": "34TEST001", "aktif": True}
        mock_uow = _make_mock_uow(arac_by_id=current)
        mock_uow.arac_repo.update = AsyncMock(return_value=True)
        svc = _make_service()

        result = await svc.update_arac(
            1, _make_arac_update(notlar="via uow"), uow=mock_uow
        )

        assert result is True


# ---------------------------------------------------------------------------
# delete_arac
# ---------------------------------------------------------------------------


class TestDeleteArac:
    async def test_delete_returns_false_when_not_found(self):
        mock_uow = _make_mock_uow(arac_by_id=None)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_arac(999)

        assert result is False

    async def test_delete_active_vehicle_sets_passive(self):
        active = {"id": 1, "plaka": "34TEST001", "aktif": True}
        mock_uow = _make_mock_uow(arac_by_id=active)
        mock_uow.arac_repo.update = AsyncMock(return_value=True)
        svc = _make_service()

        with (
            patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow),
            patch.object(svc, "_log_vehicle_event", new_callable=AsyncMock),
        ):
            result = await svc.delete_arac(1)

        assert result is True
        mock_uow.arac_repo.update.assert_called_once_with(1, aktif=False)

    async def test_delete_passive_vehicle_hard_deletes(self):
        passive = {"id": 1, "plaka": "34TEST001", "aktif": False}
        mock_uow = _make_mock_uow(arac_by_id=passive)
        mock_uow.arac_repo.hard_delete = AsyncMock(return_value=True)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_arac(1)

        assert result is True
        mock_uow.arac_repo.hard_delete.assert_called_once_with(1)

    async def test_delete_passive_raises_on_dependent_data(self):
        passive = {"id": 1, "plaka": "34TEST001", "aktif": False}
        mock_uow = _make_mock_uow(arac_by_id=passive)
        mock_uow.arac_repo.hard_delete = AsyncMock(
            side_effect=Exception("FK violation")
        )
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="cannot be permanently deleted"):
                await svc.delete_arac(1)


# ---------------------------------------------------------------------------
# delete_all_vehicles
# ---------------------------------------------------------------------------


class TestDeleteAllVehicles:
    async def test_delete_all_returns_count(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.hard_delete_all = AsyncMock(return_value=3)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_all_vehicles()

        assert result == 3

    async def test_delete_all_raises_on_error(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.hard_delete_all = AsyncMock(
            side_effect=Exception("FK error")
        )
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="dependencies"):
                await svc.delete_all_vehicles()


# ---------------------------------------------------------------------------
# get_all_paged / get_all_vehicles
# ---------------------------------------------------------------------------


class TestGetAllPaged:
    async def test_returns_dict_with_items_and_total(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(return_value=[])
        mock_uow.arac_repo.count_all = AsyncMock(return_value=0)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        assert "items" in result
        assert "total" in result

    async def test_skips_invalid_vehicle_records(self):
        mock_uow = _make_mock_uow()
        # Return a dict that can't be validated as AracEntity (missing required fields)
        mock_uow.arac_repo.get_all = AsyncMock(return_value=[{"id": 1}])
        mock_uow.arac_repo.count_all = AsyncMock(return_value=1)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        # Invalid records are skipped
        assert result["total"] == 1
        assert isinstance(result["items"], list)

    async def test_get_all_vehicles_delegates_to_paged(self):
        mock_uow = _make_mock_uow()
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_vehicles()

        assert isinstance(result, list)

    async def test_get_all_paged_with_filters(self):
        mock_uow = _make_mock_uow()
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged(
                marka="VOLVO", model="FH16", min_yil=2020, max_yil=2024
            )

        assert "items" in result
        call_kwargs = mock_uow.arac_repo.get_all.call_args[1]
        assert call_kwargs["filters"]["marka"] == "VOLVO"


# ---------------------------------------------------------------------------
# get_vehicle_stats / get_by_id
# ---------------------------------------------------------------------------


class TestGetVehicleStats:
    async def test_returns_none_when_not_found(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_arac_with_stats = AsyncMock(return_value=None)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_vehicle_stats(9999)

        assert result is None

    async def test_get_by_id_returns_none_when_missing(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_by_id(9999)

        assert result is None


# ---------------------------------------------------------------------------
# bulk_add_arac
# ---------------------------------------------------------------------------


class TestBulkAddArac:
    async def test_empty_list_returns_zero(self):
        svc = _make_service()
        result = await svc.bulk_add_arac([])
        assert result == 0

    async def test_skips_existing_plates(self):
        mock_uow = _make_mock_uow()
        # AUDIT-035: mevcut plaka get_plaka_id_map'te → yeni eklenmez (reaktive edilir).
        mock_uow.arac_repo.get_plaka_id_map = AsyncMock(return_value={"34TEST001": 5})
        svc = _make_service()

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.bulk_add_arac([_make_arac_create(plaka="34TEST001")])

        assert result == 0

    async def test_adds_new_vehicles(self):
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_aktif_plakalar = AsyncMock(return_value=[])
        mock_uow.arac_repo.bulk_create = AsyncMock(return_value=[101, 102])
        svc = _make_service()

        with (
            patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow),
            patch.object(svc, "_log_vehicle_event", new_callable=AsyncMock),
        ):
            result = await svc.bulk_add_arac(
                [
                    _make_arac_create(plaka="34NEW001"),
                    _make_arac_create(plaka="34NEW002"),
                ]
            )

        assert result == 2
