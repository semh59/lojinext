import pytest

from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    HybridFuelPredictor,
    PhysicsBasedFuelPredictor,
    RouteConditions,
)


@pytest.fixture
def predictor():
    return PhysicsBasedFuelPredictor()


def test_payload_sensitivity(predictor):
    """
    Test how payload affects consumption on flat vs hills.
    """
    v_ms = 80 / 3.6
    flat_segment = [(10000.0, v_ms, 0.0)]  # 10km flat

    # 1. Empty Trip (14.5t)
    empty_pred = predictor.predict_granular(flat_segment, load_ton=0.0)

    # 2. Standard Load (20.0t payload -> 34.5t total)
    std_pred = predictor.predict_granular(flat_segment, load_ton=20.0)

    # 3. Heavy Load (30.0t payload -> 44.5t total)
    heavy_pred = predictor.predict_granular(flat_segment, load_ton=30.0)

    print(f"\n[DEEP] Payload Empty (14.5t): {empty_pred.consumption_l_100km} L/100km")
    print(f"[DEEP] Payload Standard (34.5t): {std_pred.consumption_l_100km} L/100km")
    print(f"[DEEP] Payload Heavy (44.5t): {heavy_pred.consumption_l_100km} L/100km")

    assert (
        heavy_pred.consumption_l_100km
        > std_pred.consumption_l_100km
        > empty_pred.consumption_l_100km
    )


def test_hybrid_learning():
    """
    Test HybridFuelPredictor learning from historical errors.
    """
    predictor = HybridFuelPredictor()
    route = RouteConditions(distance_km=100.0, load_ton=20.0)

    # Initial state
    p1 = predictor.predict(route)
    initial_liters = p1.total_liters

    # Simulate a series of "Actual" readings where vehicle is 20% THIRSTIER
    for _ in range(10):
        actual = initial_liters * 1.20
        predictor.learn_from_actual(initial_liters, actual)

    assert predictor.correction_factor > 1.10

    # New prediction should be higher
    p2 = predictor.predict(route)
    assert p2.total_liters > p1.total_liters


def test_extreme_downhill_momentum(predictor):
    """
    Verify that extreme downhill doesn't produce negative fuel or absurdly low values
    """
    v_ms = 60 / 3.6
    descent = [(5000.0, v_ms, -500.0)]  # 10% grade

    pred = predictor.predict_granular(descent, load_ton=20.0)
    print(f"\n[DEEP] Extreme Downhill (10%): {pred.consumption_l_100km} L/100km")

    # Validation: still positive, finite and strongly reduced by gravity recovery
    assert pred.consumption_l_100km > 0
    assert pred.consumption_l_100km < 2.0
    assert pred.insight is not None


if __name__ == "__main__":
    p = PhysicsBasedFuelPredictor()
    test_payload_sensitivity(p)
    test_hybrid_learning()
    test_extreme_downhill_momentum(p)
