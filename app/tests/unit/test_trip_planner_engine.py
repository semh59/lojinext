"""Feature C.1 — TripPlannerEngine entegrasyon-tarzı testler.

DB ve gerçek PredictionService olmadan; UnitOfWork ve PredictionService
mock'lanır. Saf yardımcılar `test_trip_planner_scoring.py`'da test edilir;
burada engine'in akışı doğrulanır.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest


class _FakePredictor:
    """predict_consumption stub — arac_id → litres map'i ile çağrılır."""

    def __init__(self, litres_by_id: Dict[int, float]) -> None:
        self._map = litres_by_id

    async def predict_consumption(
        self, *, arac_id: int, **kwargs: Any
    ) -> Dict[str, Any]:
        return {
            "tahmini_litre": self._map.get(arac_id, 0.0),
            "model_used": "physics",
            "status": "success",
        }


class _FakeAracRepo:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    async def get_eligible_for_planning(self, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._rows


class _FakeSoforRepo:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    async def get_eligible_for_planning(self, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._rows


class _FakeUoW:
    """Async context manager — repo'ları test'lerin sağladığı stub'lara bağlar."""

    def __init__(
        self,
        arac_rows: List[Dict[str, Any]],
        sofor_rows: List[Dict[str, Any]],
    ) -> None:
        self.arac_repo = _FakeAracRepo(arac_rows)
        self.sofor_repo = _FakeSoforRepo(sofor_rows)
        self.session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


async def _fake_get_score_breakdown_sofor(
    sofor_id: int, uow: Any = None
) -> Dict[str, Any]:
    """get_score_breakdown_sofor stub (v2.modules.driver.application.get_score).

    Şoför 100 → mükemmel; 101 → cold-start (has_trips=False); 102 → orta.
    """
    if sofor_id == 100:
        return {"total": 85.0, "has_trips": True}
    if sofor_id == 101:
        return {"total": 50.0, "has_trips": False}
    return {"total": 60.0, "has_trips": True}


async def _fake_get_route_profile_sofor(
    sofor_id: int, min_trips_for_best: int = 5, uow: Any = None
) -> Dict[str, Any]:
    """get_route_profile_sofor stub (v2.modules.driver.application.get_route_profile)."""
    if sofor_id == 100:
        return {
            "profiles": [
                {
                    "route_type": "highway_dominant",
                    "trip_count": 12,
                    "deviation_pct": -4.5,
                }
            ]
        }
    return {"profiles": []}


@pytest.fixture
def _patched_engine(monkeypatch):
    """UoW + SoforService'i fake'lere bağla; PredictionService caller verir."""

    import v2.modules.ai_assistant.application.plan_trip as planner_mod

    current_year = date.today().year
    arac_rows = [
        # Genç + sefer geçmişi → high health, high availability
        {
            "id": 1,
            "plaka": "34 ABC 123",
            "yil": current_year - 3,
            "recent_trip_count": 1,
        },
        # Orta yaş + meşgul
        {
            "id": 2,
            "plaka": "34 DEF 456",
            "yil": current_year - 10,
            "recent_trip_count": 5,
        },
        # Yaşlı + bakım uyarısı
        {
            "id": 3,
            "plaka": "34 GHI 789",
            "yil": current_year - 18,
            "has_open_maintenance_alert": True,
            "recent_trip_count": 0,
        },
    ]
    sofor_rows = [
        {"id": 100, "ad_soyad": "Ali Veli", "recent_trip_count": 1},
        {"id": 101, "ad_soyad": "Yeni Şoför", "recent_trip_count": 0},
        {"id": 102, "ad_soyad": "Mehmet Demir", "recent_trip_count": 4},
    ]

    monkeypatch.setattr(
        "app.database.unit_of_work.UnitOfWork",
        lambda: _FakeUoW(arac_rows, sofor_rows),
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_score_breakdown_sofor",
        _fake_get_score_breakdown_sofor,
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_route_profile_sofor",
        _fake_get_route_profile_sofor,
    )

    # find_similar_trips → 3 benzer sefer (fuel score normalizasyonunu da test eder)
    async def _fake_similar(*args, **kwargs):
        return [{"sefer_id": i, "similarity": 0.9} for i in range(3)]

    monkeypatch.setattr(planner_mod, "find_similar_trips", _fake_similar)

    # PredictionService stub — araç 1 en az, 2 orta, 3 en çok yakar
    predictor = _FakePredictor({1: 120.0, 2: 145.0, 3: 180.0})

    return planner_mod.TripPlannerEngine(predictor)


@pytest.mark.asyncio
async def test_engine_returns_top_3_vehicles_sorted_by_score(_patched_engine):
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    inp = PlanInput(
        cikis_yeri="Ankara",
        varis_yeri="İstanbul",
        mesafe_km=450,
        tarih=date.today(),
        ascent_m=320,
        descent_m=310,
        flat_distance_km=400,
        weight_kg=22000,
        route_analysis={"motorway": {"flat": 400}, "ascent_m": 320, "descent_m": 310},
    )
    result = await _patched_engine.plan(inp, top_n=3)

    assert len(result.vehicles) == 3
    # En yüksek skor en başta
    scores = [v.score for v in result.vehicles]
    assert scores == sorted(scores, reverse=True)
    # Araç 1 (genç + düşük tüketim + müsait) lider olmalı
    assert result.vehicles[0].arac_id == 1
    # Aday içinde minimum yakacak → fuel_score=1.0
    assert result.vehicles[0].fuel_score == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_engine_classifies_route_type_highway(_patched_engine):
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    inp = PlanInput(
        cikis_yeri="Ankara",
        varis_yeri="İstanbul",
        mesafe_km=450,
        tarih=date.today(),
        flat_distance_km=400,
        ascent_m=100,
        descent_m=100,
        route_analysis={
            "motorway": {"flat": 400},
            "ascent_m": 100,
            "descent_m": 100,
        },
    )
    result = await _patched_engine.plan(inp)
    assert result.route_type == "highway_dominant"


@pytest.mark.asyncio
async def test_engine_returns_top_3_drivers_sorted(_patched_engine):
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    inp = PlanInput(
        cikis_yeri="Ankara",
        varis_yeri="İstanbul",
        mesafe_km=450,
        tarih=date.today(),
        flat_distance_km=400,
        route_analysis={"motorway": {"flat": 400}},
    )
    result = await _patched_engine.plan(inp, top_n=3)

    assert len(result.drivers) == 3
    scores = [d.score for d in result.drivers]
    assert scores == sorted(scores, reverse=True)
    # Şoför 100 (yüksek hibrit + iyi route_type_perf) lider olmalı
    assert result.drivers[0].sofor_id == 100
    # Cold-start şoför (101) cold_start=True
    cs = [d for d in result.drivers if d.sofor_id == 101]
    assert cs and cs[0].cold_start is True


@pytest.mark.asyncio
async def test_engine_no_guzergah_id_defaults_neutral_weather(_patched_engine):
    """guzergah_id verilmediğinde weather_impact=1.0 (unknown)."""
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=100,
        tarih=date.today(),
        flat_distance_km=100,
        route_analysis={"motorway": {"flat": 100}},
    )
    result = await _patched_engine.plan(inp)
    assert result.weather_impact == 1.0
    assert result.risk_label == "unknown"


@pytest.mark.asyncio
async def test_engine_top_n_clamped_to_max(_patched_engine):
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    inp = PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=100,
        tarih=date.today(),
        flat_distance_km=100,
        route_analysis={"motorway": {"flat": 100}},
    )
    result = await _patched_engine.plan(inp, top_n=99)
    # Bizim filo 3 araç + 3 şoför; clamp 5'e indirir ama aday sayısı kısıtlar
    assert len(result.vehicles) == 3
    assert len(result.drivers) == 3


@pytest.mark.asyncio
async def test_engine_empty_candidates_returns_empty_lists(monkeypatch):
    """Hard filter boş → vehicles=[] + drivers=[]; engine hata fırlatmaz."""

    import v2.modules.ai_assistant.application.plan_trip as planner_mod

    monkeypatch.setattr(
        "app.database.unit_of_work.UnitOfWork",
        lambda: _FakeUoW([], []),
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_score_breakdown_sofor",
        _fake_get_score_breakdown_sofor,
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_route_profile_sofor",
        _fake_get_route_profile_sofor,
    )

    async def _empty_similar(*args, **kwargs):
        return []

    monkeypatch.setattr(planner_mod, "find_similar_trips", _empty_similar)

    engine = planner_mod.TripPlannerEngine(_FakePredictor({}))
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    result = await engine.plan(
        PlanInput(
            cikis_yeri="A",
            varis_yeri="B",
            mesafe_km=100,
            tarih=date.today(),
            flat_distance_km=100,
            route_analysis={"motorway": {"flat": 100}},
        )
    )
    assert result.vehicles == []
    assert result.drivers == []
