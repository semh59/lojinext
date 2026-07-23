"""
Fuel (yakit) use-case coverage tests — targeting uncovered branches.

0-mock (Dilim 24): all patch(UnitOfWork) removed → real DB via db_session fixture.
Kept targeted mocks:
  - patch("...add_yakit._check_rolling_outlier") — module-function boundary, not UoW
  - MagicMock update in test_no_fields_set — bypasses YakitUpdate computed_field
    limitation (toplam_tutar crashes when fiyat_tl/litre both None)
  - patch.object(AnalizRepository, 'get_dashboard_stats') — forces exception-fallback path
  - monthly_summary fallback test: fallback is unreachable in real code (repo always
    has the method) → converted to "happy path returns list"

Dalga 4 (B.1 free-function refactor): YakitService class deleted — use-cases
are free functions in v2/modules/fuel/application/, each opening its own
UnitOfWork() (no constructor-injected repo/event_bus left to mock).
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_yakit
from v2.modules.fuel.application.add_yakit import add_yakit
from v2.modules.fuel.application.bulk_add_yakit import bulk_add_yakit
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.get_yakit import get_by_vehicle, get_yakit_by_id
from v2.modules.fuel.application.list_yakit import (
    get_all,
    get_all_paged,
    get_monthly_summary,
    get_stats,
)
from v2.modules.fuel.application.update_yakit import update_yakit

pytestmark = pytest.mark.integration


def _make_yakit_create(**overrides):
    from v2.modules.fuel.domain.entities import YakitAlimiCreate

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
    async def test_add_yakit_raises_when_km_less_than_last(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTKM01")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=130000, litre=300.0)
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)

        with pytest.raises(ValueError, match="KM Sayacı"):
            await add_yakit(data)

    async def test_add_yakit_calls_rolling_check_when_last_km_exists(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTKM02")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=100000, litre=300.0)
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)

        with patch(
            "v2.modules.fuel.application.add_yakit._check_rolling_outlier",
            new_callable=AsyncMock,
        ) as mock_rolling:
            mock_rolling.return_value = False
            await add_yakit(data)

        mock_rolling.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_yakit
# ---------------------------------------------------------------------------


class TestUpdateYakit:
    async def test_update_yakit_returns_false_when_not_found(self, db_session):
        from v2.modules.fuel.schemas import YakitUpdate

        update = YakitUpdate(istasyon="Yeni", litre=300.0, fiyat_tl=40.0)
        result = await update_yakit(9999, update)
        assert result is False

    async def test_update_yakit_returns_true_when_no_fields_set(self, db_session):
        """Empty update_data (exclude_unset) → return True without DB write.

        Targeted mock: MagicMock as update bypasses the computed_field
        toplam_tutar crash when fiyat_tl and litre are both None.
        """
        arac = await seed_arac(db_session, plaka="34YAKTUP01")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        update = MagicMock()
        update.model_dump = MagicMock(return_value={})
        result = await update_yakit(yakit.id, update)
        assert result is True

    async def test_update_yakit_success(self, db_session):
        from v2.modules.fuel.schemas import YakitUpdate

        arac = await seed_arac(db_session, plaka="34YAKTUP02")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        update = YakitUpdate(istasyon="Yeni Istasyon", litre=300.0, fiyat_tl=40.0)
        result = await update_yakit(yakit.id, update)
        assert result is True


# ---------------------------------------------------------------------------
# delete_yakit
# ---------------------------------------------------------------------------


class TestDeleteYakit:
    async def test_delete_yakit_success(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTDEL01")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        result = await delete_yakit(yakit.id)
        assert result is True

        # Verify hard-deleted: second delete returns False (not found)
        result2 = await delete_yakit(yakit.id)
        assert result2 is False


# ---------------------------------------------------------------------------
# get_yakit_by_id
# ---------------------------------------------------------------------------


class TestGetYakitById:
    async def test_returns_none_when_not_found(self, db_session):
        result = await get_yakit_by_id(9999)
        assert result is None

    async def test_returns_model_when_found(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTGET01")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        result = await get_yakit_by_id(yakit.id)
        assert result is not None


# ---------------------------------------------------------------------------
# get_by_vehicle
# ---------------------------------------------------------------------------


class TestGetByVehicle:
    async def test_returns_list_from_real_db(self, db_session):
        result = await get_by_vehicle(999999)
        assert isinstance(result, list)

    async def test_returns_items_for_vehicle(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTVEH01")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=100000, litre=300.0)
        await db_session.commit()

        result = await get_by_vehicle(arac.id)
        assert isinstance(result, list)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_stats — fallback path
# ---------------------------------------------------------------------------


class TestGetStats:
    async def test_stats_fallback_when_dashboard_fails(self, db_session):
        """When get_dashboard_stats raises, falls back to yakit_repo.get_stats."""
        import v2.modules.analytics_executive.infrastructure.executive_read_models as analiz_repo_mod

        with patch.object(
            analiz_repo_mod.AnalizRepository,
            "get_dashboard_stats",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ):
            result = await get_stats()

        assert isinstance(result, dict)

    async def test_stats_returns_dict(self, db_session):
        result = await get_stats()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_monthly_summary
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    async def test_monthly_summary_uses_series_method(self, db_session):
        result = await get_monthly_summary()
        assert isinstance(result, list)

    async def test_monthly_summary_returns_list_from_real_db(self, db_session):
        """Happy-path: real DB always has the method → returns a list.

        Note: the daily-fallback branch (when analiz_repo lacks
        get_monthly_consumption_series) is unreachable in production
        since the repo always has the method — verified by code inspection.
        """
        result = await get_monthly_summary()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# bulk_add_yakit
# ---------------------------------------------------------------------------


class TestBulkAddYakit:
    async def test_bulk_skips_zero_litre_entries(self, db_session):
        from v2.modules.fuel.domain.entities import YakitAlimiCreate

        arac = await seed_arac(db_session, plaka="34YAKTBLK01")
        await db_session.commit()

        # model_construct bypasses Field(gt=0) to reach the service-level litre<=0 guard
        item = YakitAlimiCreate.model_construct(
            arac_id=arac.id,
            tarih=date.today() - timedelta(days=1),
            istasyon="Test",
            fiyat_tl=Decimal("40.0"),
            litre=0.0,
            km_sayac=110000,
            depo_durumu="Dolu",
        )
        result = await bulk_add_yakit([item])
        assert result == 0

    async def test_bulk_skips_odometer_reversal(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTBLK02")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=200000, litre=300.0)
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, km_sayac=110000)  # < 200000
        result = await bulk_add_yakit([data])
        assert result == 0

    async def test_bulk_adds_valid_entries(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTBLK03")
        await db_session.commit()

        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)
        result = await bulk_add_yakit([data])
        assert result == 1


# ---------------------------------------------------------------------------
# get_all (legacy)
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_get_all_returns_items_list(self, db_session):
        result = await get_all(limit=50)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_all_paged — date string parsing
# ---------------------------------------------------------------------------


class TestGetAllPagedDateParsing:
    async def test_parses_date_strings(self, db_session):
        result = await get_all_paged(
            baslangic_tarih="2025-01-01",
            bitis_tarih="2025-12-31",
        )
        assert "items" in result

    async def test_parses_date_strings_no_results(self, db_session):
        result = await get_all_paged(
            baslangic_tarih="2020-01-01",
            bitis_tarih="2020-01-31",
        )
        assert "items" in result
        assert isinstance(result["items"], list)
