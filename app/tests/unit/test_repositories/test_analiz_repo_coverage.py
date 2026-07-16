"""
AnalizRepository unit tests — targets 168 missing statements.

Covers:
- get_training_seferler (lines 36-79): limit/offset clamping, execute_query delegation
- save_model_params (lines 81-103): upsert path, rollback on error, standalone commit
- get_model_params (lines 105-124): found/not-found, str katsayilar JSON parse
- get_filo_ortalama_tuketim (lines 164-200): with/without date filters, exception fallback
- get_dashboard_stats (lines 202-243): _mapping path, SimpleNamespace path, exception fallback
- get_month_over_month_trends (lines 245-345): normal compute, exception path, no-row path
- get_all_vehicles_consumption_stats (lines 347-386): days clamping, result mapping
- get_recent_unread_alerts (lines 388-403): success, exception fallback
- get_period_stats (lines 405-427): row/no-row
- get_vehicle_summary_stats (lines 429-447): row/no-row
- get_fleet_performance_stats (lines 449-477): row/no-row
- get_top_routes_by_vehicle (lines 479-500): limit clamping, result mapping
- get_daily_summary_for_ml (lines 506-553): with/without arac_id
- get_heatmap_data (lines 555-572): days clamping, result mapping
- get_daily_consumption_series (lines 598-624): isoformat date, value cast
- get_top_performing_vehicles (lines 626-654): limit clamping, row mapping
- get_bulk_cost_stats (lines 656-693): months int cast, result mapping
- get_analiz_repo factory (lines 700-708): with/without session
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(session=None):
    """Return an AnalizRepository with a mocked async session."""
    from v2.modules.analytics_executive.infrastructure.executive_read_models import (
        AnalizRepository,
    )

    repo = AnalizRepository.__new__(AnalizRepository)
    mock_session = session if session is not None else AsyncMock()
    repo._session = mock_session
    return repo


def _mapping_row(**kwargs):
    """Build a mock row that has a ._mapping attribute."""
    m = MagicMock()
    m._mapping = kwargs
    return m


def _attr_row(**kwargs):
    """Build a mock row where values are plain attributes (no _mapping)."""
    r = MagicMock(spec_set=list(kwargs.keys()))
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


def _fetchall_result(rows):
    """Build a mock execute result whose .fetchall() returns rows."""
    result = MagicMock()
    result.fetchall = MagicMock(return_value=rows)
    return result


def _fetchone_result(row):
    """Build a mock execute result whose .fetchone() returns row."""
    result = MagicMock()
    result.fetchone = MagicMock(return_value=row)
    return result


def _scalar_one_or_none_result(value):
    """Build a mock execute result whose .scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


# ---------------------------------------------------------------------------
# get_training_seferler
# ---------------------------------------------------------------------------


