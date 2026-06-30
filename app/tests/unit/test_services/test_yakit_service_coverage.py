"""
YakitService coverage tests — targeting uncovered branches.

0-mock (Dilim 24): all patch(UnitOfWork) removed → real DB via db_session fixture.
Kept targeted mocks:
  - patch.object(svc, '_check_rolling_outlier') — service-method boundary, not UoW
  - MagicMock update in test_no_fields_set — bypasses YakitUpdate computed_field
    limitation (toplam_tutar crashes when fiyat_tl/litre both None)
  - patch.object(AnalizRepository, 'get_dashboard_stats') — forces exception-fallback path
  - monthly_summary fallback test: fallback is unreachable in real code (repo always
    has the method) → converted to "happy path returns list"
"""

from datetime import date, timedelta
from decimal import Decimal
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


def _svc():
    from app.core.services.yakit_service import YakitService

    return YakitService(repo=MagicMock(), event_bus=MagicMock())


# ---------------------------------------------------------------------------
# add_yakit — KM outlier / odometer check
# ---------------------------------------------------------------------------


class TestAddYakitKmCheck:
    async def test_add_yakit_raises_when_km_less_than_last(self, db_session):
        from app.core.services.yakit_service import YakitService

        arac = await seed_arac(db_session, plaka="34YAKTKM01")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=130000, litre=300.0)
        await db_session.commit()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)

        with pytest.raises(ValueError, match="KM Sayacı"):
            await svc.add_yakit(data)

    async def test_add_yakit_calls_rolling_check_when_last_km_exists(self, db_session):
        from app.core.services.yakit_service import YakitService

        arac = await seed_arac(db_session, plaka="34YAKTKM02")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=100000, litre=300.0)
        await db_session.commit()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)

        with patch.object(
            svc, "_check_rolling_outlier", new_callable=AsyncMock
        ) as mock_rolling:
            mock_rolling.return_value = False
            await svc.add_yakit(data)

        mock_rolling.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_yakit
# ---------------------------------------------------------------------------


class TestUpdateYakit:
    async def test_update_yakit_returns_false_when_not_found(self, db_session):
        from app.core.entities.models import YakitUpdate

        svc = _svc()
        update = YakitUpdate(istasyon="Yeni", litre=300.0, fiyat_tl=40.0)
        result = await svc.update_yakit(9999, update)
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

        svc = _svc()
        update = MagicMock()
        update.model_dump = MagicMock(return_value={})
        result = await svc.update_yakit(yakit.id, update)
        assert result is True

    async def test_update_yakit_success(self, db_session):
        from app.core.entities.models import YakitUpdate

        arac = await seed_arac(db_session, plaka="34YAKTUP02")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        svc = _svc()
        update = YakitUpdate(istasyon="Yeni Istasyon", litre=300.0, fiyat_tl=40.0)
        result = await svc.update_yakit(yakit.id, update)
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

        svc = _svc()
        result = await svc.delete_yakit(yakit.id)
        assert result is True

        # Verify hard-deleted: second delete returns False (not found)
        result2 = await svc.delete_yakit(yakit.id)
        assert result2 is False


# ---------------------------------------------------------------------------
# get_yakit_by_id
# ---------------------------------------------------------------------------


class TestGetYakitById:
    async def test_returns_none_when_not_found(self, db_session):
        svc = _svc()
        result = await svc.get_yakit_by_id(9999)
        assert result is None

    async def test_returns_model_when_found(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTGET01")
        yakit = await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=100000, litre=300.0
        )
        await db_session.commit()

        svc = _svc()
        result = await svc.get_yakit_by_id(yakit.id)
        assert result is not None


# ---------------------------------------------------------------------------
# get_by_vehicle
# ---------------------------------------------------------------------------


