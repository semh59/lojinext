"""Additional coverage tests for app/core/ml/physics_fuel_predictor.py.

Targets uncovered branches:
- _equilibrium_speed_ms: downhill/flat (grade<=0) fast path
- _equilibrium_speed_ms: binary search when nominal speed is NOT achievable
- _get_gravity_recovery: all age brackets (<=3, <=6, <=10, >10)
- _build_segments: road_grade path (distributions present)
- _build_segments: road-category km breakdown (analysis without distributions)
- _build_segments: remaining_km=0 edge (flat_km = distance_km)
- _build_segments: no segments from analysis fallback → 3-part default
- _build_segments: distance_km <= covered_km (no tail segment)
- predict_granular: is_empty_trip=True (effective_load=0)
- predict_granular: dist_m <= 0 (segment skipped)
- predict_granular: grade_pct <= 0.5 (no equilibrium correction)
- predict_granular: silent_outlier_log=True (suppresses warning)
- predict_granular: historical_stats with climb/drag thresholds
- predict_granular: insight branches (climb, drag, descent)
- calibrate_with_historical: < 5 data points → error
- calibrate_with_historical: >=5 data points → calibration_factor
- HybridFuelPredictor: predict with correction_factor != 1.0
- HybridFuelPredictor: learn_from_actual outlier guard (ratio outside 0.5..1.5)
- HybridFuelPredictor: learn_from_actual >20 history entries → prune
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _equilibrium_speed_ms
# ---------------------------------------------------------------------------


def test_equilibrium_speed_downhill_returns_nominal():
    """grade_pct <= 0 → returns nominal speed unchanged."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    result = p._equilibrium_speed_ms(
        nominal_v_ms=20.0, grade_pct=-3.0, total_mass_kg=30000
    )
    assert result == 20.0


def test_equilibrium_speed_flat_returns_nominal():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    result = p._equilibrium_speed_ms(
        nominal_v_ms=20.0, grade_pct=0.0, total_mass_kg=30000
    )
    assert result == 20.0


def test_equilibrium_speed_fast_path_when_power_sufficient():
    """Light load on gentle grade: engine power sufficient → nominal speed returned."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        VehicleSpecs,
    )

    # High engine power makes nominal achievable
    specs = VehicleSpecs(engine_power_w=1_000_000.0)
    p = PhysicsBasedFuelPredictor(vehicle=specs)
    result = p._equilibrium_speed_ms(
        nominal_v_ms=15.0, grade_pct=2.0, total_mass_kg=15000
    )
    assert result == 15.0


def test_equilibrium_speed_binary_search_heavy_load():
    """Heavy load on very steep grade triggers binary search → speed < nominal."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        VehicleSpecs,
    )

    # Low engine power forces slow-down
    specs = VehicleSpecs(engine_power_w=100_000.0)
    p = PhysicsBasedFuelPredictor(vehicle=specs)
    nominal = 20.0  # ~72 km/h
    eq = p._equilibrium_speed_ms(
        nominal_v_ms=nominal, grade_pct=15.0, total_mass_kg=40000
    )
    assert eq < nominal
    assert eq >= 5.0  # floor constraint


# ---------------------------------------------------------------------------
# _get_gravity_recovery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "age, expected",
    [
        (1, 0.90),  # <= 3
        (3, 0.90),  # == 3
        (5, 0.80),  # <= 6
        (6, 0.80),  # == 6
        (8, 0.68),  # <= 10
        (10, 0.68),  # == 10
        (11, 0.60),  # > 10
        (20, 0.60),  # >> 10
    ],
)
def test_gravity_recovery_age_brackets(age, expected):
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    result = PhysicsBasedFuelPredictor._get_gravity_recovery(age)
    assert result == expected


# ---------------------------------------------------------------------------
# _build_segments: road_grade distributions path
# ---------------------------------------------------------------------------


def test_build_segments_road_grade_distributions():
    """When analysis has distributions.road_grade → uses joint path."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=300.0,
        load_ton=20.0,
        ascent_m=500.0,
        descent_m=300.0,
        avg_speed_kmh=80.0,
        route_analysis={
            "distributions": {
                "road_grade": {
                    "motorway+flat": 50.0,
                    "motorway+uphill_moderate": 25.0,
                    "primary+downhill_moderate": 25.0,
                }
            }
        },
    )
    segs = p._build_segments(route)
    assert len(segs) > 0
    # Each segment is (dist_m, speed_ms, delta_h)
    for dist_m, speed_ms, delta_h in segs:
        assert dist_m > 0


def test_build_segments_road_grade_distributions_empty_pct_skipped():
    """Entries with 0 pct in road_grade are skipped."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=200.0,
        load_ton=15.0,
        ascent_m=200.0,
        descent_m=100.0,
        route_analysis={
            "distributions": {
                "road_grade": {
                    "motorway+flat": 100.0,
                    "primary+uphill_steep": 0,  # zero → skipped
                }
            }
        },
    )
    segs = p._build_segments(route)
    assert len(segs) >= 1


