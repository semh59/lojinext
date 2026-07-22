"""
Coverage tests for v2/modules/prediction_ml/application/prediction_service.py
(+ the domain/application helpers it was split into, dalga 13).

Targets: PredictionService instance methods (_build_sefer_dict,
_run_physics_fallback, predict_consumption, explain, train) plus the free
functions extracted into domain/physics_model.py, domain/route_ratios.py,
application/response_builder.py, application/ensemble_orchestration.py.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_service():
    """Build PredictionService with mocked deps."""
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
# response_builder.build_explanation_summary
# ---------------------------------------------------------------------------


def test_build_explanation_summary():
    from v2.modules.prediction_ml.application.response_builder import (
        build_explanation_summary,
    )

    summary = build_explanation_summary(
        model_used="ensemble",
        model_version="v1",
        confidence_score=0.85,
        load_ton=20.0,
        ascent_m=500.0,
        weather_factor=1.05,
    )
    assert "ensemble" in summary
    assert "0.85" in summary
    assert "20.0" in summary


# ---------------------------------------------------------------------------
# response_builder.normalize_confidence_band
# ---------------------------------------------------------------------------


def test_normalize_confidence_band_with_explicit_values():
    from v2.modules.prediction_ml.application.response_builder import (
        normalize_confidence_band,
    )

    low, high = normalize_confidence_band(
        base_value=30.0, confidence_score=0.8, confidence_low=28.0, confidence_high=32.0
    )
    assert low == 28.0
    assert high == 32.0


def test_normalize_confidence_band_computed():
    from v2.modules.prediction_ml.application.response_builder import (
        normalize_confidence_band,
    )

    low, high = normalize_confidence_band(base_value=30.0, confidence_score=0.8)
    assert low < 30.0
    assert high > 30.0


def test_normalize_confidence_band_zero_base():
    from v2.modules.prediction_ml.application.response_builder import (
        normalize_confidence_band,
    )

    low, high = normalize_confidence_band(base_value=0.0, confidence_score=0.5)
    assert low == 0.0


# ---------------------------------------------------------------------------
# route_ratios.sum_segment_km
# ---------------------------------------------------------------------------


def test_sum_segment_km_dict():
    from v2.modules.prediction_ml.domain.route_ratios import sum_segment_km

    assert sum_segment_km({"flat": 100, "up": 50, "down": 30}) == 180.0


def test_sum_segment_km_non_dict():
    from v2.modules.prediction_ml.domain.route_ratios import sum_segment_km

    assert sum_segment_km(None) == 0.0
    assert sum_segment_km("bad") == 0.0


def test_sum_segment_km_partial():
    from v2.modules.prediction_ml.domain.route_ratios import sum_segment_km

    assert sum_segment_km({"flat": 100}) == 100.0


# ---------------------------------------------------------------------------
# route_ratios.derive_route_ratios
# ---------------------------------------------------------------------------


def test_derive_route_ratios_none():
    from v2.modules.prediction_ml.domain.route_ratios import derive_route_ratios

    assert derive_route_ratios(None) is None
    assert derive_route_ratios("bad") is None


def test_derive_route_ratios_with_ratios_key():
    from v2.modules.prediction_ml.domain.route_ratios import derive_route_ratios

    result = derive_route_ratios(
        {"ratios": {"otoyol": 0.6, "devlet_yolu": 0.3, "sehir_ici": 0.1}}
    )
    assert result is not None
    assert abs(result["otoyol"] - 0.6) < 0.01


def test_derive_route_ratios_from_segments():
    from v2.modules.prediction_ml.domain.route_ratios import derive_route_ratios

    result = derive_route_ratios(
        {
            "motorway": {"flat": 300},
            "primary": {"flat": 100},
            "residential": {"flat": 50},
        }
    )
    assert result is not None
    assert "otoyol" in result


def test_derive_route_ratios_zero_total():
    from v2.modules.prediction_ml.domain.route_ratios import derive_route_ratios

    # All zeros → total_km <= 0 → None
    result = derive_route_ratios({"motorway": {"flat": 0}})
    assert result is None


def test_derive_route_ratios_highway_fallback():
    from v2.modules.prediction_ml.domain.route_ratios import derive_route_ratios

    # highway present, trunk+primary absent → trunk_km = highway_km
    result = derive_route_ratios({"highway": {"flat": 200}})
    assert result is not None
    assert result["devlet_yolu"] > 0


# ---------------------------------------------------------------------------
# route_ratios.normalize_route_analysis
# ---------------------------------------------------------------------------


def test_normalize_route_analysis_none():
    from v2.modules.prediction_ml.domain.route_ratios import normalize_route_analysis

    assert normalize_route_analysis(None) is None


def test_normalize_route_analysis_nested():
    from v2.modules.prediction_ml.domain.route_ratios import normalize_route_analysis

    result = normalize_route_analysis(
        {
            "route_analysis": {
                "ratios": {"otoyol": 0.7, "devlet_yolu": 0.2, "sehir_ici": 0.1}
            },
            "weather_factor": 1.02,
        }
    )
    assert result is not None
    assert "ratios" in result


def test_normalize_route_analysis_weather_factor_passthrough():
    from v2.modules.prediction_ml.domain.route_ratios import normalize_route_analysis

    result = normalize_route_analysis({"weather_factor": 1.1})
    assert result is not None
    assert result["weather_factor"] == 1.1


# ---------------------------------------------------------------------------
# response_builder.extract_confidence_score
# ---------------------------------------------------------------------------


def test_extract_confidence_score_valid():
    from v2.modules.prediction_ml.application.response_builder import (
        extract_confidence_score,
    )

    assert extract_confidence_score({"confidence_score": 0.75}) == 0.75


def test_extract_confidence_score_clamped():
    from v2.modules.prediction_ml.application.response_builder import (
        extract_confidence_score,
    )

    assert extract_confidence_score({"confidence_score": 1.5}) == 1.0
    assert extract_confidence_score({"confidence_score": -0.1}) == 0.0


def test_extract_confidence_score_none_input():
    from v2.modules.prediction_ml.application.response_builder import (
        extract_confidence_score,
    )

    assert extract_confidence_score(None) is None
    assert extract_confidence_score({"other": 1}) is None


# ---------------------------------------------------------------------------
# physics_model.build_base_factors
# ---------------------------------------------------------------------------


def test_build_base_factors():
    from v2.modules.prediction_ml.domain.physics_model import build_base_factors

    factors = build_base_factors(
        physics_l_100km=30.0,
        weather_factor=1.0,
        s_score=0.9,
        sofor_influence=1.02,
        ramp_factor=1.0,
        ton=20.0,
        ascent_m=200.0,
        descent_m=100.0,
        flat_distance_km=300.0,
        otoyol_ratio=0.6,
        devlet_yolu_ratio=0.3,
        sehir_ici_ratio=0.1,
        age=3,
        dorse_id=5,
        zorluk="Normal",
        bos_sefer=False,
    )
    assert factors["physics_base"] == 30.0
    assert factors["has_trailer"] == 1.0
    assert factors["vehicle_age"] == 3
    assert factors["difficulty_level"] == "Normal"


def test_build_base_factors_bos_sefer():
    from v2.modules.prediction_ml.domain.physics_model import build_base_factors

    factors = build_base_factors(
        physics_l_100km=28.0,
        weather_factor=1.0,
        s_score=None,
        sofor_influence=1.0,
        ramp_factor=1.0,
        ton=20.0,
        ascent_m=0.0,
        descent_m=0.0,
        flat_distance_km=0.0,
        otoyol_ratio=0.6,
        devlet_yolu_ratio=0.3,
        sehir_ici_ratio=0.1,
        age=0,
        dorse_id=None,
        zorluk="Kolay",
        bos_sefer=True,
    )
    assert factors["load_ton"] == 0.0
    assert factors["has_trailer"] == 0.0


# ---------------------------------------------------------------------------
# physics_model.build_vehicle_specs
# ---------------------------------------------------------------------------


def test_build_vehicle_specs_no_arac():
    from app.config import settings
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    specs, age = build_vehicle_specs(None, None, settings.VEHICLE_AGE_DEGRADATION_RATE)
    assert age == 0


def test_build_vehicle_specs_with_arac():
    from app.config import settings
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    arac = {"bos_agirlik_kg": 9000, "yil": date.today().year - 3}
    specs, age = build_vehicle_specs(arac, None, settings.VEHICLE_AGE_DEGRADATION_RATE)
    assert age == 3


def test_build_vehicle_specs_old_vehicle_degradation():
    from app.config import settings
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    arac = {
        "bos_agirlik_kg": 8000,
        "motor_verimliligi": 0.40,
        "yil": date.today().year - 10,
    }
    specs, age = build_vehicle_specs(arac, None, settings.VEHICLE_AGE_DEGRADATION_RATE)
    # Engine efficiency should be degraded
    assert specs.engine_efficiency < 0.40


def test_build_vehicle_specs_old_vehicle_degradation_rate_zero():
    """Behavior proof: age_degradation_rate=0 -> no age penalty regardless of age."""
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    arac = {
        "bos_agirlik_kg": 8000,
        "motor_verimliligi": 0.40,
        "yil": date.today().year - 20,
    }
    specs, age = build_vehicle_specs(arac, None, 0.0)
    assert specs.engine_efficiency == pytest.approx(0.40)


def test_build_vehicle_specs_old_vehicle_degradation_rate_high():
    """Behavior proof: a higher DB-configured rate produces a larger penalty."""
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    arac = {
        "bos_agirlik_kg": 8000,
        "motor_verimliligi": 0.40,
        "yil": date.today().year - 10,
    }
    _specs_low, _ = build_vehicle_specs(arac, None, 0.01)
    specs_high, _ = build_vehicle_specs(arac, None, 0.05)
    assert specs_high.engine_efficiency < _specs_low.engine_efficiency


def test_build_vehicle_specs_with_dorse():
    from app.config import settings
    from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

    arac = {"yil": 2020}
    dorse = {"bos_agirlik_kg": 7000}
    specs, age = build_vehicle_specs(arac, dorse, settings.VEHICLE_AGE_DEGRADATION_RATE)
    assert specs.trailer_empty_weight_kg == 7000


# ---------------------------------------------------------------------------
# response_builder.build_prediction_response
# ---------------------------------------------------------------------------


def test_build_prediction_response_basic():
    from v2.modules.prediction_ml.application.response_builder import (
        build_prediction_response,
    )

    resp = build_prediction_response(
        mesafe_km=500.0,
        tahmini_tuketim=32.0,
        model_used="ensemble",
        model_version="v2",
        confidence_score=0.85,
        warning_level="GREEN",
        fallback_triggered=False,
        faktorler={"physics_base": 31.0},
        insight="All good",
        explanation_summary="Test summary",
    )
    assert resp["tahmini_tuketim"] == 32.0
    assert resp["tahmini_litre"] == round(500 * 32 / 100, 1)
    assert resp["model_used"] == "ensemble"
    assert resp["warning_level"] == "GREEN"
    assert resp["fallback_triggered"] is False
    assert resp["explanation_summary"] == "Test summary"


def test_build_prediction_response_no_summary():
    from v2.modules.prediction_ml.application.response_builder import (
        build_prediction_response,
    )

    resp = build_prediction_response(
        mesafe_km=100.0,
        tahmini_tuketim=28.0,
        model_used="physics",
        model_version="v1",
        confidence_score=0.72,
        warning_level="YELLOW",
        fallback_triggered=True,
        faktorler={},
    )
    assert "Tahmin tamamlandi" in resp["explanation_summary"]


# ---------------------------------------------------------------------------
# _run_physics_fallback (kept on PredictionService — see physics_model.py docstring)
# ---------------------------------------------------------------------------


def test_run_physics_fallback_no_ensemble():
    svc = _make_service()
    ctx = {
        "_use_ensemble": False,
        "_fallback_l_100km": 30.0,
        "_base_factors": {"physics_base": 30.0},
        "_physics_insight": "OK",
        "ton": 20.0,
        "ascent_m": 100.0,
        "weather_factor": 1.0,
    }
    resp = svc._run_physics_fallback({}, ctx, 400.0)
    assert resp["model_used"] == "linear"
    assert resp["fallback_triggered"] is False
    assert resp["faktorler"]["fallback_reason"] == "physics_mode_selected"


def test_run_physics_fallback_ensemble_unavailable():
    svc = _make_service()
    ctx = {
        "_use_ensemble": True,
        "_fallback_l_100km": 33.0,
        "_base_factors": {},
        "_physics_insight": None,
        "ton": 15.0,
        "ascent_m": 0.0,
        "weather_factor": 1.02,
    }
    resp = svc._run_physics_fallback({}, ctx, 300.0)
    assert resp["model_used"] == "physics"
    assert resp["fallback_triggered"] is True
    assert resp["faktorler"]["fallback_reason"] == "ensemble_unavailable_or_disabled"


# ---------------------------------------------------------------------------
# ensemble_orchestration.process_ensemble_result
# ---------------------------------------------------------------------------


def test_process_ensemble_result_green():
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        process_ensemble_result,
    )

    ensemble_result = {
        "tahmin_l_100km": 31.5,
        "confidence_score": 0.85,
        "model_version": "ensemble-v2.0",
        "ml_correction": 1.2,
        "champion": "xgboost",
        "challenger": "physics",
    }
    resp = process_ensemble_result(
        ensemble_result=ensemble_result,
        fallback_l_100km=30.0,
        mesafe_km=500.0,
        ton=20.0,
        ascent_m=100.0,
        bos_sefer=False,
        weather_factor=1.0,
        base_factors={"physics_base": 30.0},
        physics_insight="Normal",
    )
    assert resp["warning_level"] == "GREEN"
    assert resp["fallback_triggered"] is False
    assert resp["tahmini_tuketim"] == 31.5


def test_process_ensemble_result_red_triggers_fallback():
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        process_ensemble_result,
    )

    ensemble_result = {
        "tahmin_l_100km": 50.0,
        "confidence_score": 0.20,  # below RED threshold 0.40
        "model_version": "ensemble-v2.0",
        "ml_correction": 0.0,
    }
    resp = process_ensemble_result(
        ensemble_result=ensemble_result,
        fallback_l_100km=30.0,
        mesafe_km=500.0,
        ton=20.0,
        ascent_m=0.0,
        bos_sefer=False,
        weather_factor=1.0,
        base_factors={},
        physics_insight=None,
    )
    assert resp["warning_level"] == "RED"
    assert resp["fallback_triggered"] is True
    assert resp["tahmini_tuketim"] == 30.0


def test_process_ensemble_result_yellow():
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        process_ensemble_result,
    )

    ensemble_result = {
        "tahmin_l_100km": 32.0,
        "confidence_score": 0.50,  # between RED 0.40 and YELLOW 0.60
        "model_version": "v2",
        "ml_correction": 0.5,
    }
    resp = process_ensemble_result(
        ensemble_result=ensemble_result,
        fallback_l_100km=30.0,
        mesafe_km=400.0,
        ton=18.0,
        ascent_m=0.0,
        bos_sefer=False,
        weather_factor=1.0,
        base_factors={},
        physics_insight=None,
    )
    assert resp["warning_level"] == "YELLOW"
    assert resp["fallback_triggered"] is False


def test_process_ensemble_result_missing_confidence():
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        process_ensemble_result,
    )

    ensemble_result = {
        "tahmin_l_100km": 35.0,
        # no confidence_score key
        "model_version": "v1",
    }
    resp = process_ensemble_result(
        ensemble_result=ensemble_result,
        fallback_l_100km=30.0,
        mesafe_km=400.0,
        ton=18.0,
        ascent_m=0.0,
        bos_sefer=False,
        weather_factor=1.0,
        base_factors={},
        physics_insight=None,
    )
    assert resp["warning_level"] == "RED"
    assert resp["fallback_triggered"] is True


def test_process_ensemble_result_guven_araligi():
    from v2.modules.prediction_ml.application.ensemble_orchestration import (
        process_ensemble_result,
    )

    ensemble_result = {
        "tahmin_l_100km": 31.0,
        "confidence_score": 0.80,
        "model_version": "v2",
        "guven_araligi": [29.0, 33.0],
    }
    resp = process_ensemble_result(
        ensemble_result=ensemble_result,
        fallback_l_100km=30.0,
        mesafe_km=500.0,
        ton=20.0,
        ascent_m=0.0,
        bos_sefer=False,
        weather_factor=1.0,
        base_factors={},
        physics_insight=None,
    )
    assert resp["confidence_low"] == 29.0
    assert resp["confidence_high"] == 33.0


# ---------------------------------------------------------------------------
# _build_sefer_dict
# ---------------------------------------------------------------------------


async def test_build_sefer_dict():
    svc = _make_service()
    arac = {"marka": "Volvo", "model": "FH", "yil": 2020, "motor_hacmi": 12000}
    sofor = {"id": 5, "score": 0.9}
    dorse = {"id": 3}
    result = await svc._build_sefer_dict(
        arac=arac,
        sofor=sofor,
        dorse=dorse,
        mesafe_km=500.0,
        ton=20.0,
        ascent_m=100.0,
        descent_m=50.0,
        flat_distance_km=350.0,
        target_date=date.today(),
        bos_sefer=False,
        route_analysis=None,
        weather_factor=1.0,
    )
    assert result["mesafe_km"] == 500.0
    assert result["sofor_id"] == 5
    assert result["dorse_id"] == 3
    assert result["marka"] == "Volvo"


async def test_build_sefer_dict_bos_sefer():
    svc = _make_service()
    result = await svc._build_sefer_dict(
        arac={},
        sofor=None,
        dorse=None,
        mesafe_km=300.0,
        ton=20.0,
        ascent_m=0.0,
        descent_m=0.0,
        flat_distance_km=300.0,
        target_date=date.today(),
        bos_sefer=True,
        route_analysis=None,
        weather_factor=1.0,
    )
    # bos_sefer → ton forced to 0
    assert result["ton"] == 0.0
    assert result["sofor_id"] is None


# ---------------------------------------------------------------------------
# predict_consumption — physics fallback path (use_ensemble=False)
# ---------------------------------------------------------------------------


async def test_predict_consumption_physics_only():
    """Physics-only path: use_ensemble=False, no DB lookup needed."""
    svc = _make_service()

    physics_result = _make_physics_result(32.0)

    with (
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=AsyncMock())),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
    ):
        # Provide pre-fetched objects to skip DB
        mock_arac = SimpleNamespace(**{"id": 1, "marka": "Volvo", "yil": 2020})

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=False,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"
    assert result["model_used"] == "linear"
    assert result["fallback_triggered"] is False


async def test_predict_consumption_ensemble_success():
    """Ensemble path: ensemble returns success."""
    svc = _make_service()
    physics_result = _make_physics_result(30.0)

    ensemble_result = {
        "success": True,
        "tahmin_l_100km": 31.5,
        "confidence_score": 0.85,
        "model_version": "ensemble-v2.0",
        "ml_correction": 1.0,
        "champion": "xgboost",
        "challenger": "physics",
    }

    mock_arac = SimpleNamespace(**{"id": 1, "marka": "Volvo", "yil": 2020})

    with (
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_physics_model",
            new=AsyncMock(return_value=physics_result),
        ),
        patch.object(svc, "_log_prediction_to_ai", new=AsyncMock()),
        patch(
            "v2.modules.prediction_ml.application.prediction_service.run_ensemble_prediction",
            new=AsyncMock(return_value=ensemble_result),
        ),
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = False
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=500.0,
            ton=20.0,
            use_ensemble=True,
            _arac_obj=mock_arac,
            _sofor_obj=None,
            _dorse_obj=None,
        )

    assert result["status"] == "success"


async def test_predict_consumption_ensemble_fails_fallback():
    """Ensemble returns no success → physics fallback used."""
    svc = _make_service()
    physics_result = _make_physics_result(30.0)

    mock_arac = SimpleNamespace(**{"id": 1, "yil": 2020})

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
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = False
        mock_settings.AI_CONFIDENCE_THRESHOLD_RED = 0.40
        mock_settings.AI_CONFIDENCE_THRESHOLD_YELLOW = 0.60
        mock_settings.MAX_AGE_DEGRADATION = 0.15
        mock_settings.VEHICLE_AGE_DEGRADATION_RATE = 0.015

        result = await svc.predict_consumption(
            arac_id=1,
            mesafe_km=400.0,
            use_ensemble=True,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"
    assert result["fallback_triggered"] is True


async def test_predict_consumption_with_route_analysis():
    """Route analysis with ratios and weather_factor keys."""
    svc = _make_service()
    physics_result = _make_physics_result(29.0)

    mock_arac = SimpleNamespace(**{"id": 2, "yil": 2021})

    route_analysis = {
        "ratios": {"otoyol": 0.7, "devlet_yolu": 0.2, "sehir_ici": 0.1},
        "weather_factor": 1.05,
    }

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
        patch(
            "v2.modules.prediction_ml.domain.vehicle_health_adjustment.apply_maintenance_factor",
            side_effect=lambda p, f, r: p,
        ),
        patch("v2.modules.prediction_ml.application.prediction_service.settings") as mock_settings,
    ):
        mock_settings.MAINTENANCE_FACTOR_ENABLED = False

        result = await svc.predict_consumption(
            arac_id=2,
            mesafe_km=400.0,
            ton=15.0,
            use_ensemble=False,
            route_analysis=route_analysis,
            _arac_obj=mock_arac,
        )

    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# _log_prediction_to_ai
# ---------------------------------------------------------------------------


async def test_log_prediction_to_ai_no_error():
    svc = _make_service()
    mock_smart_ai = MagicMock()
    mock_smart_ai.teach = AsyncMock()

    with patch("v2.modules.prediction_ml.application.prediction_service.asyncio") as mock_asyncio:
        mock_asyncio.create_task = MagicMock()
        with patch(
            "v2.modules.ai_assistant.public.get_smart_ai",
            return_value=mock_smart_ai,
            create=True,
        ):
            # Should not raise
            await svc._log_prediction_to_ai(1, 500.0, 32.0)


# ---------------------------------------------------------------------------
# train_xgboost_model
# ---------------------------------------------------------------------------


async def test_train_xgboost_model_success():
    svc = _make_service()
    svc.ensemble_service.train_for_vehicle = AsyncMock(
        return_value={
            "success": True,
            "ensemble_r2": 0.92,
            "sample_count": 100,
            "metrics": {},
        }
    )

    with patch(
        "app.infrastructure.audit.audit_logger.log_audit_event", new=AsyncMock()
    ):
        result = await svc.train_xgboost_model(arac_id=1, user_id=5)

    assert result["status"] == "success"
    assert result["r2_score"] == 0.92
    assert result["sample_count"] == 100


async def test_train_xgboost_model_failure():
    svc = _make_service()
    svc.ensemble_service.train_for_vehicle = AsyncMock(
        return_value={
            "success": False,
            "ensemble_r2": 0.0,
            "sample_count": 5,
            "metrics": {},
        }
    )

    with patch(
        "app.infrastructure.audit.audit_logger.log_audit_event", new=AsyncMock()
    ):
        result = await svc.train_xgboost_model(arac_id=99)

    assert result["status"] == "failure"


# ---------------------------------------------------------------------------
# get_prediction_service singleton
# ---------------------------------------------------------------------------


def test_get_prediction_service_singleton():
    """Delegates to the DI container — same instance on every call (dalga 17
    fix: this used to be an independent module-level singleton, out of sync
    with app/core/container.py's own copy; now both paths share one object)."""
    from v2.modules.prediction_ml.application.prediction_service import (
        get_prediction_service,
    )

    s1 = get_prediction_service()
    s2 = get_prediction_service()
    assert s1 is s2
