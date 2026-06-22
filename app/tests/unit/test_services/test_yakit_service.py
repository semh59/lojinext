"""YakitService unit tests — UnitOfWork mocked."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_mock_uow():
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.session = AsyncMock()

    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(
        return_value={"id": 1, "plaka": "34ABC123", "aktif": True}
    )
    mock_uow.arac_repo.get_all = AsyncMock(return_value=[])

    mock_uow.yakit_repo = MagicMock()
    mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=False)
    mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
    mock_uow.yakit_repo.add = AsyncMock(return_value=10)
    mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.yakit_repo.update_yakit = AsyncMock(return_value=True)
    mock_uow.yakit_repo.hard_delete = AsyncMock(return_value=True)
    mock_uow.yakit_repo.get_all = AsyncMock(return_value={"items": [], "total": 0})
    mock_uow.yakit_repo.get_stats = AsyncMock(
        return_value={"toplam_yakit": 0, "aylik_ort": 0}
    )
    mock_uow.yakit_repo.bulk_create = AsyncMock(return_value=None)

    mock_uow.analiz_repo = MagicMock()
    mock_uow.analiz_repo.get_dashboard_stats = AsyncMock(
        return_value={
            "toplam_yakit": 5000,
            "filo_ortalama": 32.5,
            "toplam_tutar": 150000,
        }
    )
    mock_uow.analiz_repo.get_monthly_consumption_series = AsyncMock(return_value=[])
    mock_uow.analiz_repo.get_daily_consumption_series = AsyncMock(return_value=[])
    return mock_uow


def _make_yakit_create(**kwargs):
    from app.core.entities.models import YakitAlimiCreate

    defaults = {
        "arac_id": 1,
        "tarih": date.today() - timedelta(days=1),
        "istasyon": "Test Istasyon",
        "fiyat_tl": 40.0,
        "litre": 300.0,
        "km_sayac": 125000,
        "fis_no": "F001",
        "depo_durumu": "Dolu",
    }
    defaults.update(kwargs)
    return YakitAlimiCreate(**defaults)


class TestYakitService:
    def test_service_exists(self):
        """YakitService class is importable."""
        from app.core.services.yakit_service import YakitService

        assert YakitService is not None

    async def test_basic_initialization(self):
        """YakitService can be instantiated without a real DB."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        assert svc is not None

    async def test_happy_path_add_yakit(self):
        """add_yakit returns an integer ID on success."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_eb = MagicMock()
        mock_eb.publish = MagicMock()
        svc = YakitService(repo=MagicMock(), event_bus=mock_eb)

        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.add_yakit(data)

        assert result == 10
        mock_uow.yakit_repo.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_add_yakit_raises_for_zero_litres(self):
        """YakitAlimiCreate Pydantic schema rejects litre=0 at construction."""
        from app.core.entities.models import YakitAlimiCreate

        with pytest.raises(Exception):  # pydantic ValidationError
            YakitAlimiCreate(
                arac_id=1,
                tarih=date.today() - timedelta(days=1),
                istasyon="Test",
                fiyat_tl=40.0,
                litre=0.0,
                km_sayac=125000,
                fis_no="F001",
                depo_durumu="Dolu",
            )

    async def test_add_yakit_raises_for_zero_price(self):
        """YakitAlimiCreate Pydantic schema rejects fiyat_tl=0 at construction."""
        from app.core.entities.models import YakitAlimiCreate

        with pytest.raises(Exception):  # pydantic ValidationError
            YakitAlimiCreate(
                arac_id=1,
                tarih=date.today() - timedelta(days=1),
                istasyon="Test",
                fiyat_tl=0.0,
                litre=300.0,
                km_sayac=125000,
                fis_no="F001",
                depo_durumu="Dolu",
            )

    async def test_add_yakit_raises_for_future_date(self):
        """add_yakit raises ValueError for a future date."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        data = _make_yakit_create(tarih=date.today() + timedelta(days=5))

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="İleri tarihli"):
                await svc.add_yakit(data)

    async def test_add_yakit_raises_for_duplicate(self):
        """add_yakit raises ValueError when duplicate detected."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=True)
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="Duplicate"):
                await svc.add_yakit(data)

    async def test_add_yakit_raises_for_inactive_vehicle(self):
        """add_yakit raises ValueError when vehicle is inactive."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(
            return_value={"id": 1, "plaka": "34ABC123", "aktif": False}
        )
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="passive or invalid"):
                await svc.add_yakit(data)

    async def test_get_stats_returns_dict(self):
        """get_stats returns a dict with expected keys."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_stats()

        assert isinstance(result, dict)
        assert "toplam_yakit" in result

    async def test_get_all_paged_returns_dict(self):
        """get_all_paged returns dict with items and total."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_all = AsyncMock(
            return_value={
                "items": [
                    {
                        "id": 1,
                        "arac_id": 1,
                        "tarih": date.today() - timedelta(days=1),
                        "litre": 300.0,
                        "fiyat_tl": 40.0,
                        "km_sayac": 125000,
                        "istasyon": "Test",
                        "fis_no": "F001",
                        "depo_durumu": "Dolu",
                        "toplam_tutar": 12000.0,
                        "aktif": True,
                    }
                ],
                "total": 1,
            }
        )
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        assert "items" in result
        assert "total" in result
        assert result["total"] == 1

    async def test_delete_yakit_not_found_returns_false(self):
        """delete_yakit returns False when record not found."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_yakit(9999)

        assert result is False

    async def test_bulk_add_yakit_empty_list(self):
        """bulk_add_yakit returns 0 for empty input."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.bulk_add_yakit([])
        assert result == 0
