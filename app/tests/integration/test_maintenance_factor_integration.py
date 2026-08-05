"""
Real-object integration test for vehicle_health_factor.apply_maintenance_factor.

CONTRACT-4 regression guard: the function must update all three keys that
callers read — 'tahmini_tuketim' (primary L/100km used by sefer_write_service),
'tahmini_litre' (primary litre used by trip_planner), and 'prediction_liters'
(deprecated alias still in use). Previously only 'prediction_liters' was updated
so the maintenance factor was silently discarded before it reached the DB column
seferler.tahmini_tuketim.
"""

import pytest

pytestmark = pytest.mark.integration


async def test_apply_maintenance_factor_updates_tahmini_tuketim():
    """
    apply_maintenance_factor must multiply 'tahmini_tuketim' (L/100km).
    sefer_write_service._extract_prediction_values reads this as the primary
    key; if not updated the DB column receives the unadjusted value.
    """
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {
        "tahmini_tuketim": 30.0,
        "tahmini_litre": 120.0,
        "prediction_liters": 120.0,
    }
    result = apply_maintenance_factor(payload, factor=1.10, reason="PERIYODIK gecikti")

    assert result["tahmini_tuketim"] == pytest.approx(33.0, abs=0.1), (
        "CONTRACT-4: tahmini_tuketim not multiplied — "
        "maintenance factor would be silently discarded in DB write"
    )


async def test_apply_maintenance_factor_updates_tahmini_litre():
    """
    apply_maintenance_factor must multiply 'tahmini_litre'.
    trip_planner reads this key for vehicle fuel ranking.
    """
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {
        "tahmini_tuketim": 30.0,
        "tahmini_litre": 120.0,
        "prediction_liters": 120.0,
    }
    result = apply_maintenance_factor(payload, factor=1.10, reason="PERIYODIK gecikti")

    assert result["tahmini_litre"] == pytest.approx(132.0, abs=0.1), (
        "CONTRACT-4: tahmini_litre not multiplied — "
        "trip_planner vehicle ranking would use unadjusted value"
    )


async def test_apply_maintenance_factor_updates_all_three_keys():
    """Full three-key contract: all three must be multiplied by the same factor."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    factor = 1.07
    payload = {
        "tahmini_tuketim": 28.0,
        "tahmini_litre": 126.0,
        "prediction_liters": 126.0,
    }
    result = apply_maintenance_factor(payload, factor=factor, reason="test")

    expected_l100 = pytest.approx(28.0 * factor, abs=0.01)
    expected_litre = pytest.approx(126.0 * factor, abs=0.01)

    assert result["tahmini_tuketim"] == expected_l100
    assert result["tahmini_litre"] == expected_litre
    assert result["prediction_liters"] == expected_litre
    assert result["faktorler"]["maintenance_factor"] == factor


async def test_apply_maintenance_factor_factor_one_is_noop():
    """factor=1.0 must return unchanged payload (no-op path)."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {
        "tahmini_tuketim": 30.0,
        "tahmini_litre": 120.0,
        "prediction_liters": 120.0,
    }
    result = apply_maintenance_factor(payload, factor=1.0, reason="no change")

    assert result["tahmini_tuketim"] == 30.0
    assert result["tahmini_litre"] == 120.0
    assert result["prediction_liters"] == 120.0


async def test_apply_maintenance_factor_missing_keys_graceful():
    """Payload with only prediction_liters (legacy) still works."""
    from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    payload = {"prediction_liters": 100.0}
    result = apply_maintenance_factor(payload, factor=1.10, reason="test")

    assert result["prediction_liters"] == pytest.approx(110.0, abs=0.1)
    assert "tahmini_tuketim" not in result
    assert "tahmini_litre" not in result


# The 6th end-to-end case (real prediction_service physics pipeline +
# apply_maintenance_factor) moved to
# v2/services/prediction_ml_service/tests/test_maintenance_factor_integration.py
# with the Task 5 service extraction (2026-08-04) -- the real
# PredictionService/physics engine now lives in that process, not here;
# v2.modules.prediction_ml.public.get_prediction_service is an HTTP-client
# facade now, so calling it here would be a real network call to a
# service that isn't running in this test environment.
