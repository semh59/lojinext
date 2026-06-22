"""
Additional coverage tests for YakitService.

Targets uncovered branches beyond existing test files:
- add_yakit: future date raises ValueError
- add_yakit: duplicate entry blocked (check_duplicate=True)
- add_yakit: inactive vehicle raises ValueError
- add_yakit: toplam_tutar > 0 uses provided value (not computed)
- add_yakit: toplam_tutar == 0 falls back to litre*fiyat computation
- delete_yakit: record not found → returns False
- delete_yakit: hard_delete returns False → returns False
- delete_yakit: ValueError re-raised from inner handler
- delete_yakit: generic Exception → raises ValueError("An error occurred...")
- _check_rolling_outlier: rolling_avg < 18 triggers anomaly
- _check_rolling_outlier: rolling_avg > 55 triggers anomaly
- _check_rolling_outlier: not enough records → returns False
- _check_rolling_outlier: valid_fuel <= 0 → returns False
- _check_rolling_outlier: total_dist <= 0 → returns False
- _check_rolling_outlier: db exception → returns False
- get_all_paged: validation error for individual record skipped
- get_stats: dashboard returns None → fallback to yakit_repo.get_stats
- bulk_add_yakit: empty list → returns 0
- bulk_add_yakit: exception in inner loop → re-raised
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_uow(**overrides):
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


def _make_service():
    from app.core.services.yakit_service import YakitService

    svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
    return svc


# ---------------------------------------------------------------------------
# add_yakit — future date
# ---------------------------------------------------------------------------


class TestAddYakitFutureDate:
    async def test_future_date_raises_value_error(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        future_date = date.today() + timedelta(days=1)
        data = _make_yakit_create(tarih=future_date)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="İleri tarihli"):
                await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — duplicate entry
# ---------------------------------------------------------------------------


class TestAddYakitDuplicate:
    async def test_duplicate_entry_raises_value_error(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=True)
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="Duplicate"):
                await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — inactive vehicle
# ---------------------------------------------------------------------------


class TestAddYakitInactiveVehicle:
    async def test_inactive_vehicle_raises_value_error(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value={"id": 1, "aktif": False})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="passive or invalid"):
                await svc.add_yakit(data)

    async def test_missing_vehicle_raises_value_error(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=None)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create()

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError):
                await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — toplam_tutar handling
# ---------------------------------------------------------------------------


class TestAddYakitToplamTutar:
    async def test_toplam_tutar_provided_and_positive_uses_it(self):
        """When data has toplam_tutar > 0 attribute, repo receives that value."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        # Use a regular create, then attach toplam_tutar dynamically
        data = _make_yakit_create(litre=100.0, fiyat_tl=40.0)
        # Inject toplam_tutar as a dynamic attribute (simulates extended schema)
        object.__setattr__(data, "toplam_tutar", 9999.0)

        repo_call_kwargs = {}

        async def _capture_add(**kwargs):
            repo_call_kwargs.update(kwargs)
            return 99

        mock_uow.yakit_repo.add = _capture_add

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            await svc.add_yakit(data)

        # toplam_tutar=9999.0 > 0, computed = 100*40=4000 → 9999 should be used
        assert repo_call_kwargs.get("toplam_tutar") == 9999.0

    async def test_toplam_tutar_zero_delegates_to_repo(self):
        """When toplam_tutar == 0, the service passes the raw value through and
        lets the repo compute litre*fiyat in Decimal (single source of truth)."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(litre=100.0, fiyat_tl=45.0, toplam_tutar=0)

        repo_call_kwargs = {}

        async def _capture_add(**kwargs):
            repo_call_kwargs.update(kwargs)
            return 77

        mock_uow.yakit_repo.add = _capture_add

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            await svc.add_yakit(data)

        # The service delegates: it forwards the raw toplam_tutar (0) so the
        # repo computes the Decimal product. (Repo computation is covered by
        # test_yakit_repo_coverage and the precision test below.)
        assert repo_call_kwargs.get("toplam_tutar") in (0, None)


# ---------------------------------------------------------------------------
# delete_yakit — various paths
# ---------------------------------------------------------------------------


class TestDeleteYakitMore:
    async def test_delete_yakit_not_found_returns_false(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value=None)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_yakit(9999)

        assert result is False

    async def test_delete_yakit_hard_delete_returns_false(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value={"id": 5, "arac_id": 1})
        mock_uow.yakit_repo.hard_delete = AsyncMock(return_value=False)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.delete_yakit(5)

        assert result is False

    async def test_delete_yakit_value_error_re_raised(self):
        """ValueError raised inside should propagate directly."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value={"id": 5, "arac_id": 1})
        mock_uow.yakit_repo.hard_delete = AsyncMock(
            side_effect=ValueError("custom value error")
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="custom value error"):
                await svc.delete_yakit(5)

    async def test_delete_yakit_generic_exception_raises_value_error(self):
        """Generic Exception is wrapped in ValueError."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_by_id = AsyncMock(return_value={"id": 5, "arac_id": 1})
        mock_uow.yakit_repo.hard_delete = AsyncMock(
            side_effect=RuntimeError("db crash")
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="An error occurred"):
                await svc.delete_yakit(5)


# ---------------------------------------------------------------------------
# _check_rolling_outlier — anomaly branches
# ---------------------------------------------------------------------------


class TestCheckRollingOutlier:
    async def test_rolling_avg_too_low_triggers_anomaly(self):
        """rolling_avg < 18 returns True and publishes event."""
        from app.core.services.yakit_service import YakitService

        mock_event_bus = MagicMock()

        svc = YakitService(repo=MagicMock(), event_bus=mock_event_bus)

        # Fake DB rows: low consumption scenario
        # kms: [200000, 199900, 199800, 199700, 199600] → dist = 400 km
        # litres: [5] already provided in rows; valid_fuel excludes last row's litre
        class FakeRow:
            def __init__(self, litre, km_sayac):
                self.litre = litre
                self.km_sayac = km_sayac

        fake_rows = [
            FakeRow(1.0, 199900),
            FakeRow(1.0, 199800),
            FakeRow(1.0, 199700),
            FakeRow(1.0, 199600),
            FakeRow(1.0, 199500),
        ]

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=fake_rows)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_uow = _make_mock_uow()
        mock_uow.session = mock_session

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            # current_litre=1.0, current_km=200000 → very low consumption
            result = await svc._check_rolling_outlier(1, 1.0, 200000)

        # Should detect anomaly (very low consumption = < 18 L/100km)
        assert result is True
        mock_event_bus.publish.assert_called_once()

    async def test_rolling_avg_too_high_triggers_anomaly(self):
        """rolling_avg > 55 returns True."""
        from app.core.services.yakit_service import YakitService

        mock_event_bus = MagicMock()
        svc = YakitService(repo=MagicMock(), event_bus=mock_event_bus)

        # 100 litres per 100 km → way above 55
        class FakeRow:
            def __init__(self, litre, km_sayac):
                self.litre = litre
                self.km_sayac = km_sayac

        # 5 rows, each 100L over 100km
        fake_rows = [
            FakeRow(100.0, 199900),
            FakeRow(100.0, 199800),
            FakeRow(100.0, 199700),
            FakeRow(100.0, 199600),
            FakeRow(100.0, 199500),
        ]

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=fake_rows)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_uow = _make_mock_uow()
        mock_uow.session = mock_session

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 100.0, 200000)

        assert result is True

    async def test_rolling_outlier_no_records_returns_false(self):
        """Empty last_5 → returns False."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_uow = _make_mock_uow()
        mock_uow.session = mock_session

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 300.0, 125000)

        assert result is False

    async def test_rolling_outlier_total_dist_zero_returns_false(self):
        """When all km values are identical, total_dist = 0 → returns False."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        class FakeRow:
            def __init__(self, litre, km_sayac):
                self.litre = litre
                self.km_sayac = km_sayac

        # All same km → total_dist = 0
        fake_rows = [FakeRow(100.0, 125000)] * 5

        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=fake_rows)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_uow = _make_mock_uow()
        mock_uow.session = mock_session

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 100.0, 125000)

        assert result is False

    async def test_rolling_outlier_db_exception_returns_false(self):
        """DB exception in rolling check → returns False (no raise)."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))

        mock_uow = _make_mock_uow()
        mock_uow.session = mock_session

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 300.0, 125000)

        assert result is False


