"""Additional coverage for app/core/ai/recommendation_engine.py.

Targets:
  CACHE_TTL env-var fallback (config parse branches)
  get_all_recommendations orchestration — real DB fetch.

get_all_recommendations previously mocked unit_of_work so arac_repo/sofor_repo
returned canned dicts. Here the entity fetch runs against the real test DB
(seeded araclar/soforler); only the engine's own per-category sub-methods
(get_fleet/cost/vehicle/driver_recommendations) stay AsyncMock — this is an
orchestration unit test (fetch entities → dispatch one sub-call per entity →
gather → sort by priority); the sub-methods have their own coverage. The
asyncio.gather here runs over the mocked sub-methods (no DB), so there is no
shared-session concurrency issue.
"""

import os
import threading
from unittest.mock import AsyncMock

import pytest

from app.tests._helpers.seed import seed_arac, seed_sofor

pytestmark = pytest.mark.integration


def _make_engine():
    """Return a fresh RecommendationEngine (bypasses singleton)."""
    from app.core.ai.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine._cache = {}
    engine._cache_time = {}
    engine._lock = threading.Lock()
    return engine


def _stub_subcategories(engine, *, fleet=None, cost=None, vehicle=None, driver=None):
    """Isolate the orchestration: stub the per-category sub-methods."""
    engine.get_fleet_recommendations = AsyncMock(return_value=fleet or [])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=cost or [])
    engine.get_vehicle_recommendations = AsyncMock(return_value=vehicle or [])
    engine.get_driver_recommendations = AsyncMock(return_value=driver or [])


# ---------------------------------------------------------------------------
# CACHE_TTL env-var parse failure branches (pure config, no DB)
# ---------------------------------------------------------------------------


def test_cache_ttl_invalid_env_var_falls_back_to_default():
    """When AI_CACHE_TTL is not a valid int, CACHE_TTL should default to 3600."""
    import importlib

    orig = os.environ.get("AI_CACHE_TTL")
    os.environ["AI_CACHE_TTL"] = "not_a_number"
    try:
        import app.core.ai.recommendation_engine as mod

        importlib.reload(mod)
        assert mod.RecommendationEngine.CACHE_TTL == 3600
    finally:
        if orig is None:
            os.environ.pop("AI_CACHE_TTL", None)
        else:
            os.environ["AI_CACHE_TTL"] = orig
        importlib.reload(mod)


def test_cache_ttl_valid_env_var_is_used():
    """When AI_CACHE_TTL is valid, it should be used as-is."""
    import importlib

    orig = os.environ.get("AI_CACHE_TTL")
    os.environ["AI_CACHE_TTL"] = "7200"
    try:
        import app.core.ai.recommendation_engine as mod

        importlib.reload(mod)
        assert mod.RecommendationEngine.CACHE_TTL == 7200
    finally:
        if orig is None:
            os.environ.pop("AI_CACHE_TTL", None)
        else:
            os.environ["AI_CACHE_TTL"] = orig
        importlib.reload(mod)


# ---------------------------------------------------------------------------
# get_all_recommendations — real DB entity fetch
# ---------------------------------------------------------------------------


async def test_get_all_recommendations_empty_fleet(db_session):
    """No vehicles/drivers seeded → only the (empty) fleet/cost results → []."""
    engine = _make_engine()
    _stub_subcategories(engine)
    result = await engine.get_all_recommendations()
    assert result == []


async def test_get_all_recommendations_sorted_by_priority(db_session):
    """Combined recs are sorted descending by oncelik."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()
    low = Recommendation(
        kategori="bakim", hedef_tip="arac", hedef_id=1, mesaj="Low", oncelik=2
    )
    high = Recommendation(
        kategori="verimlilik", hedef_tip="filo", hedef_id=None, mesaj="High", oncelik=5
    )
    _stub_subcategories(engine, fleet=[low], cost=[high])

    result = await engine.get_all_recommendations()
    assert len(result) == 2
    assert result[0].oncelik >= result[1].oncelik


async def test_get_all_recommendations_with_vehicles_and_drivers(db_session):
    """Each seeded vehicle/driver triggers its sub-recommendation call (real ids)."""
    from app.core.ai.recommendation_engine import Recommendation

    arac = await seed_arac(db_session, plaka="34 ABC 010")
    sofor = await seed_sofor(db_session, ad_soyad="Sofor 20")
    await db_session.commit()

    engine = _make_engine()
    arac_rec = Recommendation(
        kategori="bakim", hedef_tip="arac", hedef_id=arac.id, mesaj="Arac", oncelik=3
    )
    driver_rec = Recommendation(
        kategori="egitim", hedef_tip="sofor", hedef_id=sofor.id, mesaj="Drv", oncelik=4
    )
    _stub_subcategories(engine, vehicle=[arac_rec], driver=[driver_rec])

    result = await engine.get_all_recommendations()

    assert any(r.hedef_id == arac.id for r in result)
    assert any(r.hedef_id == sofor.id for r in result)
    engine.get_vehicle_recommendations.assert_called_once_with(arac.id)
    engine.get_driver_recommendations.assert_called_once_with(sofor.id)


async def test_get_all_recommendations_multiple_vehicles_and_drivers(db_session):
    """3 vehicles + 2 drivers → 3 vehicle calls + 2 driver calls."""
    for i in range(3):
        await seed_arac(db_session, plaka=f"34 AA 0{i}")
    for i in range(2):
        await seed_sofor(db_session, ad_soyad=f"Sofor {i}")
    await db_session.commit()

    engine = _make_engine()
    _stub_subcategories(engine)

    result = await engine.get_all_recommendations()
    assert engine.get_vehicle_recommendations.call_count == 3
    assert engine.get_driver_recommendations.call_count == 2
    assert isinstance(result, list)


async def test_get_all_recommendations_results_gathered_correctly(db_session):
    """Fleet + cost + vehicle results are flattened and priority-sorted."""
    from app.core.ai.recommendation_engine import Recommendation

    await seed_arac(db_session, plaka="34 ABC 001")
    await db_session.commit()

    engine = _make_engine()
    r1 = Recommendation(
        kategori="bakim", hedef_tip="arac", hedef_id=1, mesaj="R1", oncelik=5
    )
    r2 = Recommendation(
        kategori="egitim", hedef_tip="sofor", hedef_id=2, mesaj="R2", oncelik=3
    )
    r3 = Recommendation(
        kategori="verimlilik", hedef_tip="filo", hedef_id=None, mesaj="R3", oncelik=4
    )
    _stub_subcategories(engine, fleet=[r1], cost=[r3], vehicle=[r2])

    result = await engine.get_all_recommendations()
    assert len(result) == 3
    priorities = [r.oncelik for r in result]
    assert priorities == sorted(priorities, reverse=True)