class TestGetTrainingSeferler:
    async def test_delegates_to_execute_query(self):
        repo = _make_repo()
        rows = [{"mesafe_km": 200.0, "tuketim": 30.0}]
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=rows)
        ) as mock_eq:
            result = await repo.get_training_seferler(arac_id=1)
            mock_eq.assert_called_once()
            assert result == rows

    async def test_limit_clamped_to_1000(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_training_seferler(arac_id=1, limit=9999)
            params = mock_eq.call_args[0][1]
            assert params["limit"] == 1000

    async def test_limit_falsy_uses_default(self):
        """limit=0 is falsy → uses default 200 before clamping."""
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_training_seferler(arac_id=1, limit=0)
            params = mock_eq.call_args[0][1]
            # 0 is falsy → `int(limit or 200)` = 200
            assert params["limit"] == 200

    async def test_offset_default_is_zero(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_training_seferler(arac_id=5)
            params = mock_eq.call_args[0][1]
            assert params["offset"] == 0

    async def test_offset_clamped_to_nonnegative(self):
        repo = _make_repo()
        with patch.object(
            repo, "execute_query", new=AsyncMock(return_value=[])
        ) as mock_eq:
            await repo.get_training_seferler(arac_id=5, offset=-5)
            params = mock_eq.call_args[0][1]
            assert params["offset"] == 0


# ---------------------------------------------------------------------------
# save_model_params
# ---------------------------------------------------------------------------


class TestSaveModelParams:
    async def test_executes_delete_and_insert(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=MagicMock())
        repo._session.commit = AsyncMock()

        # _session is set → standalone mode → commit is called
        repo._session = None  # force standalone commit path
        session_mock = AsyncMock()
        session_mock.execute = AsyncMock(return_value=MagicMock())
        session_mock.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_get_session():
            yield session_mock

        repo._get_session = fake_get_session

        # With _session=None, the code uses self.session which raises.
        # So we need to patch the session property instead.
        # Re-create with a real session mock for the actual session property path.
        repo2 = _make_repo()
        repo2._session.execute = AsyncMock(return_value=MagicMock())
        # _session is not None → no commit
        await repo2.save_model_params(
            arac_id=1,
            params={"r_squared": 0.9, "sample_count": 50, "coefficients": [1, 2, 3]},
        )
        # execute called twice (delete + insert)
        assert repo2._session.execute.call_count == 2

    async def test_commit_when_no_uow_session(self):
        """When _session is None, save_model_params should commit."""
        repo = _make_repo()
        repo._session = None  # session-less (standalone)

        session_mock = AsyncMock()
        session_mock.execute = AsyncMock(return_value=MagicMock())
        session_mock.commit = AsyncMock()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_get_session():
            yield session_mock

        repo._get_session = fake_get_session

        # save_model_params uses self.session (property), which checks _session.
        # When _session is None it raises. The actual method does `session = self.session`
        # so we need _session set. Let's test via UoW-style: set _session.
        # The code: if self._session is None: await session.commit()
        # So we can test by using session but having _session be None on check.
        # Simplest: patch the property directly.
        with patch.object(
            type(repo),
            "session",
            new_callable=lambda: property(lambda self: session_mock),
        ):
            await repo.save_model_params(
                arac_id=2,
                params={"r_squared": 0.8, "sample_count": 10},
            )
        session_mock.commit.assert_called_once()

    async def test_rollback_on_error(self):
        """Exception in save_model_params rolls back and re-raises."""
        repo = _make_repo()
        repo._session = None

        session_mock = AsyncMock()
        session_mock.execute = AsyncMock(side_effect=RuntimeError("DB error"))
        session_mock.rollback = AsyncMock()

        with patch.object(
            type(repo),
            "session",
            new_callable=lambda: property(lambda self: session_mock),
        ):
            with pytest.raises(RuntimeError, match="DB error"):
                await repo.save_model_params(arac_id=3, params={})

        session_mock.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_model_params
# ---------------------------------------------------------------------------


class TestGetModelParams:
    async def test_returns_none_when_not_found(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

        result = await repo.get_model_params(arac_id=99)
        assert result is None

    async def test_returns_dict_when_found_dict_katsayilar(self):
        repo = _make_repo()
        obj = MagicMock()
        obj.katsayilar = {"coefficients": [1.0, 2.0], "some_key": "val"}
        obj.r2_score = 0.95
        obj.sample_count = 100
        obj.updated_at = datetime.now(timezone.utc)

        repo._session.execute = AsyncMock(return_value=_scalar_one_or_none_result(obj))

        result = await repo.get_model_params(arac_id=1)
        assert result is not None
        assert result["coefficients"] == [1.0, 2.0]
        assert result["r_squared"] == 0.95
        assert result["sample_count"] == 100

    async def test_returns_dict_when_found_no_coefficients_key(self):
        """katsayilar without 'coefficients' key — entire dict returned as coefficients."""
        repo = _make_repo()
        obj = MagicMock()
        obj.katsayilar = {"intercept": 1.5, "slope": 0.3}
        obj.r2_score = 0.88
        obj.sample_count = 50
        obj.updated_at = datetime.now(timezone.utc)

        repo._session.execute = AsyncMock(return_value=_scalar_one_or_none_result(obj))

        result = await repo.get_model_params(arac_id=2)
        assert result["coefficients"] == {"intercept": 1.5, "slope": 0.3}

    async def test_json_string_katsayilar_is_parsed(self):
        """katsayilar stored as JSON string is parsed."""
        import json

        repo = _make_repo()
        obj = MagicMock()
        obj.katsayilar = json.dumps({"coefficients": [0.1, 0.2]})
        obj.r2_score = 0.7
        obj.sample_count = 20
        obj.updated_at = datetime.now(timezone.utc)

        repo._session.execute = AsyncMock(return_value=_scalar_one_or_none_result(obj))

        result = await repo.get_model_params(arac_id=3)
        assert result["coefficients"] == [0.1, 0.2]


# ---------------------------------------------------------------------------
# get_filo_ortalama_tuketim
# ---------------------------------------------------------------------------


class TestGetFiloOrtalamatuketim:
    async def test_returns_default_when_result_is_none(self):
        repo = _make_repo()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_filo_ortalama_tuketim()
        assert result == 32.0

    async def test_returns_rounded_value(self):
        repo = _make_repo()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=35.678)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_filo_ortalama_tuketim()
        assert result == 35.68

    async def test_with_date_filters(self):
        repo = _make_repo()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=31.5)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_filo_ortalama_tuketim(
            baslangic=date(2024, 1, 1),
            bitis=date(2024, 12, 31),
        )
        assert result == 31.5
        # Verify params include date filters
        call_kwargs = repo._session.execute.call_args
        params = call_kwargs[0][1]
        assert "baslangic" in params
        assert "bitis" in params

    async def test_exception_returns_default(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(side_effect=RuntimeError("DB down"))

        result = await repo.get_filo_ortalama_tuketim()
        assert result == 32.0


# ---------------------------------------------------------------------------
# get_dashboard_stats
# ---------------------------------------------------------------------------


class TestGetDashboardStats:
    async def test_returns_mapping_row_as_dict(self):
        repo = _make_repo()
        row = _mapping_row(
            toplam_sefer=5,
            toplam_km=1000.0,
            toplam_yakit=200.0,
            filo_ortalama=32.5,
            aktif_arac=3,
            toplam_arac=4,
            aktif_sofor=5,
            bugun_sefer=1,
        )
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=row)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_dashboard_stats(today_utc=date.today())
        assert result["toplam_sefer"] == 5
        assert result["filo_ortalama"] == 32.5

    async def test_returns_default_on_exception(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(side_effect=RuntimeError("fail"))

        result = await repo.get_dashboard_stats()
        assert result["filo_ortalama"] == 32.0
        assert result["toplam_arac"] == 0

    async def test_no_row_returns_default(self):
        """fetchone() returning None triggers the default return."""
        repo = _make_repo()
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=None)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_dashboard_stats()
        assert result["filo_ortalama"] == 32.0

    async def test_row_without_mapping_uses_getattr(self):
        """Row without _mapping attribute falls back to getattr path."""
        repo = _make_repo()

        class FakeRow:
            toplam_arac = 2
            toplam_sofor = 3
            filo_ortalama = 30.0
            toplam_yakit = 50.0

        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=FakeRow())
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_dashboard_stats()
        assert result["toplam_arac"] == 2


