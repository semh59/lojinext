"""
Additional coverage tests for YakitService.

0-mock (Dilim 26): all patch(UnitOfWork) removed → real DB via db_session fixture.
Kept targeted mocks:
  - TestCheckRollingOutlier — patch("...get_uow") for numeric calc branches;
    testing specific rolling-avg thresholds with controlled SQL rows (not UoW)
  - patch.object(YakitRepository, 'hard_delete') — exception path injection, not UoW
  - patch.object(YakitRepository, 'get_all') — invalid-record skip (DB can't store bad rows)
  - patch.object(AnalizRepository, 'get_dashboard_stats') — None-fallback path
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_yakit

pytestmark = pytest.mark.unit


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

    return YakitService(repo=MagicMock(), event_bus=MagicMock())


# ---------------------------------------------------------------------------
# add_yakit — future date
# ---------------------------------------------------------------------------


class TestAddYakitFutureDate:
    async def test_future_date_raises_value_error(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE01")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(
            arac_id=arac.id, tarih=date.today() + timedelta(days=1)
        )

        with pytest.raises(ValueError, match="İleri tarihli"):
            await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — duplicate entry
# ---------------------------------------------------------------------------


class TestAddYakitDuplicate:
    async def test_duplicate_entry_raises_value_error(self, db_session):
        yesterday = date.today() - timedelta(days=1)
        arac = await seed_arac(db_session, plaka="34YKMORE02")
        await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=120000, litre=300.0, tarih=yesterday
        )
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id, tarih=yesterday, litre=300.0)

        with pytest.raises(ValueError, match="Duplicate"):
            await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — inactive vehicle
# ---------------------------------------------------------------------------


class TestAddYakitInactiveVehicle:
    async def test_inactive_vehicle_raises_value_error(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE03", aktif=False)
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id)

        with pytest.raises(ValueError, match="passive or invalid"):
            await svc.add_yakit(data)

    async def test_missing_vehicle_raises_value_error(self, db_session):
        svc = _make_service()
        data = _make_yakit_create(arac_id=9999999)

        with pytest.raises(ValueError):
            await svc.add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — toplam_tutar handling
# ---------------------------------------------------------------------------


class TestAddYakitToplamTutar:
    async def test_toplam_tutar_stored_as_litre_times_fiyat(self, db_session):
        """toplam_tutar is a @computed_field on YakitAlimiCreate (fiyat_tl*litre).
        Service passes the computed value to the repo which stores it."""
        arac = await seed_arac(db_session, plaka="34YKMORE04")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id, litre=100.0, fiyat_tl=40.0)

        yakit_id = await svc.add_yakit(data)
        assert isinstance(yakit_id, int) and yakit_id > 0

        stored = await svc.get_yakit_by_id(yakit_id)
        assert stored is not None
        # fiyat_tl(40) * litre(100) = 4000
        assert float(stored.toplam_tutar) == pytest.approx(4000.0)

    async def test_toplam_tutar_different_fiyat_litre(self, db_session):
        """toplam_tutar computed correctly for different fiyat/litre values."""
        arac = await seed_arac(db_session, plaka="34YKMORE05")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id, litre=200.0, fiyat_tl=45.0)

        yakit_id = await svc.add_yakit(data)
        assert isinstance(yakit_id, int) and yakit_id > 0

        stored = await svc.get_yakit_by_id(yakit_id)
        assert stored is not None
        # fiyat_tl(45) * litre(200) = 9000
        assert float(stored.toplam_tutar) == pytest.approx(9000.0)


# ---------------------------------------------------------------------------
# delete_yakit — various paths
# ---------------------------------------------------------------------------


class TestDeleteYakitMore:
    async def test_delete_yakit_not_found_returns_false(self, db_session):
        svc = _make_service()
        result = await svc.delete_yakit(9999999)
        assert result is False

    async def test_delete_yakit_hard_delete_returns_false(self, db_session):
        """Narrow targeted mock: hard_delete returns False → service returns False."""
        import app.database.repositories.yakit_repo as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE06")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        svc = _make_service()
        with patch.object(
            yakit_repo_mod.YakitRepository, "hard_delete", AsyncMock(return_value=False)
        ):
            result = await svc.delete_yakit(yakit.id)

        assert result is False

    async def test_delete_yakit_value_error_re_raised(self, db_session):
        """ValueError raised inside hard_delete propagates directly."""
        import app.database.repositories.yakit_repo as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE07")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        svc = _make_service()
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "hard_delete",
            AsyncMock(side_effect=ValueError("custom value error")),
        ):
            with pytest.raises(ValueError, match="custom value error"):
                await svc.delete_yakit(yakit.id)

    async def test_delete_yakit_generic_exception_raises_value_error(self, db_session):
        """Generic Exception is wrapped in ValueError."""
        import app.database.repositories.yakit_repo as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE08")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        svc = _make_service()
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "hard_delete",
            AsyncMock(side_effect=RuntimeError("db crash")),
        ):
            with pytest.raises(ValueError, match="An error occurred"):
                await svc.delete_yakit(yakit.id)


# ---------------------------------------------------------------------------
# _check_rolling_outlier — anomaly branches
# Kept: patch("...get_uow") — these test specific numeric thresholds (< 18, > 55)
# using controlled SQL rows; converting to real DB would require seeding precise
# odometer sequences and is not meaningful for the calculation logic.
# ---------------------------------------------------------------------------


class TestCheckRollingOutlier:
    async def test_rolling_avg_too_low_triggers_anomaly(self):
        """rolling_avg < 18 returns True and publishes event."""
        from app.core.services.yakit_service import YakitService

        mock_event_bus = MagicMock()
        svc = YakitService(repo=MagicMock(), event_bus=mock_event_bus)

        fake_rows = [
            {"litre": 1.0, "km_sayac": 199900},
            {"litre": 1.0, "km_sayac": 199800},
            {"litre": 1.0, "km_sayac": 199700},
            {"litre": 1.0, "km_sayac": 199600},
            {"litre": 1.0, "km_sayac": 199500},
        ]

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=fake_rows)

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 1.0, 200000)

        assert result is True
        mock_event_bus.publish.assert_called_once()

    async def test_rolling_avg_too_high_triggers_anomaly(self):
        """rolling_avg > 55 returns True."""
        from app.core.services.yakit_service import YakitService

        mock_event_bus = MagicMock()
        svc = YakitService(repo=MagicMock(), event_bus=mock_event_bus)

        fake_rows = [
            {"litre": 100.0, "km_sayac": 199900},
            {"litre": 100.0, "km_sayac": 199800},
            {"litre": 100.0, "km_sayac": 199700},
            {"litre": 100.0, "km_sayac": 199600},
            {"litre": 100.0, "km_sayac": 199500},
        ]

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=fake_rows)

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 100.0, 200000)

        assert result is True

    async def test_rolling_outlier_no_records_returns_false(self):
        """Empty last_5 → returns False."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=[])

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 300.0, 125000)

        assert result is False

    async def test_rolling_outlier_total_dist_zero_returns_false(self):
        """When all km values are identical, total_dist = 0 → returns False."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        fake_rows = [{"litre": 100.0, "km_sayac": 125000}] * 5

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=fake_rows)

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 100.0, 125000)

        assert result is False

    async def test_rolling_outlier_db_exception_returns_false(self):
        """DB exception in rolling check → returns False (no raise)."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(
            side_effect=Exception("DB error")
        )

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            result = await svc._check_rolling_outlier(1, 300.0, 125000)

        assert result is False


