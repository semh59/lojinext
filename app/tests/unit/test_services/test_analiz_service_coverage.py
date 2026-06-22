"""
Coverage tests for AnalizService (analiz_service.py).
Focuses on calculate_moving_average, calculate_trend, calculate_eei,
calculate_long_term_stats, get_fleet_average, clear_cache, singleton.

0-mock slice 3a: all MagicMock / AsyncMock / patch(UnitOfWork) removed.
- Pure-math tests use AnalizService(yakit_repo=None, sefer_repo=None) — repos
  fall back to session-less singletons that are never called by math methods.
- DB-touching tests use the db_session fixture with real seeded Postgres rows.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    """Construct AnalizService without any mock repos.

    Passing None for both repos makes __init__ fall through to get_yakit_repo()
    / get_sefer_repo() (session-less singletons).  Pure math tests never touch
    the repos, so the session-less state is fine.
    """
    from app.core.services.analiz_service import AnalizService

    return AnalizService(yakit_repo=None, sefer_repo=None)


# ---------------------------------------------------------------------------
# Tests: calculate_moving_average
# ---------------------------------------------------------------------------


class TestCalculateMovingAverage:
    def test_first_window_minus_one_elements_are_none(self):
        svc = _make_service()
        values = [30.0, 31.0, 32.0, 33.0, 34.0]
        result = svc.calculate_moving_average(values, window=3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None

    def test_correct_average_calculated(self):
        svc = _make_service()
        values = [30.0, 30.0, 30.0, 30.0, 30.0]
        result = svc.calculate_moving_average(values, window=3)
        assert result[2] == pytest.approx(30.0)
        assert result[3] == pytest.approx(30.0)

    def test_window_1_returns_all_values(self):
        svc = _make_service()
        values = [10.0, 20.0, 30.0]
        result = svc.calculate_moving_average(values, window=1)
        assert result == [10.0, 20.0, 30.0]

    def test_empty_list_returns_empty(self):
        svc = _make_service()
        assert svc.calculate_moving_average([], window=5) == []

    def test_window_larger_than_list_all_none(self):
        svc = _make_service()
        values = [30.0, 31.0]
        result = svc.calculate_moving_average(values, window=5)
        assert all(v is None for v in result)

    def test_result_length_matches_input(self):
        svc = _make_service()
        values = [30.0, 31.0, 32.0, 33.0, 34.0]
        result = svc.calculate_moving_average(values, window=3)
        assert len(result) == len(values)


# ---------------------------------------------------------------------------
# Tests: calculate_trend
# ---------------------------------------------------------------------------


class TestCalculateTrend:
    def test_fewer_than_3_values_returns_stable(self):
        svc = _make_service()
        result = svc.calculate_trend([30.0, 32.0])
        assert result["direction"] == "stable"
        assert result["slope"] == 0
        assert result["strength"] == 0

    def test_increasing_trend_detected(self):
        svc = _make_service()
        values = [28.0, 30.0, 32.0, 34.0, 36.0, 38.0]
        result = svc.calculate_trend(values)
        assert result["direction"] == "increasing"
        assert result["slope"] > 0

    def test_decreasing_trend_detected(self):
        svc = _make_service()
        values = [38.0, 36.0, 34.0, 32.0, 30.0, 28.0]
        result = svc.calculate_trend(values)
        assert result["direction"] == "decreasing"
        assert result["slope"] < 0

    def test_stable_trend_for_flat_data(self):
        svc = _make_service()
        values = [32.0, 32.0, 32.0, 32.0, 32.0]
        result = svc.calculate_trend(values)
        assert result["direction"] == "stable"

    def test_r_squared_between_0_and_1(self):
        svc = _make_service()
        values = [28.0, 30.0, 32.0, 34.0, 36.0]
        result = svc.calculate_trend(values)
        assert 0 <= result["strength"] <= 1.0

    def test_returns_dict_with_expected_keys(self):
        svc = _make_service()
        result = svc.calculate_trend([30.0, 31.0, 32.0, 33.0])
        assert "slope" in result
        assert "direction" in result
        assert "strength" in result


# ---------------------------------------------------------------------------
# Tests: calculate_eei (delegated to AnomalyDetectionService)
# ---------------------------------------------------------------------------


class TestCalculateEei:
    def test_eei_returns_float(self):
        svc = _make_service()
        eei = svc.calculate_eei(actual_consumption=35.0, predicted_consumption=32.0)
        assert isinstance(eei, float)

    def test_eei_below_100_when_actual_above_predicted(self):
        """actual > predicted → EEI < 100 (less efficient than predicted)."""
        svc = _make_service()
        eei = svc.calculate_eei(actual_consumption=38.0, predicted_consumption=32.0)
        assert eei < 100.0

    def test_eei_above_100_when_actual_below_predicted(self):
        """actual < predicted → EEI > 100 (more efficient than predicted)."""
        svc = _make_service()
        eei = svc.calculate_eei(actual_consumption=28.0, predicted_consumption=32.0)
        assert eei > 100.0


# ---------------------------------------------------------------------------
# Tests: detect_anomalies (delegated)
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    async def test_empty_list_returns_empty(self):
        svc = _make_service()
        result = await svc.detect_anomalies([])
        assert result == []

    async def test_few_values_returns_empty(self):
        svc = _make_service()
        result = await svc.detect_anomalies([30, 31, 32])
        assert result == []


# ---------------------------------------------------------------------------
# Tests: analyze_vehicle_consumption (delegated)
# ---------------------------------------------------------------------------


class TestAnalyzeVehicleConsumption:
    async def test_returns_vehicle_stats_with_correct_arac_id(self):
        from app.core.entities import VehicleStats

        svc = _make_service()
        consumptions = [30.0, 31.0, 32.0, 33.0, 34.0, 31.0, 32.0, 33.0, 32.0, 31.0]
        result = await svc.analyze_vehicle_consumption(
            arac_id=7, consumptions=consumptions
        )
        assert isinstance(result, VehicleStats)
        assert result.arac_id == 7


# ---------------------------------------------------------------------------
# Tests: get_fleet_average  (DB — requires db_session)
# ---------------------------------------------------------------------------


class TestGetFleetAverage:
    async def test_returns_float(self, db_session):
        """Seed completed trips with tuketim, then get_fleet_average returns a float."""
        from app.core.services.analiz_service import AnalizService
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

        arac = await seed_arac(db_session, plaka="34GA001")
        sofor = await seed_sofor(db_session, ad_soyad="Test Sofor GA")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            durum="Completed",
            mesafe_km=500.0,
            tuketim=32.5,
        )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)
        # Wire a deterministic in-memory cache so the UoW path can complete
        # against the test session without hitting real Redis TTL behaviour.
        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        result = await svc.get_fleet_average(year=2025, month=9)

        assert isinstance(result, float)
        # COALESCE to DEFAULT_FILO_ORTALAMA=32.0 when no completed trips exist,
        # or the real average otherwise.  Both are valid floats > 0.
        assert result > 0.0

    async def test_uses_cache_on_second_call(self, db_session):
        """Behavioral cache proof: second call returns same value even after row deletion."""
        from sqlalchemy import delete

        from app.core.services.analiz_service import AnalizService
        from app.database.models import Sefer as SeferModel
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

        arac = await seed_arac(db_session, plaka="34GA002")
        sofor = await seed_sofor(db_session, ad_soyad="Test Sofor GA2")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            durum="Completed",
            mesafe_km=450.0,
            tuketim=31.0,
        )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)

        # Wire a deterministic in-memory cache
        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        result1 = await svc.get_fleet_average(year=2025, month=8)

        # Delete the seeded rows so a fresh DB read would return the default
        await db_session.execute(delete(SeferModel))
        await db_session.commit()

        # Second call must return the cached value, not the (now-empty) DB result
        result2 = await svc.get_fleet_average(year=2025, month=8)

        assert isinstance(result1, float)
        assert result1 == result2  # served from cache


# ---------------------------------------------------------------------------
# Tests: calculate_long_term_stats  (DB — requires db_session)
# ---------------------------------------------------------------------------


class TestCalculateLongTermStats:
    async def test_returns_none_when_insufficient_data(self, db_session):
        """Only 2 yakit rows → len(alimlar) < 3 → None."""
        from app.core.services.analiz_service import AnalizService
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_yakit

        arac = await seed_arac(db_session, plaka="34LT001")
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=10000, litre=300.0)
        await seed_yakit(db_session, arac_id=arac.id, km_sayac=11000, litre=320.0)
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)
        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        result = await svc.calculate_long_term_stats(arac_id=arac.id)
        assert result is None

    async def test_returns_none_when_all_same_km(self, db_session):
        """3 rows all with same km_sayac → dist == 0 for all → x_data empty → None."""
        from app.core.services.analiz_service import AnalizService
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_yakit

        arac = await seed_arac(db_session, plaka="34LT002")
        # All same km_sayac — use different dates to satisfy unique constraints
        t0 = date(2025, 1, 1)
        t1 = date(2025, 1, 2)
        t2 = date(2025, 1, 3)
        await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=10000, litre=100.0, tarih=t0
        )
        await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=10000, litre=300.0, tarih=t1
        )
        await seed_yakit(
            db_session, arac_id=arac.id, km_sayac=10000, litre=320.0, tarih=t2
        )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)
        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        # All same km → dist=0 → no x_data points → len(x_data) < 3 → None
        result = await svc.calculate_long_term_stats(arac_id=arac.id)
        assert result is None

    async def test_returns_result_with_sufficient_data(self, db_session):
        """4 rows with incrementing km → sufficient data → dict with expected keys."""
        from app.core.services.analiz_service import AnalizService
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_yakit

        arac = await seed_arac(db_session, plaka="34LT003")
        rows = [
            (10000, 100.0, date(2025, 1, 1)),
            (11000, 300.0, date(2025, 1, 8)),
            (12000, 320.0, date(2025, 1, 15)),
            (13000, 310.0, date(2025, 1, 22)),
        ]
        for km, litre, tarih in rows:
            await seed_yakit(
                db_session, arac_id=arac.id, km_sayac=km, litre=litre, tarih=tarih
            )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)
        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        result = await svc.calculate_long_term_stats(arac_id=arac.id)
        assert result is not None
        assert "ortalama" in result
        assert "guvenilirlik" in result
        assert "toplam_km" in result
        assert "toplam_yakit" in result

    async def test_uses_cache_on_second_call(self, db_session):
        """Behavioral cache proof: second call returns same dict after rows are deleted."""
        from sqlalchemy import delete

        from app.core.services.analiz_service import AnalizService
        from app.database.models import YakitAlimi as YakitAlimiModel
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_yakit

        arac = await seed_arac(db_session, plaka="34LT004")
        rows = [
            (10000, 100.0, date(2025, 2, 1)),
            (11000, 300.0, date(2025, 2, 8)),
            (12000, 320.0, date(2025, 2, 15)),
            (13000, 310.0, date(2025, 2, 22)),
        ]
        for km, litre, tarih in rows:
            await seed_yakit(
                db_session, arac_id=arac.id, km_sayac=km, litre=litre, tarih=tarih
            )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=None)

        cache_store: dict = {}
        svc.cache.get = lambda key: cache_store.get(key)  # type: ignore[method-assign]
        svc.cache.set = lambda key, val, ttl_seconds=None: cache_store.update(  # type: ignore[method-assign]
            {key: val}
        )

        result1 = await svc.calculate_long_term_stats(arac_id=arac.id)
        assert result1 is not None

        # Delete rows — a fresh DB read would now return < 3 entries (None)
        await db_session.execute(
            delete(YakitAlimiModel).where(YakitAlimiModel.arac_id == arac.id)
        )
        await db_session.commit()

        # Second call: cache hit → same result returned (not None from empty DB)
        result2 = await svc.calculate_long_term_stats(arac_id=arac.id)
        assert result1 == result2


# ---------------------------------------------------------------------------
# Tests: create_fuel_periods / distribute_fuel_to_trips delegation
# ---------------------------------------------------------------------------


class TestDelegationMethods:
    async def test_create_fuel_periods_delegates(self):
        svc = _make_service()
        result = await svc.create_fuel_periods([])
        assert result == []

    async def test_recalculate_vehicle_periods_delegates(self, db_session):
        """Real effect: seed arac + yakit rows, call recalculate_vehicle_periods,
        confirm it runs without error (periods saved or gracefully skipped when
        < 2 fuel records prevent period creation)."""
        from app.core.services.analiz_service import AnalizService
        from app.database.repositories.sefer_repo import SeferRepository
        from app.database.repositories.yakit_repo import YakitRepository
        from app.tests._helpers.seed import seed_arac, seed_yakit

        arac = await seed_arac(db_session, plaka="34RP001")
        # Seed 2 fuel rows at different km — minimum for 1 period
        await seed_yakit(
            db_session,
            arac_id=arac.id,
            km_sayac=10000,
            litre=300.0,
            tarih=date(2025, 3, 1),
        )
        await seed_yakit(
            db_session,
            arac_id=arac.id,
            km_sayac=11000,
            litre=310.0,
            tarih=date(2025, 3, 15),
        )
        await db_session.commit()

        yakit_repo = YakitRepository(session=db_session)
        sefer_repo = SeferRepository(session=db_session)
        svc = AnalizService(yakit_repo=yakit_repo, sefer_repo=sefer_repo)

        # recalculate_vehicle_periods internally opens a UnitOfWork (which the
        # db_session fixture monkeypatches to the test session), computes periods
        # from the seeded fuel rows, and saves them.  We assert it completes
        # without raising.
        await svc.recalculate_vehicle_periods(arac.id)
        # If we reach here without exception the delegation chain is intact.
        assert True


# ---------------------------------------------------------------------------
# Tests: clear_cache
# ---------------------------------------------------------------------------


class TestClearCache:
    def test_clear_cache_does_not_raise(self):
        svc = _make_service()
        svc.clear_cache()  # should not raise


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestAnalizServiceSingleton:
    def test_get_analiz_service_returns_instance(self):
        # Reset singleton for clean test
        import app.core.services.analiz_service as mod
        from app.core.services.analiz_service import AnalizService, get_analiz_service

        orig = mod._analiz_service
        try:
            mod._analiz_service = None
            svc = get_analiz_service()
            assert isinstance(svc, AnalizService)
        finally:
            mod._analiz_service = orig

    def test_get_analiz_service_same_instance(self):
        from app.core.services.analiz_service import get_analiz_service

        a = get_analiz_service()
        b = get_analiz_service()
        assert a is b
