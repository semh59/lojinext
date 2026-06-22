"""
Additional coverage for app/core/ai/recommendation_engine.py.

Targets missing lines:
  35-36  — CACHE_TTL env var fallback (ValueError/TypeError branch)
  300-331 — get_all_recommendations full path
"""

import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_engine():
    """Return a fresh RecommendationEngine (bypasses singleton)."""
    from app.core.ai.recommendation_engine import RecommendationEngine

    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine._cache = {}
    engine._cache_time = {}
    engine._lock = threading.Lock()
    return engine


def _make_uow_ctx(araclar=None, soforler=None):
    mock_uow = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(fetchone=MagicMock(return_value=None))
    )
    mock_uow.session = mock_session

    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_all = AsyncMock(return_value=araclar or [])
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_all = AsyncMock(return_value=soforler or [])

    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    return mock_uow


# ---------------------------------------------------------------------------
# CACHE_TTL env-var parse failure branches (lines 35-36)
# ---------------------------------------------------------------------------


def test_cache_ttl_invalid_env_var_falls_back_to_default():
    """When AI_CACHE_TTL is not a valid int, CACHE_TTL should default to 3600."""
    import importlib

    # Save original
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
# get_all_recommendations (lines 300-331)
# ---------------------------------------------------------------------------


async def test_get_all_recommendations_empty_fleet():
    """get_all_recommendations works when no vehicles or drivers."""
    engine = _make_engine()

    # All sub-methods return empty
    engine.get_fleet_recommendations = AsyncMock(return_value=[])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=[])
    engine.get_vehicle_recommendations = AsyncMock(return_value=[])
    engine.get_driver_recommendations = AsyncMock(return_value=[])

    mock_uow = _make_uow_ctx(araclar=[], soforler=[])

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_all_recommendations()

    assert result == []


async def test_get_all_recommendations_sorted_by_priority():
    """get_all_recommendations returns recs sorted descending by oncelik."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()

    low_rec = Recommendation(
        kategori="bakim",
        hedef_tip="arac",
        hedef_id=1,
        mesaj="Low priority",
        oncelik=2,
    )
    high_rec = Recommendation(
        kategori="verimlilik",
        hedef_tip="filo",
        hedef_id=None,
        mesaj="High priority",
        oncelik=5,
    )

    engine.get_fleet_recommendations = AsyncMock(return_value=[low_rec])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=[high_rec])
    engine.get_vehicle_recommendations = AsyncMock(return_value=[])
    engine.get_driver_recommendations = AsyncMock(return_value=[])

    mock_uow = _make_uow_ctx(araclar=[], soforler=[])

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_all_recommendations()

    assert len(result) == 2
    # First should be the highest priority
    assert result[0].oncelik >= result[1].oncelik


async def test_get_all_recommendations_with_vehicles_and_drivers():
    """get_all_recommendations calls sub-methods for each vehicle and driver."""
    from app.core.ai.recommendation_engine import Recommendation

    engine = _make_engine()

    arac_rec = Recommendation(
        kategori="bakim",
        hedef_tip="arac",
        hedef_id=10,
        mesaj="Arac rec",
        oncelik=3,
    )
    driver_rec = Recommendation(
        kategori="egitim",
        hedef_tip="sofor",
        hedef_id=20,
        mesaj="Driver rec",
        oncelik=4,
    )

    engine.get_fleet_recommendations = AsyncMock(return_value=[])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=[])
    engine.get_vehicle_recommendations = AsyncMock(return_value=[arac_rec])
    engine.get_driver_recommendations = AsyncMock(return_value=[driver_rec])

    mock_uow = _make_uow_ctx(
        araclar=[{"id": 10}],
        soforler=[{"id": 20}],
    )

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_all_recommendations()

    assert any(r.hedef_id == 10 for r in result)
    assert any(r.hedef_id == 20 for r in result)
    engine.get_vehicle_recommendations.assert_called_once_with(10)
    engine.get_driver_recommendations.assert_called_once_with(20)


async def test_get_all_recommendations_multiple_vehicles_and_drivers():
    """Multiple vehicles and drivers each get their own recommendation call."""
    engine = _make_engine()

    engine.get_fleet_recommendations = AsyncMock(return_value=[])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=[])
    engine.get_vehicle_recommendations = AsyncMock(return_value=[])
    engine.get_driver_recommendations = AsyncMock(return_value=[])

    mock_uow = _make_uow_ctx(
        araclar=[{"id": 1}, {"id": 2}, {"id": 3}],
        soforler=[{"id": 11}, {"id": 12}],
    )

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_all_recommendations()

    # 3 vehicles + 2 drivers = 5 sub calls
    assert engine.get_vehicle_recommendations.call_count == 3
    assert engine.get_driver_recommendations.call_count == 2
    assert isinstance(result, list)


async def test_get_all_recommendations_results_gathered_correctly():
    """Results from gather are combined properly into a flat sorted list."""
    from app.core.ai.recommendation_engine import Recommendation

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

    engine.get_fleet_recommendations = AsyncMock(return_value=[r1])
    engine.get_cost_saving_suggestions = AsyncMock(return_value=[r3])
    engine.get_vehicle_recommendations = AsyncMock(return_value=[r2])
    engine.get_driver_recommendations = AsyncMock(return_value=[])

    mock_uow = _make_uow_ctx(
        araclar=[{"id": 1}],
        soforler=[],
    )

    with patch("app.core.ai.recommendation_engine.unit_of_work", return_value=mock_uow):
        result = await engine.get_all_recommendations()

    assert len(result) == 3
    priorities = [r.oncelik for r in result]
    assert priorities == sorted(priorities, reverse=True)