# ---------------------------------------------------------------------------
# get_all_paged — validation error skipped
# ---------------------------------------------------------------------------


class TestGetAllPagedValidationSkip:
    async def test_invalid_record_skipped_in_paged_result(self, db_session):
        """Records that fail model_validate are skipped (no crash).

        Narrow targeted mock: real DB cannot store structurally invalid rows,
        so YakitRepository.get_all is patched to inject a broken record.
        """
        import app.database.repositories.yakit_repo as yakit_repo_mod

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
        invalid_row = {"id": 2, "broken": "data"}

        svc = _make_service()
        with patch.object(
            yakit_repo_mod.YakitRepository,
            "get_all",
            AsyncMock(return_value={"items": [valid_row, invalid_row], "total": 2}),
        ):
            result = await svc.get_all_paged()

        assert result["total"] == 2
        assert len(result["items"]) == 1


# ---------------------------------------------------------------------------
# get_stats — dashboard returns None → fallback
# ---------------------------------------------------------------------------


class TestGetStatsDashboardNone:
    async def test_stats_dashboard_none_falls_back_to_repo(self, db_session):
        """When get_dashboard_stats returns None/falsy, fallback to yakit_repo.get_stats."""
        import app.database.repositories.analiz_repo as analiz_repo_mod

        svc = _make_service()
        with patch.object(
            analiz_repo_mod.AnalizRepository,
            "get_dashboard_stats",
            AsyncMock(return_value=None),
        ):
            result = await svc.get_stats()

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# bulk_add_yakit
# ---------------------------------------------------------------------------


class TestBulkAddYakitEmpty:
    async def test_empty_list_returns_zero(self):
        svc = _make_service()
        result = await svc.bulk_add_yakit([])
        assert result == 0

    async def test_bulk_logs_count_when_items_added(self, db_session):
        """Count > 0 after successful bulk insert with real DB."""
        arac = await seed_arac(db_session, plaka="34YKMORE09")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id, km_sayac=130000)
        result = await svc.bulk_add_yakit([data])
        assert result == 1


# ---------------------------------------------------------------------------
# add_yakit — litre/fiyat validation
# ---------------------------------------------------------------------------


class TestAddYakitValidation:
    async def test_zero_litre_raises(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE10")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id)
        object.__setattr__(data, "litre", 0.0)

        with pytest.raises(ValueError, match="Litres must be greater than zero"):
            await svc.add_yakit(data)

    async def test_zero_fiyat_raises(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE11")
        await db_session.commit()

        svc = _make_service()
        data = _make_yakit_create(arac_id=arac.id)
        object.__setattr__(data, "fiyat_tl", 0.0)

        with pytest.raises(ValueError, match="Price must be greater than zero"):
            await svc.add_yakit(data)
