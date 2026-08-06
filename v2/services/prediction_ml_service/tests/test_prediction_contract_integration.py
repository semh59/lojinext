"""
Real integration test for the prediction_service response-shape contract.

Split off app/tests/integration/test_prediction_contract_integration.py
(Task 5, 2026-08-04): this case exercises the real physics engine
end-to-end with zero mocks on the prediction logic itself -- that only
lives in this service's own process now.

CONTRACT-4-adjacent guard: prediction_service.predict_consumption must
return a dict with 'tahmini_tuketim' as the primary L/100km key (not
'prediction_l_100km'), plus 'confidence_score' in [0,1] and
'fallback_triggered' present -- consumers on the main backend
(anomaly_detector, driver_stats) depend on this exact shape (see their
own contract tests, mocked at the cross-process boundary now).
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


async def test_prediction_service_returns_tahmini_tuketim():
    """
    prediction_service.predict_consumption must return a dict with
    'tahmini_tuketim' as the primary L/100km key (not 'prediction_l_100km').
    Also asserts 'confidence_score' is present.

    Uses arac_id=0 (general model, no cross-module vehicle fetch needed) to
    stay a pure in-process test of the physics pipeline -- fetching a real
    vehicle over HTTP from the fleet module is a separate, already-covered
    cross-module-client concern.
    """
    from prediction_ml_service.application.prediction_service import (
        get_prediction_service,
    )

    svc = get_prediction_service()

    with patch(
        "prediction_ml_service.application.prediction_service"
        ".cross_module_client.get_runtime_float",
        new=AsyncMock(return_value=0.015),
    ):
        result = await svc.predict_consumption(
            arac_id=0,
            mesafe_km=300.0,
            ton=18.0,
            ascent_m=500.0,
            descent_m=500.0,
            use_ensemble=False,
        )

    # Primary contract: key name must be tahmini_tuketim
    assert "tahmini_tuketim" in result, (
        f"'tahmini_tuketim' missing from prediction response. Got keys: {list(result)}"
    )
    assert result["tahmini_tuketim"] > 0, "Expected a positive L/100km estimate"

    # confidence_score must be present and valid
    assert "confidence_score" in result, (
        f"'confidence_score' missing. Keys: {list(result)}"
    )
    assert 0.0 <= result["confidence_score"] <= 1.0, (
        f"confidence_score out of [0,1]: {result['confidence_score']}"
    )

    assert "fallback_triggered" in result