class TestGetByVehicle:
    async def test_returns_list_from_real_db(self, db_session):
        svc = _svc()
        result = await svc.get_by_vehicle(999999)
        assert isinstance(result, list)

    async def test_returns_items_for_vehicle(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTVEH01")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=100000, litre=300.0)
        await db_session.commit()

        svc = _svc()
        result = await svc.get_by_vehicle(arac.id)
        assert isinstance(result, list)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# get_stats — fallback path
# ---------------------------------------------------------------------------


class TestGetStats:
    async def test_stats_fallback_when_dashboard_fails(self, db_session):
        """When get_dashboard_stats raises, falls back to yakit_repo.get_stats."""
        import app.database.repositories.analiz_repo as analiz_repo_mod

        svc = _svc()
        with patch.object(
            analiz_repo_mod.AnalizRepository,
            "get_dashboard_stats",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ):
            result = await svc.get_stats()

        assert isinstance(result, dict)

    async def test_stats_returns_dict(self, db_session):
        svc = _svc()
        result = await svc.get_stats()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_monthly_summary
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    async def test_monthly_summary_uses_series_method(self, db_session):
        svc = _svc()
        result = await svc.get_monthly_summary()
        assert isinstance(result, list)

    async def test_monthly_summary_returns_list_from_real_db(self, db_session):
        """Happy-path: real DB always has the method → returns a list.

        Note: the daily-fallback branch (when analiz_repo lacks
        get_monthly_consumption_series) is unreachable in production
        since the repo always has the method — verified by code inspection.
        """
        svc = _svc()
        result = await svc.get_monthly_summary()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# bulk_add_yakit
# ---------------------------------------------------------------------------


class TestBulkAddYakit:
    async def test_bulk_skips_zero_litre_entries(self, db_session):
        from app.core.entities.models import YakitAlimiCreate

        arac = await seed_arac(db_session, plaka="34YAKTBLK01")
        await db_session.commit()

        svc = _svc()
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
        result = await svc.bulk_add_yakit([item])
        assert result == 0

    async def test_bulk_skips_odometer_reversal(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTBLK02")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=200000, litre=300.0)
        await db_session.commit()

        svc = _svc()
        data = _make_yakit_create(arac_id=arac.id, km_sayac=110000)  # < 200000
        result = await svc.bulk_add_yakit([data])
        assert result == 0

    async def test_bulk_adds_valid_entries(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTBLK03")
        await db_session.commit()

        svc = _svc()
        data = _make_yakit_create(arac_id=arac.id, km_sayac=125000)
        result = await svc.bulk_add_yakit([data])
        assert result == 1


# ---------------------------------------------------------------------------
# add_yakit_alimi alias
# ---------------------------------------------------------------------------


class TestAddYakitAlimi:
    async def test_alias_raises_without_data(self):
        svc = _svc()
        with pytest.raises(ValueError, match="No data"):
            await svc.add_yakit_alimi()

    async def test_alias_delegates_to_add_yakit(self, db_session):
        arac = await seed_arac(db_session, plaka="34YAKTALIAS01")
        await db_session.commit()

        svc = _svc()
        result = await svc.add_yakit_alimi(
            arac_id=arac.id,
            tarih=date.today() - timedelta(days=1),
            istasyon="Test",
            fiyat_tl=40.0,
            litre=300.0,
            km_sayac=125000,
            fis_no="F002",
            depo_durumu="Dolu",
        )
        assert isinstance(result, int) and result > 0


# ---------------------------------------------------------------------------
# get_all (legacy)
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_get_all_returns_items_list(self, db_session):
        svc = _svc()
        result = await svc.get_all(limit=50)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_all_paged — date string parsing
# ---------------------------------------------------------------------------


class TestGetAllPagedDateParsing:
    async def test_parses_date_strings(self, db_session):
        svc = _svc()
        result = await svc.get_all_paged(
            baslangic_tarih="2025-01-01",
            bitis_tarih="2025-12-31",
        )
        assert "items" in result

    async def test_parses_date_strings_no_results(self, db_session):
        svc = _svc()
        result = await svc.get_all_paged(
            baslangic_tarih="2020-01-01",
            bitis_tarih="2020-01-31",
        )
        assert "items" in result
        assert isinstance(result["items"], list)
