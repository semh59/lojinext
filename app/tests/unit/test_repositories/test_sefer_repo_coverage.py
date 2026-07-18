"""SeferRepository comprehensive unit tests — targets missing lines 49-843.

Covers:
- get_all (lines 49-148): filters, ordering, flattening, include_inactive
- get_by_id / get_by_id_with_details (lines 252-279)
- count_all / count_today (lines 281-324)
- update_sefer / delete / add (lines 326-393)
- get_by_sefer_no (lines 395-407)
- get_fuel_performance_analytics (lines 499-623)
- refresh_stats_mv (lines 635-659)
- get_by_date_range (lines 661-686)
- set_onay_durumu (lines 688-714)
- get_by_onay_durumu (lines 716-732)
- get_by_sofor_id (lines 734-747)
- get_with_route_analysis (lines 749-777)
- get_driver_trips_with_route_analysis (lines 779-815)
- get_driver_trips_by_route_type (lines 817-854)
"""

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return a SeferRepository with a mocked async session."""
    from v2.modules.trip.infrastructure.repository import SeferRepository

    repo = SeferRepository.__new__(SeferRepository)
    mock_session = session if session is not None else AsyncMock()
    repo._session = mock_session
    return repo


def _mock_execute(repo, return_value):
    """Wire repo.session.execute to return *return_value*."""
    repo._session.execute = AsyncMock(return_value=return_value)
    return repo


def _scalars_result(rows):
    """Build a mock result whose .scalars().unique().all() and .scalars().all() return rows."""
    # Build from the inside out to avoid Python 3.14 mock chaining issues
    first_val = rows[0] if rows else None

    # Inner unique chain: scalars().unique().all() -> rows
    unique_chain = MagicMock()
    unique_chain.all = MagicMock(return_value=rows)

    # scalars() mock: supports .unique().all(), .all(), .first()
    scalars_mock = MagicMock()
    scalars_mock.unique = MagicMock(return_value=unique_chain)
    scalars_mock.all = MagicMock(return_value=rows)
    scalars_mock.first = MagicMock(return_value=first_val)

    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=scalars_mock)
    return mock_result


def _scalar_result(value):
    """Build a mock result whose .scalar() returns value."""
    mock_result = MagicMock()
    mock_result.scalar.return_value = value
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


class _FakeArac:
    def __init__(self, plaka):
        self.plaka = plaka


class _FakeSofor:
    def __init__(self, ad_soyad):
        self.ad_soyad = ad_soyad


class _FakeDorse:
    def __init__(self, plaka):
        self.plaka = plaka


class _FakeGuzergah:
    def __init__(self, cikis_yeri, varis_yeri):
        self.cikis_yeri = cikis_yeri
        self.varis_yeri = varis_yeri


class _FakeSefer:
    """Minimal fake Sefer ORM row — avoids MagicMock.__dict__ pitfalls."""

    def __init__(
        self,
        id=1,
        tarih=date(2024, 3, 1),
        cikis_yeri="Ankara",
        varis_yeri="Konya",
        sefer_no="S-001",
        plaka="34ABC01",
        sofor_adi="Ali Veli",
        dorse_plakasi="34TRL01",
        has_guzergah=False,
    ):
        self.id = id
        self.tarih = tarih
        self.cikis_yeri = cikis_yeri
        self.varis_yeri = varis_yeri
        self.sefer_no = sefer_no
        self.arac = _FakeArac(plaka)
        self.sofor = _FakeSofor(sofor_adi)
        self.dorse = _FakeDorse(dorse_plakasi)
        self.guzergah = _FakeGuzergah(cikis_yeri, varis_yeri) if has_guzergah else None
        # _sa_instance_state must be present so the repo's .pop() works
        self._sa_instance_state = object()


def _make_sefer_orm(**kwargs):
    """Build a minimal fake Sefer ORM object."""
    return _FakeSefer(**kwargs)


# ---------------------------------------------------------------------------
# get_all  (lines 49-148)
# ---------------------------------------------------------------------------


class TestGetAll:
    async def test_returns_list(self):
        repo = _make_repo()
        sefer = _make_sefer_orm()
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()

        assert isinstance(result, list)
        assert len(result) == 1

    async def test_flattens_arac_plaka(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(plaka="06TIR99")
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()
        assert result[0]["plaka"] == "06TIR99"

    async def test_flattens_sofor_adi(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(sofor_adi="Mehmet Yıldız")
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()
        assert result[0]["sofor_adi"] == "Mehmet Yıldız"

    async def test_guzergah_adi_without_guzergah(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(
            cikis_yeri="Bursa", varis_yeri="İzmir", has_guzergah=False
        )
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()
        assert result[0]["guzergah_adi"] == "Bursa - İzmir"

    async def test_guzergah_adi_with_guzergah(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(
            cikis_yeri="Bursa", varis_yeri="İzmir", has_guzergah=True
        )
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()
        assert "Bursa" in result[0]["guzergah_adi"]
        assert "İzmir" in result[0]["guzergah_adi"]

    async def test_filters_dict_overrides_params(self):
        """When filters dict is passed, it should override keyword params."""
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(filters={"arac_id": 5, "sofor_id": 3})
        # Should not raise; execute was called
        repo._session.execute.assert_called_once()

    async def test_tarih_string_coercion(self):
        """String tarih values must be coerced to date objects."""
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(filters={"tarih": "2024-05-01"})
        repo._session.execute.assert_called_once()

    async def test_asc_ordering(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(desc=False)
        repo._session.execute.assert_called_once()

    async def test_search_filter(self):
        """search executes the driver-name trigram lookup (Tier E madde 26,
        Sofor.ad_soyad is encrypted at rest) plus the main filtered SELECT."""
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(search="Ankara")
        assert repo._session.execute.call_count == 2

    async def test_durum_filter(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(durum="Tamamlandı")
        repo._session.execute.assert_called_once()

    async def test_include_inactive_false_excludes_iptal(self):
        """include_inactive=False (default) should add durum != İptal clause."""
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(include_inactive=False)
        repo._session.execute.assert_called_once()

    async def test_include_inactive_true(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(include_inactive=True)
        repo._session.execute.assert_called_once()

    async def test_onay_durumu_filter_via_filters_dict(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(filters={"onay_durumu": "Bekliyor"})
        repo._session.execute.assert_called_once()

    async def test_no_arac_no_sofor_no_dorse(self):
        """Sefer without relations should produce None values for plaka etc."""
        repo = _make_repo()
        sefer = _make_sefer_orm()
        # Override relations to None on the plain object
        sefer.arac = None
        sefer.sofor = None
        sefer.dorse = None
        sefer.guzergah = None

        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_all()
        assert result[0]["plaka"] is None
        assert result[0]["sofor_adi"] is None
        assert result[0]["dorse_plakasi"] is None


# ---------------------------------------------------------------------------
# get_by_id  (lines 252-275)
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_returns_dict_when_found(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(id=42)
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(42)
        assert result is not None
        assert result["id"] == 42

    async def test_returns_none_when_not_found(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(999)
        assert result is None

    async def test_flattens_arac_plaka(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(plaka="34TEST")
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(1)
        assert result["plaka"] == "34TEST"

    async def test_guzergah_adi_with_guzergah_relation(self):
        repo = _make_repo()
        sefer = _make_sefer_orm(cikis_yeri="Ank", varis_yeri="Kon", has_guzergah=True)
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(1)
        assert "Ank" in result["guzergah_adi"]

    async def test_get_by_id_with_details_delegates(self):
        """get_by_id_with_details must call get_by_id."""
        repo = _make_repo()
        sefer = _make_sefer_orm(id=7)
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id_with_details(7)
        assert result is not None
        assert result["id"] == 7


# ---------------------------------------------------------------------------
# count_all / count_today  (lines 281-324)
# ---------------------------------------------------------------------------


class TestCounts:
    async def test_count_all_basic(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(15))
        result = await repo.count_all()
        assert result == 15

    async def test_count_all_none_returns_zero(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(None))
        result = await repo.count_all()
        assert result == 0

    async def test_count_all_with_filters(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(5))
        result = await repo.count_all(
            filters={
                "durum": "Tamamlandı",
                "arac_id": 1,
                "sofor_id": 2,
                "onay_durumu": "Onaylandı",
            }
        )
        assert result == 5

    async def test_count_all_include_inactive(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(20))
        result = await repo.count_all(include_inactive=True)
        assert result == 20

    async def test_count_today_returns_int(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(4))
        result = await repo.count_today()
        assert result == 4

    async def test_count_today_with_explicit_date(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(2))
        result = await repo.count_today(today=date(2024, 6, 1))
        assert result == 2

    async def test_count_today_none_returns_zero(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_result(None))
        result = await repo.count_today()
        assert result == 0


# ---------------------------------------------------------------------------
# update_sefer / delete  (lines 326-332)
# ---------------------------------------------------------------------------


class TestUpdateDelete:
    async def test_update_sefer_delegates_to_update(self):
        repo = _make_repo()
        # update() needs session.execute and flush
        mock_obj = MagicMock()
        mock_obj.__table__ = MagicMock()
        mock_obj.__table__.columns = [MagicMock(name="durum")]
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = MagicMock()
        repo._session.execute = AsyncMock(return_value=execute_result)
        repo._session.flush = AsyncMock()

        # Patch update to avoid going deep into ORM
        from unittest.mock import patch as _patch

        with _patch.object(
            repo, "update", new=AsyncMock(return_value=True)
        ) as mock_update:
            result = await repo.update_sefer(5, durum="Tamamlandı")
            mock_update.assert_called_once_with(5, durum="Tamamlandı")
            assert result is True

    async def test_delete_calls_update_is_deleted(self):
        repo = _make_repo()
        with patch.object(
            repo, "update", new=AsyncMock(return_value=True)
        ) as mock_update:
            result = await repo.delete(3)
            mock_update.assert_called_once_with(3, is_deleted=True)
            assert result is True


# ---------------------------------------------------------------------------
# add  (lines 334-393)
# ---------------------------------------------------------------------------


class TestAdd:
    async def test_add_returns_id(self):
        repo = _make_repo()
        repo._session.add = MagicMock()
        repo._session.flush = AsyncMock()

        mock_sefer = MagicMock()
        mock_sefer.id = 99

        with patch(
            "v2.modules.trip.infrastructure.repository.Sefer", return_value=mock_sefer
        ):
            result = await repo.add(
                tarih=date(2024, 1, 1),
                arac_id=1,
                sofor_id=2,
                cikis_yeri="Ankara",
                varis_yeri="Konya",
                mesafe_km=250.0,
                sefer_no="S-TEST-01",
                bos_agirlik_kg=12000,
                dolu_agirlik_kg=30000,
                net_kg=18000,
            )
        assert result == 99

    async def test_add_filters_unknown_keys(self):
        """Keys not in the allowed set should be silently dropped."""
        repo = _make_repo()
        repo._session.add = MagicMock()
        repo._session.flush = AsyncMock()

        mock_sefer = MagicMock()
        mock_sefer.id = 11

        with patch(
            "v2.modules.trip.infrastructure.repository.Sefer", return_value=mock_sefer
        ):
            result = await repo.add(
                tarih=date(2024, 1, 1),
                arac_id=1,
                unknown_field="should_be_dropped",
                cikis_yeri="X",
                varis_yeri="Y",
                mesafe_km=100,
                bos_agirlik_kg=10000,
                dolu_agirlik_kg=20000,
                net_kg=10000,
            )
        assert result == 11

    async def test_add_raises_value_error_on_duplicate_sefer_no(self):
        """IntegrityError with 'sefer_no' in message → ValueError."""
        from sqlalchemy.exc import IntegrityError

        repo = _make_repo()
        repo._session.add = MagicMock()

        orig_exc = Exception("duplicate key value violates unique constraint sefer_no")
        ie = IntegrityError(statement="INSERT", params={}, orig=orig_exc)

        repo._session.flush = AsyncMock(side_effect=ie)

        mock_sefer = MagicMock()
        mock_sefer.id = None

        with patch(
            "v2.modules.trip.infrastructure.repository.Sefer", return_value=mock_sefer
        ):
            with pytest.raises(ValueError, match="sefer numarası"):
                await repo.add(
                    tarih=date(2024, 1, 1),
                    arac_id=1,
                    cikis_yeri="A",
                    varis_yeri="B",
                    mesafe_km=100,
                    sefer_no="DUPLICATE",
                    bos_agirlik_kg=10000,
                    dolu_agirlik_kg=20000,
                    net_kg=10000,
                )

    async def test_add_re_raises_non_sefer_no_integrity_error(self):
        """IntegrityError without 'sefer_no' in message → re-raised as-is."""
        from sqlalchemy.exc import IntegrityError

        repo = _make_repo()
        repo._session.add = MagicMock()

        orig_exc = Exception("some other constraint violation")
        ie = IntegrityError(statement="INSERT", params={}, orig=orig_exc)

        repo._session.flush = AsyncMock(side_effect=ie)

        mock_sefer = MagicMock()
        mock_sefer.id = None

        with patch(
            "v2.modules.trip.infrastructure.repository.Sefer", return_value=mock_sefer
        ):
            with pytest.raises(IntegrityError):
                await repo.add(
                    tarih=date(2024, 1, 1),
                    arac_id=1,
                    cikis_yeri="A",
                    varis_yeri="B",
                    mesafe_km=100,
                    bos_agirlik_kg=10000,
                    dolu_agirlik_kg=20000,
                    net_kg=10000,
                )

    async def test_add_accepts_positional_dict(self):
        """add() accepts data as positional dict argument."""
        repo = _make_repo()
        repo._session.add = MagicMock()
        repo._session.flush = AsyncMock()

        mock_sefer = MagicMock()
        mock_sefer.id = 55

        with patch(
            "v2.modules.trip.infrastructure.repository.Sefer", return_value=mock_sefer
        ):
            result = await repo.add(
                {
                    "tarih": date(2024, 2, 1),
                    "arac_id": 2,
                    "cikis_yeri": "C",
                    "varis_yeri": "D",
                    "mesafe_km": 300,
                    "bos_agirlik_kg": 10000,
                    "dolu_agirlik_kg": 20000,
                    "net_kg": 10000,
                }
            )
        assert result == 55


# ---------------------------------------------------------------------------
# get_by_sefer_no  (lines 395-407)
# ---------------------------------------------------------------------------


class _SimpleSeferRow:
    """Plain object with __dict__ for get_by_sefer_no (avoids MagicMock.__dict__ issues)."""

    def __init__(self, **kwargs):
        self._sa_instance_state = object()
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestGetBySeferNo:
    async def test_returns_dict_when_found(self):
        repo = _make_repo()
        sefer = _SimpleSeferRow(id=1, sefer_no="S-001")
        mock_result = _scalars_result([sefer])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_sefer_no("S-001")
        assert result is not None
        assert result["sefer_no"] == "S-001"
        assert "_sa_instance_state" not in result

    async def test_returns_none_when_not_found(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_sefer_no("NONEXISTENT")
        assert result is None


# ---------------------------------------------------------------------------
# get_fuel_performance_analytics  (lines 499-623)
# ---------------------------------------------------------------------------


def _paired_row(
    id=1, tarih=date(2024, 1, 1), tuketim=35.0, tahmini_tuketim=33.0, mesafe_km=250.0
):
    r = MagicMock()
    r.id = id
    r.tarih = tarih
    r.tuketim = tuketim
    r.tahmini_tuketim = tahmini_tuketim
    r.mesafe_km = mesafe_km
    return r


class TestFuelPerformanceAnalytics:
    async def test_raises_for_invalid_durum(self):
        repo = _make_repo()
        with pytest.raises(ValueError, match="Geçersiz durum"):
            await repo.get_fuel_performance_analytics(durum="YANLIS")

    async def test_empty_dataset_returns_low_data_true(self):
        repo = _make_repo()

        empty_result = MagicMock()
        empty_result.fetchall.return_value = []

        repo._session.execute = AsyncMock(return_value=empty_result)

        result = await repo.get_fuel_performance_analytics()

        assert result["low_data"] is True
        assert result["kpis"]["total_compared"] == 0
        assert result["kpis"]["mae"] == 0.0

    async def test_with_paired_data_computes_mae_rmse(self):
        repo = _make_repo()

        paired = [_paired_row(tuketim=35.0, tahmini_tuketim=30.0)]
        trend_rows = [MagicMock(tarih=date(2024, 1, 10), tuketim=35.0)]
        dist_rows = [MagicMock(tuketim=35.0)]

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.fetchall.return_value = paired
            elif call_count == 2:
                mock_result.fetchall.return_value = trend_rows
            else:
                mock_result.fetchall.return_value = dist_rows
            return mock_result

        repo._session.execute = AsyncMock(side_effect=side_effect)

        result = await repo.get_fuel_performance_analytics()

        assert result["kpis"]["total_compared"] == 1
        assert result["kpis"]["mae"] == pytest.approx(5.0, abs=0.01)
        assert result["kpis"]["rmse"] == pytest.approx(5.0, abs=0.01)

    async def test_outliers_populated_for_high_deviation(self):
        """Pairs with >20% deviation must appear in outliers list."""
        repo = _make_repo()

        # 35 actual, 10 predicted → ~71% deviation → outlier
        paired = [_paired_row(tuketim=35.0, tahmini_tuketim=10.0)]
        trend_rows = []
        dist_rows = []

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.fetchall.return_value = paired
            elif call_count == 2:
                mock_result.fetchall.return_value = trend_rows
            else:
                mock_result.fetchall.return_value = dist_rows
            return mock_result

        repo._session.execute = AsyncMock(side_effect=side_effect)

        result = await repo.get_fuel_performance_analytics()
        assert len(result["outliers"]) == 1
        assert result["outliers"][0]["deviation_pct"] > 20

    async def test_filter_params_passed(self):
        """Method accepts all filter params without raising."""
        repo = _make_repo()

        empty_result = MagicMock()
        empty_result.fetchall.return_value = []
        repo._session.execute = AsyncMock(return_value=empty_result)

        result = await repo.get_fuel_performance_analytics(
            durum="Tamamlandı",
            baslangic_tarih=date(2024, 1, 1),
            bitis_tarih=date(2024, 12, 31),
            arac_id=1,
            sofor_id=2,
            search="test",
        )
        assert isinstance(result, dict)

    async def test_trend_weekly_bucketing(self):
        """Trend entries are grouped by ISO week."""
        repo = _make_repo()

        paired_rows = []
        trend_rows = [
            MagicMock(tarih=date(2024, 1, 8), tuketim=32.0),
            MagicMock(tarih=date(2024, 1, 9), tuketim=34.0),
            MagicMock(tarih=date(2024, 1, 15), tuketim=36.0),
        ]
        dist_rows = []

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.fetchall.return_value = paired_rows
            elif call_count == 2:
                mock_result.fetchall.return_value = trend_rows
            else:
                mock_result.fetchall.return_value = dist_rows
            return mock_result

        repo._session.execute = AsyncMock(side_effect=side_effect)

        result = await repo.get_fuel_performance_analytics()
        # Two distinct weeks should produce 2 trend entries
        assert len(result["trend"]) == 2

    async def test_distribution_histogram(self):
        """Distribution buckets are built correctly."""
        repo = _make_repo()

        paired_rows = []
        trend_rows = []
        dist_rows = [
            MagicMock(tuketim=32.0),
            MagicMock(tuketim=34.0),
            MagicMock(tuketim=37.0),
        ]

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.fetchall.return_value = paired_rows
            elif call_count == 2:
                mock_result.fetchall.return_value = trend_rows
            else:
                mock_result.fetchall.return_value = dist_rows
            return mock_result

        repo._session.execute = AsyncMock(side_effect=side_effect)

        result = await repo.get_fuel_performance_analytics()
        assert len(result["distribution"]) > 0
        for entry in result["distribution"]:
            assert "range" in entry
            assert "count" in entry


# ---------------------------------------------------------------------------
# refresh_stats_mv  (lines 635-659)
# ---------------------------------------------------------------------------


class TestRefreshStatsMv:
    async def test_success_path(self):
        # AUDIT-013: refresh_stats_mv artık session.execute DEĞİL, engine düzeyinde
        # isolation_level='AUTOCOMMIT' ile açılan bağımsız bağlantı kullanır
        # (CONCURRENTLY transaction dışında çalışmalı).
        repo = _make_repo()
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.execution_options.return_value.connect.return_value = mock_conn

        with patch("app.database.connection.engine", mock_engine):
            await repo.refresh_stats_mv()

        mock_conn.execute.assert_called_once()
        mock_engine.execution_options.assert_called_once_with(
            isolation_level="AUTOCOMMIT"
        )

    async def test_fallback_on_concurrent_failure(self):
        """When CONCURRENTLY refresh fails, should try non-concurrent then log."""
        repo = _make_repo()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("CONCURRENTLY not supported")
            elif call_count == 2:
                # rollback
                return MagicMock()
            else:
                # fallback non-concurrent
                return MagicMock()

        repo._session.execute = AsyncMock(side_effect=side_effect)
        repo._session.rollback = AsyncMock(return_value=None)

        # Should not raise — fallback handles the error
        await repo.refresh_stats_mv()

    async def test_silent_skip_when_mv_missing(self):
        """Both refresh attempts fail → silent debug log, no exception propagated."""
        repo = _make_repo()

        async def fail_execute(*args, **kwargs):
            raise Exception("relation does not exist")

        repo._session.execute = AsyncMock(side_effect=fail_execute)
        repo._session.rollback = AsyncMock(return_value=None)

        # Must not raise
        await repo.refresh_stats_mv()


# ---------------------------------------------------------------------------
# get_by_date_range  (lines 661-686)
# ---------------------------------------------------------------------------


class TestGetByDateRange:
    async def test_basic_call(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=MagicMock())

        # execute_query does the actual call — patch it
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            result = await repo.get_by_date_range(
                start=date(2024, 1, 1), end=date(2024, 1, 31)
            )
            mock_eq.assert_called_once()
            assert isinstance(result, list)

    async def test_with_arac_id(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_by_date_range(
                start=date(2024, 1, 1), end=date(2024, 1, 31), arac_id=5
            )
            call_kwargs = mock_eq.call_args
            # Params dict should contain arac_id
            params = call_kwargs[0][1]
            assert params.get("arac_id") == 5

    async def test_string_dates_coerced(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_by_date_range(start="2024-03-01", end="2024-03-31")
            mock_eq.assert_called_once()


# ---------------------------------------------------------------------------
# set_onay_durumu  (lines 688-714)
# ---------------------------------------------------------------------------


def _make_get_session_with(sefer_mock):
    """Return an async context manager that yields a mock session with sefer."""

    @asynccontextmanager
    async def _get_session(self_inner=None):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = sefer_mock
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        yield session

    return _get_session


class TestSetOnayDurumu:
    async def test_returns_none_when_not_found(self):
        repo = _make_repo()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.set_onay_durumu(999, "Onaylandı")
        assert result is None

    async def test_returns_same_dict_when_durum_unchanged(self):
        repo = _make_repo()
        sefer = MagicMock()
        sefer.onay_durumu = "Onaylandı"
        sefer.notlar = None

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = sefer
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session
        repo._to_dict = MagicMock(return_value={"onay_durumu": "Onaylandı"})

        result = await repo.set_onay_durumu(1, "Onaylandı")
        assert result == {"onay_durumu": "Onaylandı"}

    async def test_updates_onay_durumu_and_note(self):
        repo = _make_repo()
        sefer = MagicMock()
        sefer.onay_durumu = "Bekliyor"
        sefer.notlar = ""
        repo._session = None  # simulate outside UoW so commit runs

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = sefer
            session.execute = AsyncMock(return_value=result)
            session.commit = AsyncMock()
            yield session

        repo._get_session = fake_get_session
        repo._to_dict = MagicMock(return_value={"onay_durumu": "Onaylandı"})

        result = await repo.set_onay_durumu(1, "Onaylandı", onay_notu="İncelendi")
        assert result == {"onay_durumu": "Onaylandı"}
        assert "İncelendi" in sefer.notlar


# ---------------------------------------------------------------------------
# get_by_onay_durumu  (lines 716-732)
# ---------------------------------------------------------------------------


class TestGetByOnayDurumu:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()

        # AUDIT-034: joinedload + result.unique().scalars().all(); satır s.__dict__
        # üzerinden plaka/sofor_adi/guzergah ile zenginleştirilir (N+1 re-fetch yok).
        class _FakeSefer:
            def __init__(self):
                self._sa_instance_state = None
                self.id = 1
                self.onay_durumu = "Bekliyor"
                self.cikis_yeri = "Istanbul"
                self.varis_yeri = "Ankara"
                self.arac = None
                self.sofor = None
                self.dorse = None
                self.guzergah = None

        sefer = _FakeSefer()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.unique.return_value.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_by_onay_durumu("Bekliyor")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["guzergah_adi"] == "Istanbul - Ankara"

    async def test_empty_list_when_none_found(self):
        repo = _make_repo()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.unique.return_value.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_by_onay_durumu("Onaylandı")
        assert result == []


# ---------------------------------------------------------------------------
# get_by_sofor_id  (lines 734-747)
# ---------------------------------------------------------------------------


class TestGetBySoforId:
    async def test_basic(self):
        repo = _make_repo()
        sefer = MagicMock()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session
        repo._to_dict = MagicMock(return_value={"id": 1})

        result = await repo.get_by_sofor_id(sofor_id=3)
        assert isinstance(result, list)

    async def test_with_onay_durumu_filter(self):
        repo = _make_repo()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_by_sofor_id(sofor_id=3, onay_durumu="Onaylandı")
        assert result == []


# ---------------------------------------------------------------------------
# get_with_route_analysis  (lines 749-777)
# ---------------------------------------------------------------------------


class TestGetWithRouteAnalysis:
    async def test_returns_list(self):
        repo = _make_repo()
        sefer = MagicMock()
        sefer.id = 10
        sefer.mesafe_km = 300.0
        sefer.rota_detay = {"route_analysis": {"type": "highway"}}
        sefer.tuketim = 35.0

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_with_route_analysis(days=90)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == 10
        assert result[0]["mesafe_km"] == 300.0

    async def test_rota_detay_fallback_to_whole_dict(self):
        """If rota_detay has no 'route_analysis' key, use the whole dict."""
        repo = _make_repo()
        sefer = MagicMock()
        sefer.id = 11
        sefer.mesafe_km = 200.0
        sefer.rota_detay = {"some_other_key": "value"}
        sefer.tuketim = 30.0

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_with_route_analysis()
        assert result[0]["route_analysis"] == {"some_other_key": "value"}

    async def test_none_rota_detay_returns_empty_dict(self):
        repo = _make_repo()
        sefer = MagicMock()
        sefer.id = 12
        sefer.mesafe_km = 100.0
        sefer.rota_detay = None
        sefer.tuketim = 28.0

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_with_route_analysis()
        assert result[0]["route_analysis"] == {}


# ---------------------------------------------------------------------------
# get_driver_trips_with_route_analysis  (lines 779-815)
# ---------------------------------------------------------------------------


class TestGetDriverTripsWithRouteAnalysis:
    async def test_basic(self):
        repo = _make_repo()
        sefer = MagicMock()
        sefer.id = 20
        sefer.tuketim = 34.0
        sefer.tahmini_tuketim = 32.0
        sefer.rota_detay = {}

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = [sefer]
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_driver_trips_with_route_analysis(sofor_id=5)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["gercek_tuketim"] == 34.0
        assert result[0]["tahmini_tuketim"] == 32.0

    async def test_empty_result(self):
        repo = _make_repo()

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_driver_trips_with_route_analysis(sofor_id=99)
        assert result == []


# ---------------------------------------------------------------------------
# get_driver_trips_by_route_type  (lines 817-854)
# ---------------------------------------------------------------------------


class _FakeDriverSefer:
    """Minimal sefer-like object for driver route tests."""

    def __init__(self, id, tuketim, tahmini_tuketim, rota_detay):
        self.id = id
        self.tuketim = tuketim
        self.tahmini_tuketim = tahmini_tuketim
        self.rota_detay = rota_detay


class TestGetDriverTripsByRouteType:
    async def test_filters_by_classify_route(self):
        """Only trips whose rota_detay classifies to matching route_type are returned."""
        repo = _make_repo()

        sefer_match = _FakeDriverSefer(
            30, 33.0, 31.0, {"route_analysis": {"primary_type": "highway"}}
        )
        sefer_no_match = _FakeDriverSefer(
            31, 40.0, 38.0, {"route_analysis": {"primary_type": "city"}}
        )

        rows = [sefer_match, sefer_no_match]

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars = MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=rows))
            )
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        with patch(
            "v2.modules.driver.public.classify_route",
            side_effect=lambda rd: "highway"
            if rd.get("primary_type") == "highway"
            else "city",
        ):
            result = await repo.get_driver_trips_by_route_type(
                sofor_id=5, route_type="highway"
            )

        assert len(result) == 1
        assert result[0]["id"] == 30

    async def test_empty_when_no_matching_type(self):
        repo = _make_repo()
        sefer = _FakeDriverSefer(32, 33.0, 31.0, {})

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            result = MagicMock()
            result.scalars = MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[sefer]))
            )
            session.execute = AsyncMock(return_value=result)
            yield session

        repo._get_session = fake_get_session

        with patch(
            "v2.modules.driver.public.classify_route",
            return_value="city",
        ):
            result = await repo.get_driver_trips_by_route_type(
                sofor_id=5, route_type="highway"
            )

        assert result == []


# ---------------------------------------------------------------------------
# Additional coverage for remaining missing lines
# ---------------------------------------------------------------------------


class TestGetAllExtraFilters:
    """Cover string coercion of baslangic_tarih/bitis_tarih (lines 65-67, 93-95)."""

    async def test_baslangic_bitis_tarih_string_coercion(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(
            filters={
                "baslangic_tarih": "2024-01-01",
                "bitis_tarih": "2024-12-31",
            }
        )
        repo._session.execute.assert_called_once()

    async def test_baslangic_bitis_tarih_as_date_objects(self):
        repo = _make_repo()
        mock_result = _scalars_result([])
        repo._session.execute = AsyncMock(return_value=mock_result)

        await repo.get_all(
            baslangic_tarih=date(2024, 1, 1),
            bitis_tarih=date(2024, 12, 31),
        )
        repo._session.execute.assert_called_once()


class TestGetForTraining:
    """Cover get_for_training raw SQL (lines 156-184)."""

    async def test_delegates_to_execute_query(self):
        repo = _make_repo()
        rows = [{"mesafe_km": 250.0, "ton": 18.0, "tuketim": 35.0}]

        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=rows)
        ) as mock_eq:
            result = await repo.get_for_training(arac_id=1)
            mock_eq.assert_called_once()
            assert result == rows

    async def test_custom_limit(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_for_training(arac_id=5, limit=50)
            params = mock_eq.call_args[0][1]
            assert params["limit"] == 50
            assert params["arac_id"] == 5


class TestGetCostLeakageStats:
    """Cover get_cost_leakage_stats (lines 203-239)."""

    async def test_returns_expected_keys(self):
        repo = _make_repo()

        route_scalar_result = MagicMock()
        route_scalar_result.scalar = MagicMock(return_value=50.0)

        fuel_scalar_result = MagicMock()
        fuel_scalar_result.scalar = MagicMock(return_value=100.0)

        call_count = 0

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()

            async def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return route_scalar_result
                return fuel_scalar_result

            session.execute = AsyncMock(side_effect=side_effect)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_cost_leakage_stats(days=30)

        assert "route_deviation_km" in result
        assert "route_deviation_cost" in result
        assert "fuel_gap_liters" in result
        assert "fuel_gap_cost" in result
        assert "total_leakage_cost" in result
        assert result["route_deviation_km"] == 50.0

    async def test_zero_values_when_no_data(self):
        repo = _make_repo()

        zero_result = MagicMock()
        zero_result.scalar = MagicMock(return_value=None)

        @asynccontextmanager
        async def fake_get_session():
            session = AsyncMock()
            session.execute = AsyncMock(return_value=zero_result)
            yield session

        repo._get_session = fake_get_session

        result = await repo.get_cost_leakage_stats()
        assert result["route_deviation_km"] == 0.0
        assert result["fuel_gap_liters"] == 0.0
        assert result["total_leakage_cost"] == 0.0


class TestGetTripStatsExtra:
    """Cover get_trip_stats date-filter branches (lines 424-475)."""

    async def test_with_all_filters(self):
        from app.tests.unit.test_repositories.test_sefer_repo_stats import (
            _make_repo_with_session,
            _make_stats_row,
        )

        repo = _make_repo_with_session()
        row = _make_stats_row()
        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=row)
        repo.session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_trip_stats(
            durum="Tamamlandı",
            baslangic_tarih=date(2024, 1, 1),
            bitis_tarih=date(2024, 12, 31),
        )
        assert result["total_count"] == 10


class TestRefreshStatsMvFallbacks:
    """Cover refresh_stats_mv inner exception paths (lines 647-648, 656-657)."""

    async def test_rollback_fails_silently(self):
        """If rollback itself raises, it should be swallowed."""
        repo = _make_repo()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("CONCURRENTLY fail")
            return MagicMock()

        repo._session.execute = AsyncMock(side_effect=side_effect)
        repo._session.rollback = AsyncMock(side_effect=Exception("rollback fail"))

        await repo.refresh_stats_mv()  # must not raise

    async def test_fallback_mv_refresh_also_fails(self):
        """All refresh attempts fail — error silently logged."""
        repo = _make_repo()

        async def always_fail(*args, **kwargs):
            raise Exception("mv missing")

        repo._session.execute = AsyncMock(side_effect=always_fail)
        repo._session.rollback = AsyncMock(side_effect=Exception("rollback fail"))

        await repo.refresh_stats_mv()  # must not raise


class TestGetSeferRepoFactory:
    """Cover get_sefer_repo factory (line 859)."""

    def test_returns_sefer_repo_instance(self):
        from v2.modules.trip.infrastructure.repository import (
            SeferRepository,
            get_sefer_repo,
        )

        repo = get_sefer_repo()
        assert isinstance(repo, SeferRepository)

    def test_with_session_arg(self):
        from v2.modules.trip.infrastructure.repository import (
            SeferRepository,
            get_sefer_repo,
        )

        mock_session = AsyncMock()
        repo = get_sefer_repo(session=mock_session)
        assert isinstance(repo, SeferRepository)
        assert repo._session is mock_session