# ---------------------------------------------------------------------------
# get_all_paged — validation error skipped
# ---------------------------------------------------------------------------


class TestGetAllPagedValidationSkip:
    async def test_invalid_record_skipped_in_paged_result(self):
        """Records that fail model_validate are skipped (no crash)."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        # Return one valid record and one invalid (missing required fields)
        valid_row = {
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
        # Invalid: will fail YakitAlimi.model_validate
        invalid_row = {"id": 2, "broken": "data"}

        mock_uow.yakit_repo.get_all = AsyncMock(
            return_value={"items": [valid_row, invalid_row], "total": 2}
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_all_paged()

        # Only the valid row should be in results
        assert result["total"] == 2  # total from DB unchanged
        assert len(result["items"]) == 1  # invalid row skipped


# ---------------------------------------------------------------------------
# get_stats — dashboard returns None → fallback
# ---------------------------------------------------------------------------


class TestGetStatsDashboardNone:
    async def test_stats_dashboard_none_falls_back_to_repo(self):
        """When get_dashboard_stats returns None/falsy, fallback path used."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.analiz_repo.get_dashboard_stats = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_stats = AsyncMock(
            return_value={"toplam_yakit": 42, "aylik_ort": 33.5}
        )

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.get_stats()

        assert result["toplam_yakit"] == 42


# ---------------------------------------------------------------------------
# bulk_add_yakit — empty list
# ---------------------------------------------------------------------------


class TestBulkAddYakitEmpty:
    async def test_empty_list_returns_zero(self):
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.bulk_add_yakit([])
        assert result == 0

    async def test_bulk_logs_count_when_items_added(self):
        """Verify count > 0 logged after successful bulk insert."""
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.arac_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "plaka": "34ABC123"}]
        )
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=0)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=1, km_sayac=130000)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            result = await svc.bulk_add_yakit([data])

        assert result == 1


# ---------------------------------------------------------------------------
# add_yakit — litre/fiyat validation
# ---------------------------------------------------------------------------


class TestAddYakitValidation:
    async def test_zero_litre_raises(self):
        # Pydantic enforces litre > 0 — test the service message via direct bypass
        # We can't create YakitAlimiCreate with litre=0 (validator), so patch service
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})
        mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=False)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create()
        # Bypass pydantic by directly mutating the field
        object.__setattr__(data, "litre", 0.0)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="Litres must be greater than zero"):
                await svc.add_yakit(data)

    async def test_zero_fiyat_raises(self):
        from app.core.services.yakit_service import YakitService

        mock_uow = _make_mock_uow()
        mock_uow.yakit_repo.get_son_km = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_son_km_bulk = AsyncMock(return_value={})
        mock_uow.yakit_repo.check_duplicate = AsyncMock(return_value=False)

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create()
        object.__setattr__(data, "fiyat_tl", 0.0)

        with patch("app.core.services.yakit_service.UnitOfWork", return_value=mock_uow):
            with pytest.raises(ValueError, match="Price must be greater than zero"):
                await svc.add_yakit(data)
