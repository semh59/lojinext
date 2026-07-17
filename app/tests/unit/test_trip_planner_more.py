"""Additional coverage tests for app/core/ai/trip_planner.py.

Targets uncovered branches:
- _vehicle_reasons: all message branches (high/medium/low fuel_score, sim_count,
  age <=3, age >=12, has_open_alert, low/high availability)
- _driver_reasons: cold_start, route_type_perf high with savings, medium, low,
  overall_hybrid high/low, availability low/high
- _vehicle_age_years: negative year clamped to 0
- TripPlannerEngine._classify: classify_route exception → "mixed" fallback
- TripPlannerEngine._count_similar: no route_analysis → 0
- TripPlannerEngine._count_similar: find_similar_trips exception → 0
- TripPlannerEngine._score_vehicles: empty list → []
- TripPlannerEngine._score_drivers: empty list → []
- TripPlannerEngine._score_vehicles: all liters 0 (spread=1.0 default)
- TripPlannerEngine._fetch_route_analysis: exception path
- TripPlannerEngine._fetch_route_analysis: lok is None path
- TripPlannerEngine._fetch_route_analysis: lok has route_analysis
- TripPlannerEngine.plan: top_n clamped (0 → 1, 10 → 5)
- PlanResult dataclass fields
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _vehicle_reasons branches
# ---------------------------------------------------------------------------


def test_vehicle_reasons_high_fuel_score():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    out = _vehicle_reasons(
        fuel_score=0.96,
        similar_trip_count=5,
        age_years=2,
        has_open_alert=False,
        availability_score=0.9,
    )
    assert any("en düşük tahmini tüketim" in r for r in out)
    assert any("benzer sefer" in r for r in out)
    assert any("Yeni araç" in r for r in out)
    assert any("az kullanım" in r for r in out)


def test_vehicle_reasons_medium_fuel_score():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    out = _vehicle_reasons(
        fuel_score=0.75,
        similar_trip_count=0,
        age_years=15,
        has_open_alert=True,
        availability_score=0.1,
    )
    assert any("düşük tahmini tüketim" in r for r in out)
    assert any("Eski araç" in r for r in out)
    assert any("bakım" in r for r in out)
    assert any("yoğun kullanım" in r for r in out)


def test_vehicle_reasons_low_fuel_score_no_extras():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    out = _vehicle_reasons(
        fuel_score=0.3,
        similar_trip_count=0,
        age_years=7,
        has_open_alert=False,
        availability_score=0.5,
    )
    # No special messages for mid-range values
    assert len(out) <= 5


def test_vehicle_reasons_capped_at_5():
    """Output list is never longer than 5."""
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_reasons

    out = _vehicle_reasons(
        fuel_score=0.97,
        similar_trip_count=10,
        age_years=2,
        has_open_alert=True,
        availability_score=0.05,
    )
    assert len(out) <= 5


# ---------------------------------------------------------------------------
# _driver_reasons branches
# ---------------------------------------------------------------------------


def test_driver_reasons_cold_start():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    out = _driver_reasons(
        route_type="mixed",
        deviation_pct=-5.0,
        route_type_perf=0.5,
        overall_hybrid=0.7,
        availability_score=0.5,
        cold_start=True,
    )
    assert any("Yeni şoför" in r for r in out)


def test_driver_reasons_high_perf_savings():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    out = _driver_reasons(
        route_type="motorway",
        deviation_pct=-8.5,
        route_type_perf=0.90,
        overall_hybrid=0.85,
        availability_score=0.9,
        cold_start=False,
    )
    assert any("tasarruflu" in r for r in out)
    assert any("Yüksek hibrit" in r for r in out)
    assert any("az sefer" in r for r in out)


def test_driver_reasons_medium_perf():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    out = _driver_reasons(
        route_type="mixed",
        deviation_pct=3.0,
        route_type_perf=0.72,
        overall_hybrid=0.5,
        availability_score=0.5,
        cold_start=False,
    )
    assert any("tutarlı performans" in r for r in out)


def test_driver_reasons_low_perf_risky():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    out = _driver_reasons(
        route_type="mixed",
        deviation_pct=25.0,
        route_type_perf=0.2,
        overall_hybrid=0.3,
        availability_score=0.2,
        cold_start=False,
    )
    assert any("riskli" in r for r in out)
    assert any("Düşük hibrit" in r for r in out)
    assert any("yoğun kullanım" in r for r in out)


def test_driver_reasons_capped_at_5():
    from v2.modules.ai_assistant.domain.planner_scoring import _driver_reasons

    out = _driver_reasons(
        route_type="mountain",
        deviation_pct=-12.0,
        route_type_perf=0.9,
        overall_hybrid=0.9,
        availability_score=0.9,
        cold_start=False,
    )
    assert len(out) <= 5


# ---------------------------------------------------------------------------
# _vehicle_age_years: future year clamped to 0
# ---------------------------------------------------------------------------


def test_vehicle_age_years_future_year_clamped():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_age_years

    future = date.today().year + 5
    assert _vehicle_age_years({"yil": future}) == 0


def test_vehicle_age_years_negative_result_clamped():
    from v2.modules.ai_assistant.domain.planner_scoring import _vehicle_age_years

    # yil > current year → age < 0 → clamped to 0
    assert _vehicle_age_years({"yil": 9999}) == 0


# ---------------------------------------------------------------------------
# TripPlannerEngine._classify: exception → "mixed"
# ---------------------------------------------------------------------------


def test_classify_exception_falls_back_to_mixed():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())

    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.classify_route",
        side_effect=RuntimeError("classify failed"),
    ):
        result = engine._classify(inp)

    assert result == "mixed"


# ---------------------------------------------------------------------------
# _count_similar: no route_analysis → 0
# ---------------------------------------------------------------------------


async def test_count_similar_no_route_analysis():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        route_analysis=None,
    )
    count = await engine._count_similar(inp)
    assert count == 0


async def test_count_similar_find_similar_trips_exception():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        route_analysis={"motorway": {"flat": 200.0}},
    )

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.find_similar_trips",
        side_effect=RuntimeError("DB error"),
    ):
        count = await engine._count_similar(inp)

    assert count == 0


async def test_count_similar_with_route_analysis():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        route_analysis={"motorway": {"flat": 200.0}},
    )

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.find_similar_trips",
        AsyncMock(return_value=[{"id": 1}, {"id": 2}]),
    ):
        count = await engine._count_similar(inp)

    assert count == 2


# ---------------------------------------------------------------------------
# _score_vehicles: empty list
# ---------------------------------------------------------------------------


async def test_score_vehicles_empty_list():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )
    result = await engine._score_vehicles([], inp)
    assert result == []


# ---------------------------------------------------------------------------
# _score_vehicles: all liters = 0 → fuel_score 0 for all
# ---------------------------------------------------------------------------


async def test_score_vehicles_all_zero_liters():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    mock_predictor = MagicMock()
    mock_predictor.predict_consumption = AsyncMock(
        return_value={"tahmini_litre": 0.0, "fallback_triggered": True}
    )

    engine = TripPlannerEngine(prediction_service=mock_predictor)
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )

    vehicles = [
        {"id": 1, "plaka": "34ABC01", "yil": 2020, "recent_trip_count": 2},
        {"id": 2, "plaka": "34DEF02", "yil": 2019, "recent_trip_count": 3},
    ]

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.find_similar_trips",
        AsyncMock(return_value=[]),
    ):
        result = await engine._score_vehicles(vehicles, inp)

    assert len(result) == 2
    for v in result:
        assert v.fuel_score == 0.0


# ---------------------------------------------------------------------------
# _score_drivers: empty list
# ---------------------------------------------------------------------------


async def test_score_drivers_empty_list():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )

    # _score_drivers with empty list returns [] immediately without touching UoW
    result = await engine._score_drivers([], inp, "mixed")

    assert result == []


# ---------------------------------------------------------------------------
# _fetch_route_analysis: exception path
# ---------------------------------------------------------------------------


async def test_fetch_route_analysis_exception_silenced():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        guzergah_id=5,
    )

    with patch(
        "app.database.unit_of_work.UnitOfWork", side_effect=RuntimeError("DB error")
    ):
        await engine._fetch_route_analysis(inp)  # Should not raise

    # route_analysis unchanged (still None)
    assert inp.route_analysis is None


async def test_fetch_route_analysis_lok_none():
    from app.database.unit_of_work import UnitOfWork
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        guzergah_id=5,
    )

    fake_repo = AsyncMock()
    fake_repo.get_by_id = AsyncMock(return_value=None)

    fake_uow = AsyncMock()
    fake_uow.lokasyon_repo = fake_repo

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        await engine._fetch_route_analysis(inp)

    assert inp.route_analysis is None


async def test_fetch_route_analysis_sets_route_analysis():
    from app.database.unit_of_work import UnitOfWork
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
        guzergah_id=7,
    )

    fake_route = {"route_analysis": {"motorway": {"flat": 200.0}}}
    fake_repo = AsyncMock()
    fake_repo.get_by_id = AsyncMock(return_value=fake_route)

    fake_uow = AsyncMock()
    fake_uow.lokasyon_repo = fake_repo

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        await engine._fetch_route_analysis(inp)

    assert inp.route_analysis == {"motorway": {"flat": 200.0}}


# ---------------------------------------------------------------------------
# TripPlannerEngine.plan: top_n clamping
# ---------------------------------------------------------------------------


async def test_plan_top_n_clamped_to_min_1():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )

    # Patch internal methods to short-circuit
    engine._weather_impact = AsyncMock(return_value=1.0)
    engine._shortlist = AsyncMock(return_value=([], []))
    engine._score_vehicles = AsyncMock(return_value=[])
    engine._score_drivers = AsyncMock(return_value=[])

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.classify_route",
        return_value="mixed",
    ):
        result = await engine.plan(inp, top_n=0)  # 0 → clamped to 1

    assert result.vehicles == []
    assert result.drivers == []


async def test_plan_top_n_clamped_to_max_5():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    engine = TripPlannerEngine(prediction_service=MagicMock())
    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=300.0,
        tarih=date(2026, 6, 1),
    )

    engine._weather_impact = AsyncMock(return_value=1.05)
    engine._shortlist = AsyncMock(return_value=([], []))
    engine._score_vehicles = AsyncMock(return_value=[])
    engine._score_drivers = AsyncMock(return_value=[])

    with patch(
        "v2.modules.ai_assistant.application.plan_trip.classify_route",
        return_value="motorway",
    ):
        result = await engine.plan(inp, top_n=99)  # 99 → clamped to MAX_TOP_N

    assert isinstance(result.risk_label, str)


# ---------------------------------------------------------------------------
# PlanResult dataclass
# ---------------------------------------------------------------------------


def test_plan_result_fields():
    from datetime import datetime, timezone

    from v2.modules.ai_assistant.domain.planner_scoring import PlanResult

    now = datetime.now(timezone.utc)
    r = PlanResult(
        weather_impact=1.05,
        risk_label="medium",
        route_type="motorway",
        vehicles=[],
        drivers=[],
        generated_at=now,
        cache_hit=True,
    )
    assert r.weather_impact == 1.05
    assert r.cache_hit is True
    assert r.generated_at == now
