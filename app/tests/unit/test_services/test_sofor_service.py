"""SoforService unit tests — UnitOfWork mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_mock_uow():
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_by_name = AsyncMock(return_value=None)
    mock_uow.sofor_repo.add = AsyncMock(return_value=42)
    mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.sofor_repo.update = AsyncMock(return_value=True)
    mock_uow.sofor_repo.get_all = AsyncMock(return_value=[])
    mock_uow.sofor_repo.count_all = AsyncMock(return_value=0)
    mock_uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
    mock_uow.sofor_repo.get_aktif_isimler = AsyncMock(return_value=[])
    mock_uow.sofor_repo.bulk_create = AsyncMock(return_value=[1, 2])
    mock_uow.sofor_repo.bulk_soft_delete = AsyncMock(return_value=2)
    mock_uow.sefer_repo = MagicMock()
    return mock_uow


class TestSoforService:
    def test_service_exists(self):
        """SoforService class is importable."""
        from app.core.services.sofor_service import SoforService

        assert SoforService is not None

    async def test_basic_initialization(self):
        """SoforService initializes without a real DB."""
        from app.core.services.sofor_service import SoforService

        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = SoforService(repo=mock_repo, event_bus=mock_eb)
        assert svc.repo is mock_repo
        assert svc.event_bus is mock_eb

    async def test_happy_path_add_sofor(self):
        """add_sofor returns an integer ID when name is new."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()

        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            result = await svc.add_sofor(ad_soyad="Ahmet Yilmaz")

        assert result == 42
        mock_uow.sofor_repo.add.assert_called_once()

    async def test_add_sofor_reactivates_passive_driver(self):
        """add_sofor re-activates an existing passive driver and returns its ID."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_uow.sofor_repo.get_by_name = AsyncMock(
            return_value={"id": 7, "aktif": False}
        )
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()

        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            result = await svc.add_sofor(ad_soyad="Ahmet Yilmaz")

        assert result == 7

    async def test_add_sofor_raises_on_duplicate_active(self):
        """add_sofor raises ValueError when an active driver with same name exists."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_uow.sofor_repo.get_by_name = AsyncMock(
            return_value={"id": 3, "aktif": True}
        )
        mock_repo = MagicMock()
        mock_eb = MagicMock()

        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="already exists"):
                await svc.add_sofor(ad_soyad="Ahmet Yilmaz")

    async def test_add_sofor_raises_on_short_name(self):
        """add_sofor raises ValueError when ad_soyad is too short."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="en az 3"):
                await svc.add_sofor(ad_soyad="Ab")

    async def test_get_all_paged_returns_dict(self):
        """get_all_paged returns dict with 'items' and 'total' keys."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_uow.sofor_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "ad_soyad": "Test Sürücü", "aktif": True}]
        )
        mock_uow.sofor_repo.count_all = AsyncMock(return_value=1)
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        assert "items" in result
        assert "total" in result
        assert result["total"] == 1

    async def test_get_by_id_returns_none_for_missing(self):
        """get_by_id returns None when driver does not exist."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
        mock_repo = MagicMock()
        mock_eb = MagicMock()
        svc = SoforService(repo=mock_repo, event_bus=mock_eb)

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_by_id(9999)

        assert result is None

    async def test_update_score_raises_on_out_of_range(self):
        """update_score raises ValueError for score outside 0.1-2.0."""
        from app.core.services.sofor_service import SoforService

        svc = SoforService(repo=MagicMock(), event_bus=MagicMock())
        with pytest.raises(ValueError, match="between 0.1 and 2.0"):
            await svc.update_score(1, 3.5)

    async def test_calculate_hybrid_score_no_trips(self):
        """calculate_hybrid_score returns manual_score when no trips found."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        mock_uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
        svc = SoforService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            result = await svc.calculate_hybrid_score(sofor_id=1, manual_score=1.2)

        assert result == 1.2

    async def test_bulk_delete_empty_list(self):
        """bulk_delete returns zeros when given an empty list."""
        from app.core.services.sofor_service import SoforService

        svc = SoforService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.bulk_delete([])
        assert result["deleted"] == 0
        assert result["errors"] == []

    async def test_edge_case_none_ad_soyad_raises(self):
        """add_sofor raises ValueError when ad_soyad is empty string."""
        from app.core.services.sofor_service import SoforService

        mock_uow = _make_mock_uow()
        svc = SoforService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.sofor_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError):
                await svc.add_sofor(ad_soyad="")