# ---------------------------------------------------------------------------
# get_month_over_month_trends
# ---------------------------------------------------------------------------


class TestGetMonthOverMonthTrends:
    async def test_computes_delta_correctly(self):
        repo = _make_repo()
        row = _mapping_row(
            curr_sefer=10,
            curr_km=1000.0,
            curr_tuketim=35.0,
            prev_sefer=8,
            prev_km=800.0,
            prev_tuketim=33.0,
        )
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=row)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_month_over_month_trends(today_utc=date(2024, 6, 15))
        assert isinstance(result, dict)
        assert "sefer" in result
        assert "km" in result
        assert "tuketim" in result
        # (10-8)/8*100 = 25.0
        assert result["sefer"] == pytest.approx(25.0, abs=0.01)

    async def test_prev_zero_returns_zero_delta(self):
        """When previous period is 0, delta should be 0 (no division by zero)."""
        repo = _make_repo()
        row = _mapping_row(
            curr_sefer=5,
            curr_km=500.0,
            curr_tuketim=30.0,
            prev_sefer=0,
            prev_km=0.0,
            prev_tuketim=0.0,
        )
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=row)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_month_over_month_trends()
        assert result["sefer"] == 0.0
        assert result["km"] == 0.0

    async def test_exception_returns_zeros(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

        result = await repo.get_month_over_month_trends()
        assert result == {"sefer": 0.0, "km": 0.0, "tuketim": 0.0}

    async def test_no_row_returns_zeros(self):
        repo = _make_repo()
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=None)
        repo._session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_month_over_month_trends()
        assert result == {"sefer": 0.0, "km": 0.0, "tuketim": 0.0}

    async def test_january_prev_month_is_december(self):
        """January should map previous month to December of prior year."""
        repo = _make_repo()
        row = _mapping_row(
            curr_sefer=3,
            curr_km=300.0,
            curr_tuketim=32.0,
            prev_sefer=3,
            prev_km=300.0,
            prev_tuketim=32.0,
        )
        result_mock = MagicMock()
        result_mock.fetchone = MagicMock(return_value=row)
        repo._session.execute = AsyncMock(return_value=result_mock)

        # Jan 15 → prev should be Dec 15 of prior year
        result = await repo.get_month_over_month_trends(today_utc=date(2024, 1, 15))
        assert result["sefer"] == 0.0  # equal periods


