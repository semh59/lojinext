"""AracService reactivate / delete / deactivate unit tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_mock_uow(arac_dict=None):
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.session = MagicMock()
    mock_uow.session.add = MagicMock()
    mock_uow.session.flush = AsyncMock()

    mock_uow.arac_repo = MagicMock()
    default_arac = arac_dict or {"id": 1, "plaka": "34ABC123", "aktif": True}
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=default_arac)
    mock_uow.arac_repo.get_by_plaka = AsyncMock(return_value=None)
    mock_uow.arac_repo.add = AsyncMock(return_value=MagicMock(id=99))
    mock_uow.arac_repo.update = AsyncMock(return_value=True)
    mock_uow.arac_repo.hard_delete = AsyncMock(return_value=True)
    mock_uow.arac_repo.hard_delete_all = AsyncMock(return_value=5)
    mock_uow.arac_repo.get_all = AsyncMock(return_value=[])
    mock_uow.arac_repo.count_all = AsyncMock(return_value=0)
    mock_uow.arac_repo.get_arac_with_stats = AsyncMock(return_value=None)
    mock_uow.arac_repo.get_aktif_plakalar = AsyncMock(return_value=[])
    mock_uow.arac_repo.bulk_create = AsyncMock(return_value=[])
    return mock_uow


class TestAracServiceReactivate:
    def test_service_exists(self):
        """AracService class is importable."""
        from app.core.services.arac_service import AracService

        assert AracService is not None

    async def test_basic_initialization(self):
        """AracService initializes without a real DB."""
        from app.core.services.arac_service import AracService

        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = AracService(repo=mock_repo, event_bus=mock_eb)
        assert svc.repo is mock_repo
        assert svc.event_bus is mock_eb

    async def test_create_arac_reactivates_passive_vehicle(self):
        """create_arac re-activates an existing passive vehicle instead of inserting."""
        from app.core.entities.models import AracCreate
        from app.core.services.arac_service import AracService

        existing = {"id": 5, "plaka": "34 XYZ 999", "aktif": False}
        mock_uow = _make_mock_uow(arac_dict=existing)
        mock_uow.arac_repo.get_by_plaka = AsyncMock(return_value=existing)

        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()
        svc = AracService(repo=MagicMock(), event_bus=mock_eb)

        # Valid Turkish plate: 34 + 3 letters + 3 digits
        data = AracCreate(
            plaka="34 XYZ 999",
            marka="Mercedes",
            model="Actros",
            yil=2020,
            tank_kapasitesi=600,
        )

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.create_arac(data)

        assert result == 5
        mock_uow.arac_repo.update.assert_called_once()
        # Should set aktif=True
        call_kwargs = mock_uow.arac_repo.update.call_args
        assert call_kwargs[1].get("aktif") is True or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] is True
        )

    async def test_create_arac_raises_for_existing_active_plate(self):
        """create_arac raises ValueError for duplicate active vehicle plate."""
        from app.core.entities.models import AracCreate
        from app.core.services.arac_service import AracService

        existing = {"id": 3, "plaka": "34 ABC 1234", "aktif": True}
        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_plaka = AsyncMock(return_value=existing)

        mock_eb = MagicMock()
        svc = AracService(repo=MagicMock(), event_bus=mock_eb)

        # Use a valid Turkish plate format: 2 digits + 1-3 letters + 2-4 digits
        data = AracCreate(
            plaka="34 ABC 1234",
            marka="Mercedes",
            model="Actros",
            yil=2020,
            tank_kapasitesi=600,
        )

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="already exists"):
                await svc.create_arac(data)

    async def test_delete_arac_active_vehicle_deactivates(self):
        """delete_arac on an active vehicle sets aktif=False (soft delete)."""
        from app.core.services.arac_service import AracService

        mock_uow = _make_mock_uow(arac_dict={"id": 1, "plaka": "34ABC", "aktif": True})
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()
        svc = AracService(repo=MagicMock(), event_bus=mock_eb)

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_arac(1)

        assert result is True
        mock_uow.arac_repo.update.assert_called()

    async def test_delete_arac_passive_vehicle_hard_deletes(self):
        """delete_arac on a passive vehicle performs a hard delete."""
        from app.core.services.arac_service import AracService

        mock_uow = _make_mock_uow(arac_dict={"id": 2, "plaka": "34DEF", "aktif": False})
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()
        svc = AracService(repo=MagicMock(), event_bus=mock_eb)

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_arac(2)

        assert result is True
        mock_uow.arac_repo.hard_delete.assert_called_once_with(2)

    async def test_delete_arac_not_found_returns_false(self):
        """delete_arac returns False when vehicle not found."""
        from app.core.services.arac_service import AracService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()
        svc = AracService(repo=MagicMock(), event_bus=mock_eb)

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_arac(9999)

        assert result is False

    async def test_get_all_paged_returns_dict(self):
        """get_all_paged returns dict with 'items' and 'total'."""
        from app.core.services.arac_service import AracService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(return_value=[])
        mock_uow.arac_repo.count_all = AsyncMock(return_value=0)
        svc = AracService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        assert "items" in result
        assert "total" in result

    async def test_bulk_add_arac_empty_list(self):
        """bulk_add_arac returns 0 when given empty list."""
        from app.core.services.arac_service import AracService

        svc = AracService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.bulk_add_arac([])
        assert result == 0

    async def test_edge_case_get_by_id_returns_none(self):
        """get_by_id returns None for a non-existent arac_id."""
        from app.core.services.arac_service import AracService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        svc = AracService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.arac_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_by_id(9999)

        assert result is None