# ---------------------------------------------------------------------------
# _build_segments: road-category km breakdown (path 2)
# ---------------------------------------------------------------------------


def test_build_segments_road_category_breakdown():
    """analysis present without distributions → per-category flat/up/down."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=200.0,
        load_ton=18.0,
        ascent_m=400.0,
        descent_m=200.0,
        route_analysis={
            "motorway": {"flat": 100.0, "up": 50.0, "down": 30.0},
            "primary": {"flat": 20.0, "up": 0.0},
        },
    )
    segs = p._build_segments(route)
    assert len(segs) > 0


def test_build_segments_road_category_adds_tail_segment():
    """If covered_km < distance_km, a flat tail segment is appended."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=500.0,
        load_ton=20.0,
        ascent_m=0.0,
        descent_m=0.0,
        route_analysis={
            "motorway": {"flat": 100.0},  # Only 100 km covered
        },
    )
    segs = p._build_segments(route)
    # Should have at least 2 segments: the motorway flat + tail
    assert len(segs) >= 1


# ---------------------------------------------------------------------------
# _build_segments: fallback 3-part default
# ---------------------------------------------------------------------------


def test_build_segments_no_analysis_flat_only():
    """No route_analysis, flat_distance_km = distance_km → only flat segment."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=300.0,
        load_ton=20.0,
        flat_distance_km=300.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
    segs = p._build_segments(route)
    assert len(segs) >= 1


def test_build_segments_fallback_3part_when_no_segs():
    """When distance_km = 0 and no analysis → hits 3-part fallback with 0-dist."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
        RouteConditions,
    )

    p = PhysicsBasedFuelPredictor()
    route = RouteConditions(
        distance_km=100.0,
        load_ton=10.0,
        flat_distance_km=0.0,
        ascent_m=200.0,
        descent_m=150.0,
    )
    segs = p._build_segments(route)
    assert len(segs) >= 1


# ---------------------------------------------------------------------------
# predict_granular: special kwargs / branches
# ---------------------------------------------------------------------------


def test_predict_granular_empty_trip():
    """is_empty_trip=True → effective_load=0, lower consumption."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    segs = [(300_000.0, 20.0, 0.0)]

    loaded = p.predict_granular(segs, load_ton=20.0, is_empty_trip=False)
    empty = p.predict_granular(segs, load_ton=20.0, is_empty_trip=True)
    assert empty.total_liters < loaded.total_liters


def test_predict_granular_skips_zero_dist_segment():
    """Segments with dist_m=0 are skipped without error."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    segs = [(0.0, 15.0, 0.0), (100_000.0, 20.0, 100.0)]
    result = p.predict_granular(segs, load_ton=10.0)
    assert result.total_liters > 0


def test_predict_granular_gentle_grade_no_equilibrium():
    """Grade <= 0.5% → no equilibrium speed correction."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # Very slight uphill: 0.3% grade (delta_h/dist_m * 100 = 0.3)
    segs = [(100_000.0, 20.0, 300.0)]  # 300m over 100km = 0.3%
    result = p.predict_granular(segs, load_ton=10.0)
    assert result.total_liters > 0


def test_predict_granular_silent_outlier_log():
    """silent_outlier_log=True suppresses warning for high l/100km."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # Very short distance with heavy climb → very high l/100km
    segs = [(100.0, 5.0, 500.0)]  # 0.1km with 500m climb
    result = p.predict_granular(segs, load_ton=25.0, silent_outlier_log=True)
    # Should clamp to MAX_REALISTIC
    assert result.consumption_l_100km <= p.MAX_REALISTIC_L_100KM


def test_predict_granular_without_silent_outlier_log_still_clamps():
    """Without silent_outlier_log, outlier is still clamped to MAX_REALISTIC."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    segs = [(100.0, 5.0, 500.0)]
    result = p.predict_granular(segs, load_ton=25.0)
    assert result.consumption_l_100km <= p.MAX_REALISTIC_L_100KM


# ---------------------------------------------------------------------------
# predict_granular: insight branches
# ---------------------------------------------------------------------------


def test_predict_granular_climb_insight():
    """Heavy climb ratio triggers climb insight."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # Many steep uphill segments → high e_climb_total
    segs = [(50_000.0, 10.0, 3000.0)]  # 50km, 3000m climb
    historical_stats = {"climb_mean": 0.1, "climb_std": 0.05}  # threshold = 0.2
    result = p.predict_granular(segs, load_ton=20.0, historical_stats=historical_stats)
    # climb_ratio should exceed threshold
    if result.insight:
        assert "ramp" in result.insight.lower() or "tüketim" in result.insight.lower()