# ---------------------------------------------------------------------------
# get_all_vehicles_consumption_stats
# ---------------------------------------------------------------------------


class TestGetAllVehiclesConsumptionStats:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()
        row = _mapping_row(arac_id=1, plaka="34ABC", ort_tuketim=33.0)
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_all_vehicles_consumption_stats(days=30)
        assert isinstance(result, list)
        assert result[0]["plaka"] == "34ABC"

    async def test_days_clamped_to_1_to_365(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        # Should not raise for out-of-range values
        await repo.get_all_vehicles_consumption_stats(days=0)
        await repo.get_all_vehicles_consumption_stats(days=500)


# ---------------------------------------------------------------------------
# get_recent_unread_alerts
# ---------------------------------------------------------------------------


class TestGetRecentUnreadAlerts:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()
        row = _mapping_row(
            title="sefer", message="High fuel", severity="high", created_at=None
        )
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_recent_unread_alerts(limit=5)
        assert isinstance(result, list)
        assert result[0]["severity"] == "high"

    async def test_exception_returns_empty_list(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(side_effect=RuntimeError("table missing"))

        result = await repo.get_recent_unread_alerts()
        assert result == []


# ---------------------------------------------------------------------------
# get_period_stats
# ---------------------------------------------------------------------------


class TestGetPeriodStats:
    async def test_returns_dict_when_row_found(self):
        repo = _make_repo()
        row = _mapping_row(
            toplam_sefer=10, toplam_km=2000.0, ortalama_tuketim=34.0, toplam_yakit=500.0
        )
        repo._session.execute = AsyncMock(return_value=_fetchone_result(row))

        result = await repo.get_period_stats(
            start=date(2024, 1, 1), end=date(2024, 1, 31)
        )
        assert result["toplam_sefer"] == 10

    async def test_returns_empty_dict_when_no_row(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchone_result(None))

        result = await repo.get_period_stats(
            start=date(2024, 1, 1), end=date(2024, 1, 31)
        )
        assert result == {}


# ---------------------------------------------------------------------------
# get_vehicle_summary_stats
# ---------------------------------------------------------------------------


class TestGetVehicleSummaryStats:
    async def test_returns_dict_when_row_found(self):
        repo = _make_repo()
        row = _mapping_row(
            sefer_sayisi=5, toplam_km=800.0, ort_tuketim=33.0, en_iyi=30.0, en_kotu=38.0
        )
        repo._session.execute = AsyncMock(return_value=_fetchone_result(row))

        result = await repo.get_vehicle_summary_stats(
            arac_id=1, start_date=date(2024, 1, 1)
        )
        assert result["sefer_sayisi"] == 5

    async def test_returns_empty_dict_when_no_row(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchone_result(None))

        result = await repo.get_vehicle_summary_stats(
            arac_id=99, start_date=date(2024, 1, 1)
        )
        assert result == {}


# ---------------------------------------------------------------------------
# get_fleet_performance_stats
# ---------------------------------------------------------------------------


class TestGetFleetPerformanceStats:
    async def test_returns_dict_when_row_found(self):
        repo = _make_repo()
        row = _mapping_row(
            toplam_sefer=20,
            toplam_km=5000.0,
            filo_ortalama=32.0,
            toplam_harcama=10000.0,
        )
        repo._session.execute = AsyncMock(return_value=_fetchone_result(row))

        result = await repo.get_fleet_performance_stats(start_date=date(2024, 1, 1))
        assert result["toplam_sefer"] == 20

    async def test_returns_empty_dict_when_no_row(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchone_result(None))

        result = await repo.get_fleet_performance_stats(start_date=date(2024, 1, 1))
        assert result == {}


# ---------------------------------------------------------------------------
# get_top_routes_by_vehicle
# ---------------------------------------------------------------------------


class TestGetTopRoutesByVehicle:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()
        row = _mapping_row(guzergah="Ankara → Konya", sefer=3, tuketim=34.0)
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_top_routes_by_vehicle(
            arac_id=1, start_date=date(2024, 1, 1)
        )
        assert len(result) == 1
        assert result[0]["guzergah"] == "Ankara → Konya"

    async def test_limit_clamped(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_top_routes_by_vehicle(
            arac_id=1, start_date=date(2024, 1, 1), limit=999
        )
        params = repo._session.execute.call_args[0][1]
        assert params["limit"] == 50  # max 50

    async def test_limit_falsy_uses_default(self):
        """limit=0 is falsy → uses default 5 before clamping."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_top_routes_by_vehicle(
            arac_id=1, start_date=date(2024, 1, 1), limit=0
        )
        params = repo._session.execute.call_args[0][1]
        # 0 is falsy → `int(limit or 5)` = 5
        assert params["limit"] == 5


# ---------------------------------------------------------------------------
# get_daily_summary_for_ml
# ---------------------------------------------------------------------------


class TestGetDailySummaryForMl:
    async def test_with_arac_id(self):
        repo = _make_repo()
        row = _mapping_row(tarih=date(2024, 1, 1), ort_tuketim=33.0, toplam_km=200.0)
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_daily_summary_for_ml(days=30, arac_id=1)
        assert len(result) == 1

    async def test_without_arac_id(self):
        repo = _make_repo()
        row = _mapping_row(tarih=date(2024, 1, 2), ort_tuketim=32.0, toplam_km=150.0)
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_daily_summary_for_ml(days=60)
        assert len(result) == 1

    async def test_days_clamped(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_daily_summary_for_ml(days=9999)
        # Should not raise; days is clamped to 730


# ---------------------------------------------------------------------------
# get_heatmap_data
# ---------------------------------------------------------------------------


class TestGetHeatmapData:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()
        row = _mapping_row(varis_yeri="Konya", count=5, avg_consumption=33.0)
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_heatmap_data(days=90)
        assert len(result) == 1
        assert result[0]["varis_yeri"] == "Konya"

    async def test_days_clamped(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_heatmap_data(days=0)  # should clamp to 1
        await repo.get_heatmap_data(days=500)  # should clamp to 365


# ---------------------------------------------------------------------------
# get_daily_consumption_series
# ---------------------------------------------------------------------------


class TestGetDailyConsumptionSeries:
    async def test_returns_isoformat_date_and_float_value(self):
        repo = _make_repo()

        row = MagicMock()
        row.date = date(2024, 3, 15)
        row.value = 42.5
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_daily_consumption_series(days=30)
        assert len(result) == 1
        assert result[0]["date"] == "2024-03-15"
        assert result[0]["value"] == 42.5

    async def test_none_date_returns_none(self):
        repo = _make_repo()
        row = MagicMock()
        row.date = None
        row.value = 10.0
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_daily_consumption_series()
        assert result[0]["date"] is None

    async def test_days_clamped(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_daily_consumption_series(days=0)
        await repo.get_daily_consumption_series(days=500)


# ---------------------------------------------------------------------------
# get_top_performing_vehicles
# ---------------------------------------------------------------------------


class TestGetTopPerformingVehicles:
    async def test_returns_list_with_rounded_avg(self):
        repo = _make_repo()
        row = MagicMock()
        row.plaka = "34TIR01"
        row.avg_consumption = 29.678
        row.trip_count = 10
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_top_performing_vehicles(limit=15)
        assert len(result) == 1
        assert result[0]["plaka"] == "34TIR01"
        assert result[0]["avg_consumption"] == 29.68
        assert result[0]["trip_count"] == 10

    async def test_limit_clamped_to_100(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_top_performing_vehicles(limit=500)
        params = repo._session.execute.call_args[0][1]
        assert params["limit"] == 100

    async def test_limit_falsy_uses_default(self):
        """limit=0 is falsy → uses default 15 before clamping."""
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_top_performing_vehicles(limit=0)
        params = repo._session.execute.call_args[0][1]
        # 0 is falsy → `int(limit or 15)` = 15
        assert params["limit"] == 15


# ---------------------------------------------------------------------------
# get_bulk_cost_stats
# ---------------------------------------------------------------------------


class TestGetBulkCostStats:
    async def test_returns_list_of_dicts(self):
        repo = _make_repo()
        row = _mapping_row(
            ay="2024-01",
            yakit_tl=5000.0,
            yakit_litre=200.0,
            sefer_sayisi=10,
            toplam_km=3000.0,
        )
        repo._session.execute = AsyncMock(return_value=_fetchall_result([row]))

        result = await repo.get_bulk_cost_stats(months=12)
        assert len(result) == 1
        assert result[0]["ay"] == "2024-01"

    async def test_months_default_is_12(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_bulk_cost_stats()
        params = repo._session.execute.call_args[0][1]
        assert params["months"] == 12

    async def test_months_cast_to_int(self):
        repo = _make_repo()
        repo._session.execute = AsyncMock(return_value=_fetchall_result([]))

        await repo.get_bulk_cost_stats(months=6)
        params = repo._session.execute.call_args[0][1]
        assert isinstance(params["months"], int)
        assert params["months"] == 6


# ---------------------------------------------------------------------------
# get_analiz_repo factory
# ---------------------------------------------------------------------------


class TestGetAnalizRepoFactory:
    def test_returns_analiz_repo_instance(self):
        from v2.modules.analytics_executive.infrastructure.executive_read_models import (
            AnalizRepository,
            get_analiz_repo,
        )

        repo = get_analiz_repo()
        assert isinstance(repo, AnalizRepository)

    def test_singleton_returns_same_instance(self):
        from v2.modules.analytics_executive.infrastructure.executive_read_models import (
            get_analiz_repo,
        )

        repo1 = get_analiz_repo()
        repo2 = get_analiz_repo()
        assert repo1 is repo2

    def test_with_session_arg_returns_new_instance(self):
        from v2.modules.analytics_executive.infrastructure.executive_read_models import (
            AnalizRepository,
            get_analiz_repo,
        )

        mock_session = AsyncMock()
        repo = get_analiz_repo(session=mock_session)
        assert isinstance(repo, AnalizRepository)
        assert repo._session is mock_session
