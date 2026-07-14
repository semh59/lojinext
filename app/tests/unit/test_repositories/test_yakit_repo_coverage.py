"""
YakitRepository unit coverage tests — fuel record CRUD, stats, date filters,
period management, get_by_date_range, check_duplicate, get_son_km.

Uses mocked AsyncSession — no real DB needed.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from v2.modules.fuel.infrastructure.repository import YakitRepository, get_yakit_repo

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Session mock helpers
# ---------------------------------------------------------------------------


def _make_session(scalar_value=None, rows=None):
    """Return a mocked AsyncSession configured for yakit_repo calls."""
    session = AsyncMock()

    # scalar() — used by execute_scalar
    mock_result = MagicMock()
    mock_result.scalar.return_value = scalar_value
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.rowcount = 0

    # mappings() — used by execute_query
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = rows or []
    mock_result.mappings.return_value = mock_mappings

    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


def _make_repo(session=None) -> YakitRepository:
    if session is None:
        session = _make_session()
    return YakitRepository(session=session)


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_get_all_basic_returns_dict(self):
        session = _make_session(scalar_value=0, rows=[])
        repo = _make_repo(session)
        result = await repo.get_all()
        assert "items" in result
        assert "total" in result
        assert isinstance(result["items"], list)

    async def test_get_all_with_arac_id_filter(self):
        session = _make_session(scalar_value=2, rows=[{"id": 1}, {"id": 2}])
        repo = _make_repo(session)
        result = await repo.get_all(arac_id=5)
        assert result["total"] == 2

    async def test_get_all_with_date_range(self):
        session = _make_session(scalar_value=1, rows=[{"id": 1}])
        repo = _make_repo(session)
        result = await repo.get_all(
            baslangic_tarih=date(2024, 1, 1),
            bitis_tarih=date(2024, 12, 31),
        )
        assert result["total"] == 1

    async def test_get_all_include_inactive(self):
        session = _make_session(scalar_value=3, rows=[{}, {}, {}])
        repo = _make_repo(session)
        result = await repo.get_all(include_inactive=True)
        assert result["total"] == 3

    async def test_get_all_asc_order(self):
        session = _make_session(scalar_value=0, rows=[])
        repo = _make_repo(session)
        result = await repo.get_all(desc=False)
        # Just verify it runs without error
        assert "items" in result

    async def test_get_all_limit_offset_applied(self):
        session = _make_session(scalar_value=100, rows=[])
        repo = _make_repo(session)
        result = await repo.get_all(limit=10, offset=20)
        assert result["total"] == 100


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAdd:
    async def test_add_computes_toplam_tutar_when_not_provided(self):
        """When toplam_tutar is None, it should compute fiyat × litre."""
        session = _make_session()
        repo = _make_repo(session)

        created_kwargs: dict = {}

        async def _spy_create(**kwargs):
            created_kwargs.update(kwargs)
            return 99

        repo.create = _spy_create

        result = await repo.add(
            tarih=date(2024, 6, 1),
            arac_id=1,
            istasyon="Shell",
            fiyat=10.5,
            litre=50.0,
            km_sayac=150000,
        )

        assert result == 99
        assert created_kwargs["toplam_tutar"] == pytest.approx(525.0, abs=0.01)

    async def test_add_toplam_tutar_is_cent_accurate_decimal(self):
        """Money total is computed in Decimal, not float: 42.55 * 23.70 must be
        1008.44 (Decimal, ROUND_HALF_UP), NOT 1008.43 (round(float*float, 2))."""
        from decimal import Decimal

        session = _make_session()
        repo = _make_repo(session)

        created_kwargs: dict = {}

        async def _spy_create(**kwargs):
            created_kwargs.update(kwargs)
            return 1

        repo.create = _spy_create

        await repo.add(
            tarih=date(2024, 6, 1),
            arac_id=1,
            istasyon="Opet",
            fiyat=42.55,
            litre=23.70,
            km_sayac=100000,
        )

        toplam = created_kwargs["toplam_tutar"]
        assert isinstance(toplam, Decimal)
        assert toplam == Decimal("1008.44")
        # Guard against a regression to the float computation:
        assert toplam != Decimal("1008.43")

    async def test_add_uses_provided_toplam_tutar(self):
        session = _make_session()
        repo = _make_repo(session)

        created_kwargs: dict = {}

        async def _spy_create(**kwargs):
            created_kwargs.update(kwargs)
            return 55

        repo.create = _spy_create

        await repo.add(
            tarih=date(2024, 6, 1),
            arac_id=2,
            istasyon="BP",
            fiyat=8.0,
            litre=40.0,
            km_sayac=200000,
            toplam_tutar=999.0,
        )

        assert created_kwargs["toplam_tutar"] == pytest.approx(999.0, abs=0.01)

    async def test_add_zero_toplam_tutar_recomputes(self):
        """toplam_tutar=0 should be treated as missing → recompute."""
        session = _make_session()
        repo = _make_repo(session)

        created_kwargs: dict = {}

        async def _spy_create(**kwargs):
            created_kwargs.update(kwargs)
            return 1

        repo.create = _spy_create

        await repo.add(
            tarih=date(2024, 1, 1),
            arac_id=1,
            istasyon="Opet",
            fiyat=10.0,
            litre=30.0,
            km_sayac=50000,
            toplam_tutar=0.0,
        )

        assert created_kwargs["toplam_tutar"] == pytest.approx(300.0, abs=0.01)

    async def test_add_includes_fis_no(self):
        session = _make_session()
        repo = _make_repo(session)

        captured = {}

        async def _spy_create(**kwargs):
            captured.update(kwargs)
            return 7

        repo.create = _spy_create

        await repo.add(
            tarih=date(2024, 3, 15),
            arac_id=3,
            istasyon="Petrol",
            fiyat=9.5,
            litre=60.0,
            km_sayac=75000,
            fis_no="ABC123",
        )

        assert captured["fis_no"] == "ABC123"
        assert captured["depo_durumu"] == "Bilinmiyor"


# ---------------------------------------------------------------------------
# check_duplicate
# ---------------------------------------------------------------------------


class TestCheckDuplicate:
    async def test_returns_true_when_exists(self):
        session = _make_session(scalar_value=True)
        repo = _make_repo(session)
        result = await repo.check_duplicate(1, date(2024, 1, 1), 50.0)
        assert result is True

    async def test_returns_false_when_not_exists(self):
        session = _make_session(scalar_value=False)
        repo = _make_repo(session)
        result = await repo.check_duplicate(1, date(2024, 1, 1), 50.0)
        assert result is False

    async def test_returns_false_on_none(self):
        session = _make_session(scalar_value=None)
        repo = _make_repo(session)
        result = await repo.check_duplicate(1, date(2024, 1, 1), 50.0)
        assert result is False


# ---------------------------------------------------------------------------
# get_son_km
# ---------------------------------------------------------------------------


class TestGetSonKm:
    async def test_returns_int_when_found(self):
        session = _make_session(scalar_value=150000)
        repo = _make_repo(session)
        result = await repo.get_son_km(1)
        assert result == 150000

    async def test_returns_none_when_no_records(self):
        session = _make_session(scalar_value=None)
        repo = _make_repo(session)
        result = await repo.get_son_km(999)
        assert result is None


# ---------------------------------------------------------------------------
# update_yakit
# ---------------------------------------------------------------------------


class TestUpdateYakit:
    async def test_update_allowed_fields_only(self):
        session = _make_session()
        repo = _make_repo(session)

        update_calls = []

        async def _spy_update(id, **kwargs):
            update_calls.append((id, kwargs))
            return True

        repo.update = _spy_update

        await repo.update_yakit(
            1,
            tarih=date(2024, 1, 1),
            istasyon="Shell",
            fiyat_tl=10.0,
            litre=50.0,
            nonexistent_field="dropped",
        )

        assert len(update_calls) == 1
        _, kwargs = update_calls[0]
        assert "nonexistent_field" not in kwargs
        assert "tarih" in kwargs

    async def test_update_computes_toplam_tutar(self):
        session = _make_session()
        repo = _make_repo(session)

        captured = {}

        async def _spy_update(id, **kwargs):
            captured.update(kwargs)
            return True

        repo.update = _spy_update

        await repo.update_yakit(1, fiyat_tl=12.0, litre=40.0)

        assert "toplam_tutar" in captured
        assert captured["toplam_tutar"] == pytest.approx(480.0, abs=0.01)

    async def test_update_without_price_litre_no_toplam_tutar(self):
        session = _make_session()
        repo = _make_repo(session)

        captured = {}

        async def _spy_update(id, **kwargs):
            captured.update(kwargs)
            return True

        repo.update = _spy_update

        await repo.update_yakit(1, istasyon="BP")
        assert "toplam_tutar" not in captured


# ---------------------------------------------------------------------------
# get_fuel_periods
# ---------------------------------------------------------------------------


class TestGetFuelPeriods:
    async def test_returns_list(self):
        rows = [{"id": 1, "arac_id": 1}, {"id": 2, "arac_id": 1}]
        session = _make_session(rows=rows)
        repo = _make_repo(session)
        result = await repo.get_fuel_periods(arac_id=1, limit=10)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    async def test_returns_all_keys(self):
        # Two execute_query calls; first returns fuel stats, second distance
        call_count = 0

        fuel_row = {
            "total_consumption": 1000.0,
            "total_cost": 10000.0,
            "avg_price": 10.0,
        }
        dist_row = {"total_distance": 5000.0}

        session = AsyncMock()

        async def execute_side_effect(stmt, params=None):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            # Both calls go through execute_query which uses mappings().all()
            if call_count == 1:
                mock_result.mappings.return_value.all.return_value = [fuel_row]
            else:
                mock_result.mappings.return_value.all.return_value = [dist_row]
            mock_result.scalar.return_value = None
            return mock_result

        session.execute = execute_side_effect
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = _make_repo(session)
        result = await repo.get_stats()

        assert "total_consumption" in result
        assert "total_cost" in result
        assert "avg_consumption" in result
        assert "avg_price" in result
        assert "total_distance" in result

    async def test_avg_consumption_computed(self):
        call_count = 0

        session = AsyncMock()

        async def execute_side_effect(stmt, params=None):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.mappings.return_value.all.return_value = [
                    {
                        "total_consumption": 400.0,
                        "total_cost": 4000.0,
                        "avg_price": 10.0,
                    }
                ]
            else:
                mock_result.mappings.return_value.all.return_value = [
                    {"total_distance": 2000.0}
                ]
            mock_result.scalar.return_value = None
            return mock_result

        session.execute = execute_side_effect
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = _make_repo(session)
        result = await repo.get_stats()

        # 400L / 2000km * 100 = 20 L/100km
        assert result["avg_consumption"] == pytest.approx(20.0, abs=0.01)

    async def test_zero_distance_gives_zero_consumption(self):
        call_count = 0

        session = AsyncMock()

        async def execute_side_effect(stmt, params=None):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.mappings.return_value.all.return_value = [
                    {
                        "total_consumption": 200.0,
                        "total_cost": 2000.0,
                        "avg_price": 10.0,
                    }
                ]
            else:
                mock_result.mappings.return_value.all.return_value = [
                    {"total_distance": 0.0}
                ]
            mock_result.scalar.return_value = None
            return mock_result

        session.execute = execute_side_effect
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = _make_repo(session)
        result = await repo.get_stats()
        assert result["avg_consumption"] == 0.0

    async def test_no_fuel_rows_returns_zeros(self):
        call_count = 0

        session = AsyncMock()

        async def execute_side_effect(stmt, params=None):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.mappings.return_value.all.return_value = [
                    {"total_consumption": None, "total_cost": None, "avg_price": None}
                ]
            else:
                mock_result.mappings.return_value.all.return_value = []
            mock_result.scalar.return_value = None
            return mock_result

        session.execute = execute_side_effect
        session.add = MagicMock()
        session.flush = AsyncMock()

        repo = _make_repo(session)
        result = await repo.get_stats()
        assert result["total_consumption"] == 0.0
        assert result["total_cost"] == 0.0


# ---------------------------------------------------------------------------
# get_by_date_range
# ---------------------------------------------------------------------------


class TestGetByDateRange:
    async def test_returns_list(self):
        rows = [{"id": 1, "plaka": "34 AB 1234"}]
        session = _make_session(rows=rows)
        repo = _make_repo(session)
        result = await repo.get_by_date_range(
            start=date(2024, 1, 1), end=date(2024, 12, 31)
        )
        assert isinstance(result, list)

    async def test_accepts_string_dates(self):
        session = _make_session(rows=[])
        repo = _make_repo(session)
        result = await repo.get_by_date_range(start="2024-01-01", end="2024-06-30")
        assert isinstance(result, list)

    async def test_filters_by_arac_id(self):
        session = _make_session(rows=[{"id": 1}])
        repo = _make_repo(session)
        result = await repo.get_by_date_range(
            start=date(2024, 1, 1), end=date(2024, 12, 31), arac_id=7
        )
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# save_fuel_periods
# ---------------------------------------------------------------------------


class TestSaveFuelPeriods:
    async def test_empty_periods_returns_zero(self):
        session = _make_session()
        repo = _make_repo(session)
        result = await repo.save_fuel_periods([])
        assert result == 0

    async def test_saves_periods_returns_count(self):
        session = _make_session()
        repo = _make_repo(session)

        period = MagicMock()
        period.arac_id = 1
        period.alim1_id = 10
        period.alim2_id = 11
        period.alim1_tarih = date(2024, 1, 1)
        period.alim2_tarih = date(2024, 1, 31)
        period.alim1_km = 100000
        period.alim2_km = 101000
        period.alim1_litre = 0.0
        period.ara_mesafe = 1000.0
        period.toplam_yakit = 35.0
        period.ort_tuketim = 3.5
        period.durum = "OK"

        result = await repo.save_fuel_periods([period])
        assert result == 1

    async def test_clear_existing_deletes_before_insert(self):
        session = _make_session()
        repo = _make_repo(session)

        period = MagicMock()
        period.arac_id = 2
        period.alim1_id = 1
        period.alim2_id = 2
        period.alim1_tarih = date(2024, 2, 1)
        period.alim2_tarih = date(2024, 2, 28)
        period.alim1_km = 50000
        period.alim2_km = 51000
        period.alim1_litre = 0.0
        period.ara_mesafe = 1000.0
        period.toplam_yakit = 30.0
        period.ort_tuketim = 3.0
        period.durum = "OK"

        result = await repo.save_fuel_periods([period], clear_existing=True)
        assert result == 1
        # execute should have been called (for DELETE + INSERT)
        session.execute.assert_called()


# ---------------------------------------------------------------------------
# get_yakit_repo factory
# ---------------------------------------------------------------------------


class TestGetYakitRepoFactory:
    def test_returns_new_instance_with_session(self):
        session = _make_session()
        repo = get_yakit_repo(session=session)
        assert isinstance(repo, YakitRepository)
        assert repo._session is session

    def test_returns_singleton_without_session(self):
        import v2.modules.fuel.infrastructure.repository as mod

        mod._yakit_repo = None
        repo1 = get_yakit_repo()
        repo2 = get_yakit_repo()
        assert repo1 is repo2