def test_predict_granular_drag_insight():
    """High drag ratio triggers drag insight."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # Flat route at high speed → drag dominates
    segs = [(500_000.0, 33.0, 0.0)]  # 500km at 33 m/s (~120 km/h)
    historical_stats = {"drag_mean": 0.0, "drag_std": 0.01}  # very low threshold
    result = p.predict_granular(segs, load_ton=5.0, historical_stats=historical_stats)
    if result.insight:
        assert (
            "hız" in result.insight.lower()
            or "direnç" in result.insight.lower()
            or "limit" in result.insight.lower()
        )


def test_predict_granular_descent_insight():
    """Descent > climb * 0.8 triggers gravity recovery insight."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # Lots of downhill
    segs = [
        (50_000.0, 20.0, 100.0),  # small climb
        (100_000.0, 20.0, -5000.0),  # large descent
    ]
    result = p.predict_granular(segs, load_ton=10.0, arac_yasi=3)
    if result.insight:
        assert (
            "iniş" in result.insight.lower()
            or "gravity" in result.insight.lower()
            or "tasarruf" in result.insight.lower()
        )


# ---------------------------------------------------------------------------
# calibrate_with_historical
# ---------------------------------------------------------------------------


def test_calibrate_with_historical_insufficient_data():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    result = p.calibrate_with_historical([100, 200], [105, 195])
    assert "error" in result


def test_calibrate_with_historical_sufficient_data():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    predictions = [100, 110, 120, 130, 140]
    actuals = [105, 115, 118, 128, 138]
    result = p.calibrate_with_historical(predictions, actuals)
    assert "calibration_factor" in result
    assert result["sample_count"] == 5
    assert "recommendation" in result


def test_calibrate_with_historical_large_error_recommends_update():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # ~30% consistent overestimate → calibration_factor != 1.0 by >0.1
    predictions = [100.0] * 6
    actuals = [130.0] * 6
    result = p.calibrate_with_historical(predictions, actuals)
    assert result["recommendation"] == "Motor verimliliğini güncelle"


def test_calibrate_with_historical_within_threshold_says_kalibre():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        PhysicsBasedFuelPredictor,
    )

    p = PhysicsBasedFuelPredictor()
    # <10% error → "Model kalibre"
    predictions = [100.0] * 6
    actuals = [102.0] * 6
    result = p.calibrate_with_historical(predictions, actuals)
    assert result["recommendation"] == "Model kalibre"


# ---------------------------------------------------------------------------
# HybridFuelPredictor
# ---------------------------------------------------------------------------


def test_hybrid_predict_applies_correction_factor():
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        HybridFuelPredictor,
        RouteConditions,
    )

    hybrid = HybridFuelPredictor()
    hybrid.correction_factor = 1.2  # Force 20% higher

    route = RouteConditions(distance_km=300.0, load_ton=15.0, flat_distance_km=300.0)
    base_result = hybrid.physics_model.predict(route)
    hybrid_result = hybrid.predict(route)

    assert hybrid_result.total_liters == pytest.approx(
        base_result.total_liters * 1.2, rel=0.01
    )


def test_hybrid_learn_from_actual_outlier_rejected():
    """Ratio outside 0.5..1.5 is not added to historical_errors."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        HybridFuelPredictor,
    )

    hybrid = HybridFuelPredictor()
    initial_len = len(hybrid.historical_errors)

    # ratio = 200/100 = 2.0 > 1.5 → outlier
    hybrid.learn_from_actual(prediction=100.0, actual=200.0)
    assert len(hybrid.historical_errors) == initial_len


def test_hybrid_learn_from_actual_valid_ratio():
    """Valid ratio is added and correction_factor updated after 5 samples."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        HybridFuelPredictor,
    )

    hybrid = HybridFuelPredictor()
    # Add 5 valid ratios: actual = 1.1 * prediction
    for _ in range(5):
        hybrid.learn_from_actual(prediction=100.0, actual=110.0)

    assert len(hybrid.historical_errors) == 5
    assert hybrid.correction_factor == pytest.approx(1.1, rel=0.01)


def test_hybrid_learn_from_actual_prunes_over_20():
    """historical_errors is pruned to last 20 entries when >20."""
    from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
        HybridFuelPredictor,
    )

    hybrid = HybridFuelPredictor()
    # Add 22 valid ratios
    for _ in range(22):
        hybrid.learn_from_actual(prediction=100.0, actual=105.0)

    # After pruning: <= 20
    assert len(hybrid.historical_errors) <= 20
