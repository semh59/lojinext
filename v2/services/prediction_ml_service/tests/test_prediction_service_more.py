"""
Additional coverage for prediction_ml_service/application/prediction_service.py
(moved whole with the service extraction, Task 5, 2026-08-04).

Rewired against the real current source: entity fetches (arac/sofor/dorse)
go through cross_module_client over HTTP now, not a shared_kernel
UnitOfWork; the D.4 maintenance-factor health-input fetch uses this
service's own ServiceUnitOfWork + fetch_health_input (mocked directly here
rather than the DB session, to stay a real unit test); AI teach-back posts
via cross_module_client.teach instead of an in-process
ai_assistant.public.get_smart_ai() call; XAI driver-stats lookup goes
through cross_module_client.get_driver_stats.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

PS_MODULE = "prediction_ml_service.application.prediction_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    from prediction_ml_service.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService.__new__(PredictionService)
    svc.ensemble_service = MagicMock()
    svc.ensemble_service.get_predictor = MagicMock()
    return svc


def _make_physics_result(l_100km: float = 32.0, insight: str = "Normal"):
    r = MagicMock()
    r.consumption_l_100km = l_100km
    r.insight = insight
    return r


def _base_settings_mock(mock_settings, maintenance_enabled=False):
    mock_settings.MAINTENANCE_FACTOR_ENABLED = maintenance_enabled
    mock_settings.MAX_AGE_DEGRADATION = 0.15
    mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015
    mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
    mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60


# ---------------------------------------------------------------------------
# _run_ensemble_prediction: exception path
# ---------------------------------------------------------------------------


async def test_run_ensemble_prediction_exception_returns_none():
    """When ensemble_service.predict_consumption raises → returns None."""
    from prediction_ml_service.application.ensemble_orchestration import (
        run_ensemble_prediction,
    )

    svc = _make_service()
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

    result = await run_ensemble_prediction(
        svc.ensemble_service,
        1,
        sefer_dict,
        date.today(),
    )

    assert result is None


# ---------------------------------------------------------------------------
# _run_physics_model: granular_nodes path
# ---------------------------------------------------------------------------


async def test_run_physics_model_granular_nodes_path():
    """When normalized_route has granular_nodes → predict_granular is called."""
    from prediction_ml_service.domain.physics_fuel_predictor import VehicleSpecs
    from prediction_ml_service.domain.physics_model import run_physics_model

    granular_nodes = [
        {"lat": 40.0, "lon": 29.0, "elevation_m": 100},
        {"lat": 39.9, "lon": 30.0, "elevation_m": 150},
        {"lat": 39.8, "lon": 31.0, "elevation_m": 200},
    ]

    normalized_route = {
        "granular_nodes": granular_nodes,
        "historical_stats": {"mean": 31.0},
    }

    specs = VehicleSpecs()

    mock_granular_result = MagicMock()
    mock_granular_result.consumption_l_100km = 31.5
    mock_granular_result.insight = "P2P granular"

    with patch(
        "prediction_ml_service.domain.physics_model.asyncio.to_thread",
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
# predict_consumption: entity fetch over HTTP when not pre-fetched
# ---------------------------------------------------------------------------


async def test_predict_consumption_fetches_arac_over_http_when_not_provided():
    """When _arac_obj not provided → fetches arac via cross_module_client."""
    svc = _make_service()

    arac_payload = {
        "id": 1,
        "marka": "Volvo",
        "yil": 2020,
        "bos_agirlik_kg": 9000,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
    }

    physics_result = _make_physics_result(32.0)
    mock_get_vehicle = AsyncMock(return_value=arac_payload)

    with (
        patch(
            f"{PS_MODULE}.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(f"{PS_MODULE}.cross_module_client.get_vehicle", mock_get_vehicle),
        patch(
            f"{PS_MODULE}.cross_module_client.get_runtime_float",
            new=AsyncMock(return_value=0.015),
        ),
        patch(f"{PS_MODULE}.settings") as mock_settings,
    ):
        _base_settings_mock(mock_settings)

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
        )

    assert result["status"] == "success"
    mock_get_vehicle.assert_awaited_with(1)


async def test_predict_consumption_fetches_sofor_over_http():
    """When sofor_id provided and _sofor_obj is None → fetches via cross_module_client."""
    svc = _make_service()

    arac_payload = {"id": 1, "yil": 2020, "bos_agirlik_kg": 9000}
    sofor_payload = {"id": 5, "ad": "Ali"}

    physics_result = _make_physics_result(31.0)
    mock_get_driver = AsyncMock(return_value=sofor_payload)

    with (
        patch(
            f"{PS_MODULE}.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            f"{PS_MODULE}.cross_module_client.get_vehicle",
            AsyncMock(return_value=arac_payload),
        ),
        patch(f"{PS_MODULE}.cross_module_client.get_driver", mock_get_driver),
        patch(
            f"{PS_MODULE}.cross_module_client.get_runtime_float",
            new=AsyncMock(return_value=0.015),
        ),
        patch(f"{PS_MODULE}.settings") as mock_settings,
    ):
        _base_settings_mock(mock_settings)

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=400.0,
            ton=15.0,
            sofor_id=5,
            use_ensemble=False,
        )

    assert result["status"] == "success"
    mock_get_driver.assert_awaited_with(5)


# ---------------------------------------------------------------------------
# predict_consumption: MAINTENANCE_FACTOR_ENABLED (D.4) path
# ---------------------------------------------------------------------------


async def test_predict_consumption_maintenance_factor_applied():
    """MAINTENANCE_FACTOR_ENABLED=True with health input → factor applied."""
    svc = _make_service()

    mock_arac = {"id": 1, "yil": 2020, "bos_agirlik_kg": 9000}
    physics_result = _make_physics_result(32.0)

    mock_h_res = MagicMock()
    mock_h_res.factor = 1.05
    mock_h_res.reason = "overdue_maintenance"

    with (
        patch(
            f"{PS_MODULE}.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(f"{PS_MODULE}.run_ensemble_prediction", new=AsyncMock(return_value=None)),
        patch(
            f"{PS_MODULE}.cross_module_client.get_runtime_float",
            new=AsyncMock(return_value=0.015),
        ),
        patch(f"{PS_MODULE}.settings") as mock_settings,
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment"
            ".apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment"
            ".compute_maintenance_factor",
            return_value=mock_h_res,
        ),
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment.fetch_health_input",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aenter__",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aexit__",
            new=AsyncMock(return_value=False),
        ),
    ):
        _base_settings_mock(mock_settings, maintenance_enabled=True)

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

    mock_arac = {"id": 1, "yil": 2020, "bos_agirlik_kg": 9000}
    physics_result = _make_physics_result(32.0)

    with (
        patch(
            f"{PS_MODULE}.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(f"{PS_MODULE}.run_ensemble_prediction", new=AsyncMock(return_value=None)),
        patch(
            f"{PS_MODULE}.cross_module_client.get_runtime_float",
            new=AsyncMock(return_value=0.015),
        ),
        patch(f"{PS_MODULE}.settings") as mock_settings,
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment"
            ".apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment.fetch_health_input",
            new=AsyncMock(side_effect=RuntimeError("health fetch fail")),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aenter__",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aexit__",
            new=AsyncMock(return_value=False),
        ),
    ):
        _base_settings_mock(mock_settings, maintenance_enabled=True)

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=400.0,
            ton=15.0,
            use_ensemble=False,
            _arac_obj=mock_arac,
        )

    # Should still succeed (health input failure is non-fatal)
    assert result["status"] == "success"


async def test_predict_consumption_maintenance_factor_compute_exception():
    """compute_maintenance_factor raises → warning logged, continue without factor."""
    svc = _make_service()

    mock_arac = {"id": 1, "yil": 2020, "bos_agirlik_kg": 9000}
    physics_result = _make_physics_result(32.0)

    with (
        patch(
            f"{PS_MODULE}.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(f"{PS_MODULE}.run_ensemble_prediction", new=AsyncMock(return_value=None)),
        patch(
            f"{PS_MODULE}.cross_module_client.get_runtime_float",
            new=AsyncMock(return_value=0.015),
        ),
        patch(f"{PS_MODULE}.settings") as mock_settings,
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment"
            ".apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment"
            ".compute_maintenance_factor",
            side_effect=RuntimeError("compute fail"),
        ),
        patch(
            "prediction_ml_service.domain.vehicle_health_adjustment.fetch_health_input",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aenter__",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "prediction_ml_service.infrastructure.service_uow.ServiceUnitOfWork"
            ".__aexit__",
            new=AsyncMock(return_value=False),
        ),
    ):
        _base_settings_mock(mock_settings, maintenance_enabled=True)

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# _log_prediction_to_ai: background AI teach-back via cross_module_client
# ---------------------------------------------------------------------------


async def test_log_prediction_to_ai_teach_exception_swallowed():
    """cross_module_client.teach raises → exception swallowed (inner except)."""
    svc = _make_service()

    with patch(
        f"{PS_MODULE}.cross_module_client.teach",
        new=AsyncMock(side_effect=RuntimeError("teach fail")),
    ):
        # Should not raise -- _safe_teach catches internally and the
        # outer create_task/add_done_callback plumbing has its own guard too.
        await svc._log_prediction_to_ai(1, 500.0, 32.0)


async def test_log_prediction_to_ai_creates_task():
    """_log_prediction_to_ai creates a background task that calls teach."""
    svc = _make_service()

    mock_teach = AsyncMock()

    with patch(f"{PS_MODULE}.cross_module_client.teach", mock_teach):
        await svc._log_prediction_to_ai(1, 500.0, 32.0)
        # Let the fire-and-forget background task actually run once.
        import asyncio

        await asyncio.sleep(0)

    mock_teach.assert_awaited_once()


# ---------------------------------------------------------------------------
# explain_consumption: sofor stats fetch + untrained fallback
# ---------------------------------------------------------------------------


async def test_explain_consumption_sofor_id_stats_fetch():
    """When sofor_id provided (no score), stats are fetched via cross_module_client."""
    svc = _make_service()

    driver_stat = {"filo_karsilastirma": 10.0}

    mock_predictor = MagicMock()
    mock_predictor.is_trained = True
    mock_predictor.explain_prediction = MagicMock(
        return_value={"top_features": [{"feature": "mesafe_km", "value": 0.5}]}
    )

    svc.ensemble_service.get_predictor = MagicMock(return_value=mock_predictor)

    with (
        patch(
            f"{PS_MODULE}.cross_module_client.get_driver_stats",
            AsyncMock(return_value=[driver_stat]),
        ) as mock_get_driver_stats,
        patch(
            f"{PS_MODULE}.asyncio.to_thread",
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
        f"{PS_MODULE}.asyncio.to_thread",
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
            f"{PS_MODULE}.cross_module_client.get_driver_stats",
            AsyncMock(return_value=[]),
        ),
        patch(
            f"{PS_MODULE}.asyncio.to_thread",
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
        f"{PS_MODULE}.asyncio.to_thread",
        new=AsyncMock(return_value={"top_features": []}),
    ):
        result = await svc.explain_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            route_analysis=route_analysis,
        )

    assert result is not None
