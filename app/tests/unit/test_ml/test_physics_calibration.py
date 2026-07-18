"""Segment-tractive kalibrasyon sağlığı (fiziksel sabitler + slope + range).

NOT: Kalibrasyon hedefi 10 GERÇEK referans rota (farklı hız/grade), tek-nokta
flat-80 değil — flat-80 drag/parazit'i ayıramıyor. Gerçek-rota 9/10 GREEN
validasyonu scripts/validate_tractive_offline.py + sonuç dokümanında (DB
gerektirir). Bu testler DB-bağımsız sağlık kontrolü.
"""

import pytest

from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
)

pytestmark = pytest.mark.unit

EMPTY = 8000 + 6500


def _flat(payload_t, v_kmh=80.0):
    p = PhysicsBasedFuelPredictor()
    m = EMPTY + payload_t * 1000
    return p.predict_segment_tractive(
        [(100000.0, v_kmh / 3.6, 0.0)], total_mass_kg=m
    ).consumption_l_100km


def test_payload_slope_preserved():
    # Payload slope literatür hedefi 0.473 (trailer_rr 0.00738) — kalibrasyondan bağımsız.
    slope = (_flat(25) - _flat(12)) / 13.0
    assert 0.45 <= slope <= 0.50


def test_flat_consumption_realistic_and_monotonic():
    # Düz-yol tüketimi gerçekçi bantta ve yükle monoton artan.
    c12, c18, c25 = _flat(12), _flat(18), _flat(25)
    assert c12 < c18 < c25  # monoton
    assert 24.0 <= c12 <= 30.0  # 12t düz-yol gerçekçi
    assert 30.0 <= c25 <= 37.0  # 25t düz-yol gerçekçi


def test_calibration_constants_physical():
    from app.config import settings

    # VECTO non-aero TIR + gerçekçi aksesuar bandları (overfit guard).
    assert 5.3 <= settings.PHYSICS_DRAG_CDA_M2 <= 7.5
    assert 3.0 <= settings.PHYSICS_PARASITIC_KW <= 12.0
    assert 0.40 <= settings.PHYSICS_ENGINE_BSFC <= 0.46
    assert 0.90 <= settings.PHYSICS_DRIVELINE_EFF <= 0.98
