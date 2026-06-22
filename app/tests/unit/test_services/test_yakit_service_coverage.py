"""
YakitService coverage tests — targeting uncovered branches.
"""

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
    mock_uow.arac_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "plaka": "34ABC123"}]
    )

    mock_uow.yakit_repo = MagicMock()
    mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=False)
    mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
    mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})
    mock_uow.yakit_repo.add = AsyncMock(return_value=10)
    mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.yakit_repo.update_yakit = AsyncMock(return_value=True)
    mock_uow.yakit_repo.hard_delete = AsyncMock(return_value=True)
    mock_uow.yakit_repo.get_all = AsyncMock(return_value={"items": [], "total": 0})
    mock_uow.yakit_repo.get_stats = AsyncMock(
        return_value={"toplam_yakit": 0, "aylik_ort": 0}
    )
    mock_uow.yakit_repo.bulk_create = AsyncMock(return_value=None)
    mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=100000)
    mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

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


def _make_service():
    from app.core.services.yakit_service import YakitService

    svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
    return svc


def _make_yakit_create(**overrides):
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
    defaults.update(overrides)
    return YakitAlimiCreate(**defaults)


# ---------------------------------------------------------------------------
# add_yakit — KM outlier / odometer check
# ---------------------------------------------------------------------------


class TestAddYakitKmCheck:
    async def test_add_yakit_raises_when_km_less_than_last(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=130000)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(km_sayac=125000)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="KM Sayacı"):
                await svc.add_yakit(data)

    async def test_add_yakit_calls_rolling_check_when_last_km_exists(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=100000)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})
        mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=False)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(km_sayac=125000)

        with (
            patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow),
            patch.object(
                svc, "_check_rolling_outlier", new_callable=AsyncMock
            ) as mock_rolling,
        ):
            mock_rolling.return_value = False
            await svc.add_yakit(data)

        mock_rolling.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_yakit
# ---------------------------------------------------------------------------


class TestUpdateYakit:
    async def test_update_yakit_returns_false_when_not_found(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        from app.core.entities.models import YakitUpdate

        update = YakitUpdate(istasyon="Yeni")

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.update_yakit(9999, update)

        assert result is False

    async def test_update_yakit_returns_true_when_no_fields_set(self):
        """Empty update_data (exclude_unset) → return True without DB write.
        We use a MagicMock as the data object to simulate no fields set."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(
            return_value={"id": 5, "arac_id": 1, "litre": 300.0}
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        # Simulate a YakitUpdate with no fields set via a plain mock
        update = MagicMock()
        update.model_dump = MagicMock(return_value={})

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.update_yakit(5, update)

        assert result is True

    async def test_update_yakit_success(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(
            return_value={"id": 5, "arac_id": 1, "litre": 300.0}
        )
        mock_uow.yakit_repo.update_yakit = AsyncMock(return_value=True)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        from app.core.entities.models import YakitUpdate

        # Provide all fields needed to avoid computed-field crash on model_dump
        update = YakitUpdate(istasyon="Yeni Istasyon", litre=300.0, fiyat_tl=40.0)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.update_yakit(5, update)

        assert result is True
        mock_uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# delete_yakit
# ---------------------------------------------------------------------------


class TestDeleteYakit:
    async def test_delete_yakit_success(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value={"id": 10, "arac_id": 1})
        mock_uow.yakit_repo.hard_delete = AsyncMock(return_value=True)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_yakit(10)

        assert result is True
        mock_uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get_yakit_by_id
# ---------------------------------------------------------------------------


class TestGetYakitById:
    async def test_returns_none_when_not_found(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_yakit_by_id(9999)

        assert result is None

    async def test_returns_model_when_found(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(
            return_value={
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
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_yakit_by_id(1)

        assert result is not None


# ---------------------------------------------------------------------------
# get_by_vehicle
# ---------------------------------------------------------------------------


class TestGetByVehicle:
    async def test_returns_list_from_dict_items(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_all = AsyncMock(return_value={"items": [], "total": 0})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_by_vehicle(1)

        assert isinstance(result, list)

    async def test_returns_list_from_plain_list(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_all = AsyncMock(return_value=[])

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_by_vehicle(1)

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_stats — fallback path
# ---------------------------------------------------------------------------


class TestGetStats:
    async def test_stats_fallback_when_dashboard_fails(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.analiz_repo.get_dashboard_stats = AsyncMock(
            side_effect=Exception("DB error")
        )
        mock_uow.yakit_repo.get_stats = AsyncMock(
            return_value={"toplam_yakit": 0, "aylik_ort": 0}
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_stats()

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_monthly_summary
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    async def test_monthly_summary_uses_series_method(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_monthly_summary()

        assert isinstance(result, list)

    async def test_monthly_summary_falls_back_to_daily(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        # Remove the monthly method to force fallback
        del mock_uow.analiz_repo.get_monthly_consumption_series

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_monthly_summary()

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# bulk_add_yakit
# ---------------------------------------------------------------------------


class TestBulkAddYakit:
    async def test_bulk_skips_zero_litre_entries(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "plaka": "34ABC123"}]
        )
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=0)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        # litre > 0 is enforced by Pydantic, so we create valid items and then hack
        items = [_make_yakit_create(km_sayac=110000)]
        # Patch litre to 0 after creation
        items[0] = items[0].model_copy(update={"litre": 0})

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.bulk_add_yakit(items)

        assert result == 0

    async def test_bulk_skips_odometer_reversal(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "plaka": "34ABC123"}]
        )
        # last_km from the bulk cache is 200000; the new entry (110000) is a reversal.
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=200000)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={1: 200000})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=1, km_sayac=110000)  # < 200000

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.bulk_add_yakit([data])

        assert result == 0

    async def test_bulk_adds_valid_entries(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "plaka": "34ABC123"}]
        )
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=0)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=1, km_sayac=125000)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.bulk_add_yakit([data])

        assert result == 1
        mock_uow.yakit_repo.bulk_create.assert_called_once()


# ---------------------------------------------------------------------------
# add_yakit_alimi alias
# ---------------------------------------------------------------------------


class TestAddYakitAlimi:
    async def test_alias_raises_without_data(self):
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with pytest.raises(ValueError, match="No data"):
            await svc.add_yakit_alimi()

    async def test_alias_delegates_to_add_yakit(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        kwargs = {
            "arac_id": 1,
            "tarih": date.today() - timedelta(days=1),
            "istasyon": "Test",
            "fiyat_tl": 40.0,
            "litre": 300.0,
            "km_sayac": 125000,
            "fis_no": "F002",
            "depo_durumu": "Dolu",
        }

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.add_yakit_alimi(**kwargs)

        assert result == 10


# ---------------------------------------------------------------------------
# get_all (legacy)
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_get_all_returns_items_list(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all(limit=50)

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_all_paged — date string parsing
# ---------------------------------------------------------------------------


class TestGetAllPagedDateParsing:
    async def test_parses_date_strings(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged(
                baslangic_tarih="2025-01-01",
                bitis_tarih="2025-12-31",
            )

        assert "items" in result

    async def test_handles_invalid_date_strings_gracefully(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            # Should not raise even with garbage date strings
            result = await svc.get_all_paged(
                baslangic_tarih="not-a-date",
                bitis_tarih="also-not-a-date",
            )

        assert "items" in result
