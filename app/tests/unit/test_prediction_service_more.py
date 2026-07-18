"""
Additional coverage for app/services/prediction_service.py.

Targets missed lines:
  243-245   — _run_ensemble_prediction: exception → returns None
  404-407   — _run_physics_model: granular_nodes path (P2P high-fidelity)
  616, 620  — predict_consumption: DB fetch path (no _arac_obj pre-fetched)
  636-638   — predict_consumption: sofor_id DB fetch branch
  664-673   — predict_consumption: MAINTENANCE_FACTOR_ENABLED branch with health input
  818-825   — _log_prediction_to_ai: smart_ai.teach called via create_task
  828-829   — _log_prediction_to_ai: exception in outer try swallowed
  848-878   — explain_consumption: sofor_id stats fetch + predictor untrained fallback
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    from v2.modules.prediction_ml.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService.__new__(PredictionService)
    svc.weather_service = MagicMock()
    svc.weather_service.get_seasonal_factor = MagicMock(return_value=1.0)
    svc.yakit_tahmin_service = MagicMock()
    svc.ensemble_service = MagicMock()
    svc.ensemble_service.get_predictor = MagicMock()
    return svc


def _make_physics_result(l_100km: float = 32.0, insight: str = "Normal"):
    r = MagicMock()
    r.consumption_l_100km = l_100km
    r.insight = insight
    return r


# ---------------------------------------------------------------------------
# _run_ensemble_prediction: exception path (lines 243-245)
# ---------------------------------------------------------------------------


async def test_run_ensemble_prediction_exception_returns_none():
    """When ensemble_service.predict_consumption raises → returns None."""
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        run_ensemble_prediction,
    )

    svc = _make_service()

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)

    svc.ensemble_service.predict_consumption = AsyncMock(
        side_effect=RuntimeError("ensemble crash")
    )

    sefer_dict = {
        "mesafe_km": 500.0,
        "ton": 20.0,
        "sofor_id": None,
        "dorse_id": None,
        "ascent_m": 0.0,
        "descent_m": 0.0,
        "bos_sefer": False,
        "route_analysis": None,
    }

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        result = await run_ensemble_prediction(
            svc.ensemble_service,
            1,
            sefer_dict,
            date.today(),
        )

    assert result is None


# ---------------------------------------------------------------------------
# _run_physics_model: granular_nodes path (lines 404-407)
# ---------------------------------------------------------------------------


async def test_run_physics_model_granular_nodes_path():
    """When normalized_route has granular_nodes → predict_granular is called."""
    from v2.modules.prediction_ml.domain.physics_model import run_physics_model

    granular_nodes = [
        {"lat": 40.0, "lon": 29.0, "elevation_m": 100},
        {"lat": 39.9, "lon": 30.0, "elevation_m": 150},
        {"lat": 39.8, "lon": 31.0, "elevation_m": 200},
    ]

    normalized_route = {
        "granular_nodes": granular_nodes,
        "historical_stats": {"mean": 31.0},
    }

    from v2.modules.prediction_ml.domain.physics_fuel_predictor import VehicleSpecs

    specs = VehicleSpecs()

    mock_granular_result = MagicMock()
    mock_granular_result.consumption_l_100km = 31.5
    mock_granular_result.insight = "P2P granular"

    with patch(
        "v2.modules.prediction_ml.domain.physics_model.asyncio.to_thread",
        new=AsyncMock(return_value=mock_granular_result),
    ):
        result = await run_physics_model(
            specs=specs,
            age=3,
            mesafe_km=500.0,
            ton=20.0,
            ascent_m=100.0,
            descent_m=80.0,
            flat_distance_km=300.0,
            bos_sefer=False,
            weather_factor=1.0,
            otoyol_ratio=0.6,
            devlet_yolu_ratio=0.3,
            sehir_ici_ratio=0.1,
            normalized_route=normalized_route,
        )

    assert result is mock_granular_result


# ---------------------------------------------------------------------------
# predict_consumption: DB fetch path for arac (lines 616, 620)
# ---------------------------------------------------------------------------


async def test_predict_consumption_fetches_arac_from_db_when_not_provided():
    """When _arac_obj not provided → fetches arac from UoW."""
    svc = _make_service()

    # Use a real dict-like object instead of MagicMock to avoid comparison errors
    class FakeArac:
        def __init__(self):
            self.id = 1
            self.marka = "Volvo"
            self.yil = 2020
            self.bos_agirlik_kg = 9000
            self.hava_direnc_katsayisi = 0.7
            self.on_kesit_alani_m2 = 8.5
            self.motor_verimliligi = 0.38
            self.lastik_direnc_katsayisi = 0.007

    mock_arac = FakeArac()

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=mock_arac)
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.dorse_repo = MagicMock()
    mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

    physics_result = _make_physics_result(32.0)

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = False
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
        )

    assert result["status"] == "success"
    mock_uow.arac_repo.get_by_id.assert_awaited_with(1)


# ---------------------------------------------------------------------------
# predict_consumption: sofor_id DB fetch (lines 631-634)
# ---------------------------------------------------------------------------


async def test_predict_consumption_fetches_sofor_from_db():
    """When sofor_id provided and _sofor_obj is None → fetches from DB."""
    svc = _make_service()

    class FakeArac:
        def __init__(self):
            self.id = 1
            self.yil = 2020
            self.bos_agirlik_kg = 9000

    class FakeSofor:
        def __init__(self):
            self.id = 5
            self.ad = "Ali"

    mock_arac = FakeArac()
    mock_sofor = FakeSofor()

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=mock_arac)
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=mock_sofor)
    mock_uow.dorse_repo = MagicMock()
    mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

    physics_result = _make_physics_result(31.0)

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = False
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=400.0,
            ton=15.0,
            sofor_id=5,
            use_ensemble=False,
        )

    assert result["status"] == "success"
    mock_uow.sofor_repo.get_by_id.assert_awaited_with(5)


# ---------------------------------------------------------------------------
# predict_consumption: MAINTENANCE_FACTOR_ENABLED path (lines 641-673)
# ---------------------------------------------------------------------------


async def test_predict_consumption_maintenance_factor_applied():
    """MAINTENANCE_FACTOR_ENABLED=True with health input → factor applied."""
    svc = _make_service()

    class FakeArac:
        def __init__(self):
            self.id = 1
            self.yil = 2020
            self.bos_agirlik_kg = 9000
            self._health_input = MagicMock()

    mock_arac = FakeArac()
    physics_result = _make_physics_result(32.0)

    # compute_maintenance_factor result
    mock_h_res = MagicMock()
    mock_h_res.factor = 1.05
    mock_h_res.reason = "overdue_maintenance"

    with (
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_ensemble_prediction",
            new=AsyncMock(return_value=None),
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.compute_maintenance_factor",
            return_value=mock_h_res,
        ),
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = True
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"


async def test_predict_consumption_maintenance_factor_fetch_health_input_exception():
    """fetch_health_input raises → warning logged, continue without health input."""
    svc = _make_service()

    mock_arac = MagicMock()
    mock_arac.__dict__ = {"id": 1, "yil": 2020}

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=False)

    class FakeArac2:
        def __init__(self):
            self.id = 1
            self.yil = 2020
            self.bos_agirlik_kg = 9000

    mock_arac = FakeArac2()
    mock_uow.arac_repo = MagicMock()
    mock_uow.arac_repo.get_by_id = AsyncMock(return_value=mock_arac)
    mock_uow.sofor_repo = MagicMock()
    mock_uow.sofor_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.dorse_repo = MagicMock()
    mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

    physics_result = _make_physics_result(32.0)

    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.fetch_health_input",
            new=AsyncMock(side_effect=RuntimeError("health fetch fail")),
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = True
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=400.0,
            ton=15.0,
            use_ensemble=False,
        )

    # Should still succeed (health input failure is non-fatal)
    assert result["status"] == "success"


async def test_predict_consumption_maintenance_factor_compute_exception():
    """compute_maintenance_factor raises → warning logged, continue without factor."""
    svc = _make_service()

    class FakeArac:
        def __init__(self):
            self.id = 1
            self.yil = 2020
            self.bos_agirlik_kg = 9000
            self._health_input = MagicMock()

    mock_arac = FakeArac()
    physics_result = _make_physics_result(32.0)

    with (
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.compute_maintenance_factor",
            side_effect=RuntimeError("compute fail"),
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = True
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# _log_prediction_to_ai: exception in outer try (lines 828-829)
# ---------------------------------------------------------------------------


async def test_log_prediction_to_ai_get_smart_ai_exception_swallowed():
    """get_smart_ai() raises → exception swallowed (outer except)."""
    svc = _make_service()

    with patch(
        "v2.modules.prediction_ml.application.prediction_service.asyncio.create_task",
        side_effect=RuntimeError("task fail"),
    ):
        with patch(
            "v2.modules.ai_assistant.public.get_smart_ai",
            side_effect=ImportError("smart_ai not available"),
            create=True,
        ):
            # Should not raise
            await svc._log_prediction_to_ai(1, 500.0, 32.0)


async def test_log_prediction_to_ai_creates_task():
    """_log_prediction_to_ai creates a task with teach call."""

    svc = _make_service()

    created_tasks = []

    def capture_task(coro):
        created_tasks.append(coro)
        return MagicMock()

    mock_smart_ai = MagicMock()
    mock_smart_ai.teach = AsyncMock()

    with (
        patch(
            "v2.modules.prediction_ml.application.prediction_service.asyncio.create_task",
            side_effect=capture_task,
        ),
        patch(
            "v2.modules.ai_assistant.public.get_smart_ai",
            return_value=mock_smart_ai,
            create=True,
        ),
    ):
        await svc._log_prediction_to_ai(1, 500.0, 32.0)

    assert len(created_tasks) == 1


# ---------------------------------------------------------------------------
# explain_consumption: sofor stats fetch + untrained fallback (lines 848-878)
# ---------------------------------------------------------------------------


async def test_explain_consumption_sofor_id_stats_fetch():
    """When sofor_id provided (no score), stats are fetched from service."""
    svc = _make_service()

    driver_stat = MagicMock()
    driver_stat.filo_karsilastirma = 10.0

    mock_predictor = MagicMock()
    mock_predictor.is_trained = True
    mock_predictor.explain_prediction = MagicMock(
        return_value={"top_features": [{"feature": "mesafe_km", "value": 0.5}]}
    )

    svc.ensemble_service.get_predictor = MagicMock(return_value=mock_predictor)

    with (
        patch(
            "v2.modules.driver.public.get_driver_stats",
            AsyncMock(return_value=[driver_stat]),
        ) as mock_get_driver_stats,
        patch(
            "v2.modules.prediction_ml.application.prediction_service.asyncio.to_thread",
            new=AsyncMock(
                return_value={"top_features": [{"feature": "mesafe_km", "value": 0.5}]}
            ),
        ),
    ):
        result = await svc.explain_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            sofor_id=5,
        )

    assert result is not None
    mock_get_driver_stats.assert_awaited()


async def test_explain_consumption_untrained_predictor_falls_back_to_general():
    """Untrained predictor → falls back to general model (arac_id=0)."""
    svc = _make_service()

    untrained_predictor = MagicMock()
    untrained_predictor.is_trained = False

    general_predictor = MagicMock()
    general_predictor.is_trained = True
    general_predictor.explain_prediction = MagicMock(return_value={"top_features": []})

    def predictor_factory(arac_id):
        if arac_id == 1:
            return untrained_predictor
        return general_predictor

    svc.ensemble_service.get_predictor = MagicMock(side_effect=predictor_factory)

    with patch(
        "v2.modules.prediction_ml.application.prediction_service.asyncio.to_thread",
        new=AsyncMock(return_value={"top_features": []}),
    ):
        result = await svc.explain_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
        )

    assert result is not None
    # get_predictor(0) should have been called as fallback
    calls = [c.args[0] for c in svc.ensemble_service.get_predictor.call_args_list]
    assert 0 in calls


async def test_explain_consumption_sofor_id_no_stats():
    """sofor_id provided but stats empty → s_score remains None (uses 1.0)."""
    svc = _make_service()

    mock_predictor = MagicMock()
    mock_predictor.is_trained = True

    svc.ensemble_service.get_predictor = MagicMock(return_value=mock_predictor)

    with (
        patch(
            "v2.modules.driver.public.get_driver_stats",
            AsyncMock(return_value=[]),
        ),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.asyncio.to_thread",
            new=AsyncMock(return_value={"top_features": []}),
        ),
    ):
        result = await svc.explain_consumption(
            arac_id=1,
            mesafe_km=400.0,
            sofor_id=99,
        )

    assert result is not None


async def test_explain_consumption_with_route_analysis():
    """Route analysis passed → normalized and used."""
    svc = _make_service()

    mock_predictor = MagicMock()
    mock_predictor.is_trained = True

    svc.ensemble_service.get_predictor = MagicMock(return_value=mock_predictor)

    route_analysis = {
        "ratios": {"otoyol": 0.7, "devlet_yolu": 0.2, "sehir_ici": 0.1},
        "weather_factor": 1.02,
    }

    with patch(
        "v2.modules.prediction_ml.application.prediction_service.asyncio.to_thread",
        new=AsyncMock(return_value={"top_features": []}),
    ):
        result = await svc.explain_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            route_analysis=route_analysis,
        )

    assert result is not None
