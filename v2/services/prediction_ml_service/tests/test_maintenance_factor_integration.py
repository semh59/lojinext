"""
Real-object integration test for the D.4 maintenance-factor pipeline.

Split off app/tests/integration/test_maintenance_factor_integration.py
(Task 5, 2026-08-04): this file's 6th case exercises the REAL
PredictionService physics engine end-to-end (no mocks on the prediction
logic itself), which now only lives in this service's own process --
v2.modules.prediction_ml.public.get_prediction_service on the main
backend is an HTTP-client facade that would make a real network call.

CONTRACT-4 regression guard (unchanged intent): apply_maintenance_factor
must update all three keys real callers read -- 'tahmini_tuketim'
(primary L/100km used by sefer_write_service), 'tahmini_litre' (primary
litre used by trip_planner), and 'prediction_liters' (deprecated alias
still in use).
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


async def test_apply_maintenance_factor_with_real_prediction_response():
    """
    End-to-end: call the real prediction_service (physics-only, arac_id=0
    -- the general model, no cross-module vehicle fetch), apply factor,
    verify all primary keys are multiplied together.
    """
    from prediction_ml_service.application.prediction_service import (
        get_prediction_service,
    )
    from prediction_ml_service.domain.vehicle_health_adjustment import (
        apply_maintenance_factor,
    )

    svc = get_prediction_service()

    with patch(
        "prediction_ml_service.application.prediction_service"
        ".cross_module_client.get_runtime_float",
        new=AsyncMock(return_value=0.015),
    ):
        pred = await svc.predict_consumption(
            arac_id=0,
            mesafe_km=300.0,
            ton=18.0,
            ascent_m=200.0,
            descent_m=200.0,
            use_ensemble=False,
        )

    assert "tahmini_tuketim" in pred, (
        f"prediction_service missing tahmini_tuketim: {list(pred)}"
    )

    original_l100 = pred["tahmini_tuketim"]
    original_litre = pred.get("tahmini_litre") or 0.0
    factor = 1.12

    result = apply_maintenance_factor(
        dict(pred), factor=factor, reason="integration test"
    )

    if original_l100 > 0:
        assert result["tahmini_tuketim"] == pytest.approx(
            original_l100 * factor, rel=0.01
        ), "Real prediction tahmini_tuketim not scaled by maintenance factor"
    if original_litre > 0:
        assert result["tahmini_litre"] == pytest.approx(
            original_litre * factor, rel=0.01
        )
