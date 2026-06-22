"""
Unit tests for PhysicsBasedFuelPredictor, HybridFuelPredictor,
VehicleSpecs, RouteConditions, and FuelPrediction.

No external I/O — pure in-process physics calculations.
"""

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flat_route(distance_km=500.0, load_ton=20.0):
    from app.core.ml.physics_fuel_predictor import RouteConditions

    return RouteConditions(
        distance_km=distance_km,
        load_ton=load_ton,
        flat_distance_km=distance_km,
    )


def _mountain_route(distance_km=300.0, load_ton=25.0, ascent_m=2000, descent_m=1800):
    from app.core.ml.physics_fuel_predictor import RouteConditions

    return RouteConditions(
        distance_km=distance_km,
        load_ton=load_ton,
        ascent_m=ascent_m,
        descent_m=descent_m,
        flat_distance_km=0,
    )


# ---------------------------------------------------------------------------
# VehicleSpecs
# ---------------------------------------------------------------------------


class TestVehicleSpecs:
    def test_default_specs_are_valid(self):
        from app.core.ml.physics_fuel_predictor import VehicleSpecs

        specs = VehicleSpecs()
        assert specs.engine_efficiency > 0
        assert specs.fuel_density_kg_l > 0
        assert specs.empty_weight_kg > 0

    def test_invalid_engine_efficiency_raises(self):
        from app.core.ml.physics_fuel_predictor import VehicleSpecs

        with pytest.raises(ValueError, match="efficiency"):
            VehicleSpecs(engine_efficiency=0)

    def test_invalid_fuel_density_raises(self):
        from app.core.ml.physics_fuel_predictor import VehicleSpecs

        with pytest.raises(ValueError, match="density"):
            VehicleSpecs(fuel_density_kg_l=0)


# ---------------------------------------------------------------------------
# PhysicsBasedFuelPredictor — predict()
# ---------------------------------------------------------------------------


class TestPhysicsPredict:
    def test_flat_route_returns_positive_fuel(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        result = predictor.predict(_flat_route())
        assert result.total_liters > 0
        assert result.consumption_l_100km > 0

    def test_mountain_route_higher_than_flat(self):
        """Mountain route must consume more than a flat route of equal distance."""
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        flat = predictor.predict(_flat_route(distance_km=300, load_ton=20))
        mountain = predictor.predict(_mountain_route(distance_km=300, load_ton=20))
        assert mountain.consumption_l_100km > flat.consumption_l_100km

    def test_heavier_load_higher_consumption(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        light = predictor.predict(_flat_route(load_ton=5))
        heavy = predictor.predict(_flat_route(load_ton=25))
        assert heavy.consumption_l_100km > light.consumption_l_100km

    def test_empty_trip_lower_consumption(self):
        from app.core.ml.physics_fuel_predictor import (
            PhysicsBasedFuelPredictor,
            RouteConditions,
        )

        predictor = PhysicsBasedFuelPredictor()
        loaded = RouteConditions(distance_km=500, load_ton=20, flat_distance_km=500)
        empty = RouteConditions(
            distance_km=500, load_ton=20, is_empty_trip=True, flat_distance_km=500
        )
        assert (
            predictor.predict(empty).consumption_l_100km
            < predictor.predict(loaded).consumption_l_100km
        )

    def test_result_within_realistic_bounds(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        result = predictor.predict(_flat_route())
        assert (
            predictor.MIN_REALISTIC_L_100KM
            <= result.consumption_l_100km
            <= predictor.MAX_REALISTIC_L_100KM
        )

    def test_energy_breakdown_present(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        result = predictor.predict(_flat_route())
        assert "yuvarlanma" in result.energy_breakdown
        assert "hava_direnci" in result.energy_breakdown
        assert "tirmanis" in result.energy_breakdown

    def test_confidence_range_ordered(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        result = predictor.predict(_flat_route())
        low, high = result.confidence_range
        assert low < high
        assert low > 0

    def test_outlier_clamp_at_max_realistic(self):
        """An extremely steep short route should be clamped to MAX_REALISTIC."""
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        # 1 km, 25 ton, 5000 m ascent → enormous raw value
        # Use predict_granular directly so silent_outlier_log kwarg is accepted.
        segments = [(1000.0, 10.0 / 3.6, 5000.0)]  # 1 km, 10 km/h, +5000 m
        result = predictor.predict_granular(
            segments, load_ton=25.0, silent_outlier_log=True
        )
        assert result.consumption_l_100km <= predictor.MAX_REALISTIC_L_100KM


class TestPhysicsGravityRecovery:
    def test_young_vehicle_higher_recovery(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        young = PhysicsBasedFuelPredictor._get_gravity_recovery(2)
        old = PhysicsBasedFuelPredictor._get_gravity_recovery(12)
        assert young > old

    def test_recovery_brackets(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        assert PhysicsBasedFuelPredictor._get_gravity_recovery(1) == 0.90
        assert PhysicsBasedFuelPredictor._get_gravity_recovery(5) == 0.80
        assert PhysicsBasedFuelPredictor._get_gravity_recovery(8) == 0.68
        assert PhysicsBasedFuelPredictor._get_gravity_recovery(15) == 0.60


class TestPhysicsCalibrate:
    def test_calibrate_insufficient_data(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        result = predictor.calibrate_with_historical([30.0] * 3, [31.0] * 3)
        assert "error" in result

    def test_calibrate_with_valid_data(self):
        from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

        predictor = PhysicsBasedFuelPredictor()
        preds = [30.0] * 10
        actuals = [33.0] * 10
        result = predictor.calibrate_with_historical(preds, actuals)
        assert "calibration_factor" in result
        assert result["calibration_factor"] > 1.0  # underpredicted
        assert result["sample_count"] == 10


# ---------------------------------------------------------------------------
# HybridFuelPredictor
# ---------------------------------------------------------------------------


class TestHybridFuelPredictor:
    def test_predict_returns_fuel_prediction(self):
        from app.core.ml.physics_fuel_predictor import (
            FuelPrediction,
            HybridFuelPredictor,
        )

        hybrid = HybridFuelPredictor()
        result = hybrid.predict(_flat_route())
        assert isinstance(result, FuelPrediction)
        assert result.total_liters > 0

    def test_learn_from_actual_updates_correction(self):
        from app.core.ml.physics_fuel_predictor import HybridFuelPredictor

        hybrid = HybridFuelPredictor()
        for _ in range(5):
            hybrid.learn_from_actual(100.0, 110.0)  # 10 % over-prediction
        # correction_factor should shift toward 1.10
        assert hybrid.correction_factor > 1.0

    def test_outlier_ignored_by_learn(self):
        """Ratios outside (0.5, 1.5) must be ignored."""
        from app.core.ml.physics_fuel_predictor import HybridFuelPredictor

        hybrid = HybridFuelPredictor()
        initial_factor = hybrid.correction_factor
        hybrid.learn_from_actual(100.0, 300.0)  # ratio = 3 → ignored
        assert hybrid.correction_factor == initial_factor

    def test_correction_factor_applied_to_prediction(self):
        from app.core.ml.physics_fuel_predictor import HybridFuelPredictor

        hybrid = HybridFuelPredictor()
        base_result = hybrid.predict(_flat_route(load_ton=20))

        # Artificially set correction factor
        hybrid.correction_factor = 1.2
        corrected_result = hybrid.predict(_flat_route(load_ton=20))

        assert (
            abs(corrected_result.total_liters / base_result.total_liters - 1.2) < 0.05
        )
