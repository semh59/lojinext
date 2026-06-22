"""p51 koşul-nötr hesap helper testi."""

from types import SimpleNamespace

import pytest

from scripts.p51_real_world_validation import neutral_estimate

pytestmark = pytest.mark.unit


def test_neutral_estimate_strips_environmental_factors():
    # physics 34.0; driver/age/maint=1.0; çevresel (wind 1.13, seasonal 1.05) atılır → 34.0
    bd = SimpleNamespace(
        physics_baseline=34.0,
        driver=1.0,
        vehicle_age=1.0,
        maintenance=1.0,
        weather_temperature=1.0,
        weather_wind=1.13,
        weather_precipitation=1.0,
        seasonal=1.05,
    )
    assert abs(neutral_estimate(bd) - 34.0) < 1e-6


def test_neutral_estimate_keeps_vehicle_factors():
    bd = SimpleNamespace(
        physics_baseline=30.0,
        driver=1.0,
        vehicle_age=1.05,
        maintenance=1.0,
        weather_temperature=1.0,
        weather_wind=1.2,
        weather_precipitation=1.0,
        seasonal=1.1,
    )
    # vehicle_age 1.05 korunur, çevresel atılır → 30 × 1.05 = 31.5
    assert abs(neutral_estimate(bd) - 31.5) < 1e-6
