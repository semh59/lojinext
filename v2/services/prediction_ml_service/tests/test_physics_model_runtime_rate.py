"""
Split off app/tests/unit/test_services/test_runtime_config.py (missed in
the original Task 5 test-fix punch list, caught by a real CI lint run
2026-08-05): build_vehicle_specs only lives in this service's own
package now. Mechanical import-path fix only, no behavioral changes.
"""

from datetime import date

import pytest
from prediction_ml_service.domain.physics_model import build_vehicle_specs


def test_build_vehicle_specs_uses_resolved_rate_not_settings():
    """Behavior proof: _build_vehicle_specs no longer reads
    settings.VEHICLE_AGE_DEGRADATION_RATE directly -- it uses whatever
    rate the caller (predict_consumption, resolved at the async boundary)
    passes in. Rate 0 -> no age penalty; rate 0.05 -> a real penalty.
    """
    arac = {
        "bos_agirlik_kg": 8000,
        "motor_verimliligi": 0.40,
        "yil": date.today().year - 10,
    }
    specs_no_penalty, _ = build_vehicle_specs(arac, None, 0.0)
    specs_penalized, _ = build_vehicle_specs(arac, None, 0.05)

    assert specs_no_penalty.engine_efficiency == pytest.approx(0.40)
    assert specs_penalized.engine_efficiency < 0.40
    assert specs_penalized.engine_efficiency < specs_no_penalty.engine_efficiency
