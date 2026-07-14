"""
Additional coverage tests for fuel (yakit) use-cases.

0-mock (Dilim 26 + dedektif denetim, dalga 4 sonrası): all patch(UnitOfWork)
removed → real DB via db_session fixture, including TestCheckRollingOutlier
(önceden tüm UoW/yakit_repo mock'lanıyordu — integration mark'ı taşıdığı
halde gerçek DB'ye hiç dokunmuyordu, bağımsız denetimde ihlal olarak
bulunup gerçek DB'ye çevrildi).
Kept targeted mocks (narrow, not UoW):
  - TestCheckRollingOutlier::test_rolling_avg_too_low_triggers_anomaly —
    yalnız get_event_bus() call-verification için (DB tarafı gerçek)
  - TestCheckRollingOutlier::test_rolling_outlier_db_exception_returns_false —
    yalnız YakitRepository.get_last_n_by_arac exception path injection
    (gerçek DB'de tetiklenemeyen bir hata senaryosu)
  - patch.object(YakitRepository, 'hard_delete') — exception path injection, not UoW
  - patch.object(YakitRepository, 'get_all') — invalid-record skip (DB can't store bad rows)
  - patch.object(AnalizRepository, 'get_dashboard_stats') — None-fallback path

Dalga 4 (B.1 free-function refactor): YakitService class deleted — use-cases
are free functions in v2/modules/fuel/application/, each opening its own
UnitOfWork() (no constructor-injected repo/event_bus left to mock). The
private `_check_rolling_outlier` helper (previously a bound method) is now
a module-level function in v2/modules/fuel/application/add_yakit.py that
opens its own `UnitOfWork()` directly.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_yakit
from v2.modules.fuel.application.add_yakit import _check_rolling_outlier, add_yakit
from v2.modules.fuel.application.bulk_add_yakit import bulk_add_yakit
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.get_yakit import get_yakit_by_id
from v2.modules.fuel.application.list_yakit import get_all_paged, get_stats

pytestmark = pytest.mark.integration


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
# add_yakit — future date
# ---------------------------------------------------------------------------


class TestAddYakitFutureDate:
    async def test_future_date_raises_value_error(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE01")
        await db_session.commit()

        data = _make_yakit_create(
            arac_id=arac.id, tarih=date.today() + timedelta(days=1)
        )

        with pytest.raises(ValueError, match="İleri tarihli"):
            await add_yakit(data)


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

        data = _make_yakit_create(arac_id=arac.id, tarih=yesterday, litre=300.0)

        with pytest.raises(ValueError, match="Duplicate"):
            await add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — inactive vehicle
# ---------------------------------------------------------------------------


class TestAddYakitInactiveVehicle:
    async def test_inactive_vehicle_raises_value_error(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE03", aktif=False)
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id)

        with pytest.raises(ValueError, match="passive or invalid"):
            await add_yakit(data)

    async def test_missing_vehicle_raises_value_error(self, db_session):
        data = _make_yakit_create(arac_id=9999999)

        with pytest.raises(ValueError):
            await add_yakit(data)


# ---------------------------------------------------------------------------
# add_yakit — toplam_tutar handling
# ---------------------------------------------------------------------------


class TestAddYakitToplamTutar:
    async def test_toplam_tutar_stored_as_litre_times_fiyat(self, db_session):
        """toplam_tutar is a @computed_field on YakitAlimiCreate (fiyat_tl*litre).
        Use-case passes the computed value to the repo which stores it."""
        arac = await seed_arac(db_session, plaka="34YKMORE04")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, litre=100.0, fiyat_tl=40.0)

        yakit_id = await add_yakit(data)
        assert isinstance(yakit_id, int) and yakit_id > 0

        stored = await get_yakit_by_id(yakit_id)
        assert stored is not None
        # fiyat_tl(40) * litre(100) = 4000
        assert float(stored.toplam_tutar) == pytest.approx(4000.0)

    async def test_toplam_tutar_different_fiyat_litre(self, db_session):
        """toplam_tutar computed correctly for different fiyat/litre values."""
        arac = await seed_arac(db_session, plaka="34YKMORE05")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, litre=200.0, fiyat_tl=45.0)

        yakit_id = await add_yakit(data)
        assert isinstance(yakit_id, int) and yakit_id > 0

        stored = await get_yakit_by_id(yakit_id)
        assert stored is not None
        # fiyat_tl(45) * litre(200) = 9000
        assert float(stored.toplam_tutar) == pytest.approx(9000.0)


# ---------------------------------------------------------------------------
# delete_yakit — various paths
# ---------------------------------------------------------------------------


class TestDeleteYakitMore:
    async def test_delete_yakit_not_found_returns_false(self, db_session):
        result = await delete_yakit(9999999)
        assert result is False

    async def test_delete_yakit_hard_delete_returns_false(self, db_session):
        """Narrow targeted mock: hard_delete returns False → use-case returns False."""
        import v2.modules.fuel.infrastructure.repository as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE06")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        with patch.object(
            yakit_repo_mod.YakitRepository, "hard_delete", AsyncMock(return_value=False)
        ):
            result = await delete_yakit(yakit.id)

        assert result is False

    async def test_delete_yakit_value_error_re_raised(self, db_session):
        """ValueError raised inside hard_delete propagates directly."""
        import v2.modules.fuel.infrastructure.repository as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE07")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        with patch.object(
            yakit_repo_mod.YakitRepository,
            "hard_delete",
            AsyncMock(side_effect=ValueError("custom value error")),
        ):
            with pytest.raises(ValueError, match="custom value error"):
                await delete_yakit(yakit.id)

    async def test_delete_yakit_generic_exception_raises_value_error(self, db_session):
        """Generic Exception is wrapped in ValueError."""
        import v2.modules.fuel.infrastructure.repository as yakit_repo_mod

        arac = await seed_arac(db_session, plaka="34YKMORE08")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        with patch.object(
            yakit_repo_mod.YakitRepository,
            "hard_delete",
            AsyncMock(side_effect=RuntimeError("db crash")),
        ):
            with pytest.raises(ValueError, match="An error occurred"):
                await delete_yakit(yakit.id)


# ---------------------------------------------------------------------------
# _check_rolling_outlier — anomaly branches
# Kept: patch("...UnitOfWork") — these test specific numeric thresholds (< 18, > 55)
# using controlled SQL rows; converting to real DB would require seeding precise
# odometer sequences and is not meaningful for the calculation logic.
# ---------------------------------------------------------------------------


class TestCheckRollingOutlier:
    async def test_rolling_avg_too_low_triggers_anomaly(self, db_session):
        """rolling_avg < 18 returns True and publishes event (real DB rows)."""
        arac = await seed_arac(db_session, plaka="34ROL001")
        for km in (199900, 199800, 199700, 199600, 199500):
            await seed_yakit(db_session, arac_id=arac.id, km_sayac=km, litre=1.0)
        await db_session.commit()

        mock_event_bus = MagicMock()
        with patch(
            "v2.modules.fuel.application.add_yakit.get_event_bus",
            return_value=mock_event_bus,
        ):
            result = await _check_rolling_outlier(arac.id, 1.0, 200000)

        assert result is True
        mock_event_bus.publish.assert_called_once()

    async def test_rolling_avg_too_high_triggers_anomaly(self, db_session):
        """rolling_avg > 55 returns True (real DB rows)."""
        arac = await seed_arac(db_session, plaka="34ROL002")
        for km in (199900, 199800, 199700, 199600, 199500):
            await seed_yakit(db_session, arac_id=arac.id, km_sayac=km, litre=100.0)
        await db_session.commit()

        result = await _check_rolling_outlier(arac.id, 100.0, 200000)

        assert result is True

    async def test_rolling_outlier_no_records_returns_false(self, db_session):
        """No fuel history for the vehicle → returns False (real DB, empty result)."""
        arac = await seed_arac(db_session, plaka="34ROL003")
        await db_session.commit()

        result = await _check_rolling_outlier(arac.id, 300.0, 125000)

        assert result is False

    async def test_rolling_outlier_total_dist_zero_returns_false(self, db_session):
        """When all km values are identical, total_dist = 0 → returns False (real DB)."""
        arac = await seed_arac(db_session, plaka="34ROL004")
        for _ in range(5):
            await seed_yakit(db_session, arac_id=arac.id, km_sayac=125000, litre=100.0)
        await db_session.commit()

        result = await _check_rolling_outlier(arac.id, 100.0, 125000)

        assert result is False

    async def test_rolling_outlier_db_exception_returns_false(self, db_session):
        """DB exception in rolling check → returns False (no raise).

        Narrow targeted mock (not UoW): a real DB has no way to make
        get_last_n_by_arac raise on demand, so this specific repo method is
        patched to simulate a transient DB error while the surrounding
        UnitOfWork/session stay real.
        """
        from v2.modules.fuel.infrastructure.repository import YakitRepository

        arac = await seed_arac(db_session, plaka="34ROL005")
        await db_session.commit()

        with patch.object(
            YakitRepository,
            "get_last_n_by_arac",
            side_effect=Exception("DB error"),
        ):
            result = await _check_rolling_outlier(arac.id, 300.0, 125000)

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
        import v2.modules.fuel.infrastructure.repository as yakit_repo_mod

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

        with patch.object(
            yakit_repo_mod.YakitRepository,
            "get_all",
            AsyncMock(return_value={"items": [valid_row, invalid_row], "total": 2}),
        ):
            result = await get_all_paged()

        assert result["total"] == 2
        assert len(result["items"]) == 1


# ---------------------------------------------------------------------------
# get_stats — dashboard returns None → fallback
# ---------------------------------------------------------------------------


class TestGetStatsDashboardNone:
    async def test_stats_dashboard_none_falls_back_to_repo(self, db_session):
        """When get_dashboard_stats returns None/falsy, fallback to yakit_repo.get_stats."""
        import app.database.repositories.analiz_repo as analiz_repo_mod

        with patch.object(
            analiz_repo_mod.AnalizRepository,
            "get_dashboard_stats",
            AsyncMock(return_value=None),
        ):
            result = await get_stats()

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# bulk_add_yakit
# ---------------------------------------------------------------------------


class TestBulkAddYakitEmpty:
    async def test_empty_list_returns_zero(self):
        result = await bulk_add_yakit([])
        assert result == 0

    async def test_bulk_logs_count_when_items_added(self, db_session):
        """Count > 0 after successful bulk insert with real DB."""
        arac = await seed_arac(db_session, plaka="34YKMORE09")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, km_sayac=130000)
        result = await bulk_add_yakit([data])
        assert result == 1


# ---------------------------------------------------------------------------
# add_yakit — litre/fiyat validation
# ---------------------------------------------------------------------------


class TestAddYakitValidation:
    async def test_zero_litre_raises(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE10")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id)
        object.__setattr__(data, "litre", 0.0)

        with pytest.raises(ValueError, match="Litres must be greater than zero"):
            await add_yakit(data)

    async def test_zero_fiyat_raises(self, db_session):
        arac = await seed_arac(db_session, plaka="34YKMORE11")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id)
        object.__setattr__(data, "fiyat_tl", 0.0)

        with pytest.raises(ValueError, match="Price must be greater than zero"):
            await add_yakit(data)
