from app.core.ml.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    VehicleSpecs,
)


def test_terrain_variations():
    """
    Test various terrain profiles to verify realism.
    1. Flat (10km)
    2. Realistic Hilly (3% sawtooth)
    3. Extreme Mountain (6% sawtooth)
    """
    specs = VehicleSpecs()
    predictor = PhysicsBasedFuelPredictor(specs)

    speed_kmh = 80
    v_ms = speed_kmh / 3.6

    # 1. FLAT
    flat_segments = [(10000.0, v_ms, 0.0)]
    flat_pred = predictor.predict_granular(flat_segments, load_ton=20.0)

    # 2. REALISTIC HILLY (3%)
    hilly_segments = []
    for _ in range(5):
        hilly_segments.append((1000.0, v_ms, 30.0))
        hilly_segments.append((1000.0, v_ms, -30.0))
    hilly_pred = predictor.predict_granular(hilly_segments, load_ton=20.0)

    # 3. EXTREME PASS (6%)
    extreme_segments = []
    for _ in range(5):
        extreme_segments.append((1000.0, v_ms, 60.0))
        extreme_segments.append((1000.0, v_ms, -60.0))
    extreme_pred = predictor.predict_granular(extreme_segments, load_ton=20.0)

    print(f"\n[VERIFICATION] Flat: {flat_pred.consumption_l_100km} L/100km")
    print(
        f"[VERIFICATION] Realistic Hilly (3%): {hilly_pred.consumption_l_100km} L/100km"
    )
    print(
        f"[VERIFICATION] Extreme Mountain (6%): {extreme_pred.consumption_l_100km} L/100km (Capped)"
    )

    # Validations
    assert flat_pred.consumption_l_100km < 35.0
    assert hilly_pred.consumption_l_100km < 50.0  # Should be around 42-45
    assert extreme_pred.consumption_l_100km <= 65.0  # Max guardrail
    assert hilly_pred.consumption_l_100km > flat_pred.consumption_l_100km


def test_granular_vs_summary_equivalence():
    predictor = PhysicsBasedFuelPredictor()
    v_ms = 70 / 3.6
    single = [(5000.0, v_ms, 150.0)]
    multi = [(100.0, v_ms, 3.0)] * 50
    p1 = predictor.predict_granular(single, 15.0)
    p2 = predictor.predict_granular(multi, 15.0)
    assert abs(p1.consumption_l_100km - p2.consumption_l_100km) < 0.2


if __name__ == "__main__":
    test_terrain_variations()
    test_granular_vs_summary_equivalence()
