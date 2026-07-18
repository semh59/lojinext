"""Faz 7 — çevresel faktör fiziksel cap testleri."""

from datetime import date

import pytest

pytestmark = pytest.mark.unit


def test_wind_factor_capped_at_max(monkeypatch):
    from app.config import settings as s
    from v2.modules.prediction_ml.domain import adjustment_factors as af

    monkeypatch.setattr(s, "WEATHER_WIND_FACTOR_MAX", 1.10)
    # Güçlü headwind (relative 180°): cap olmadan 1.0 + 60×0.010 = 1.60 → 1.10'a clamp
    f = af.weather_wind_factor(
        wind_speed_kmh=60.0, wind_bearing_deg=180.0, segment_bearing_deg=0.0
    )
    assert f <= 1.10 + 1e-9


def test_wind_factor_below_cap_unchanged():
    from v2.modules.prediction_ml.domain import adjustment_factors as af

    # Rüzgârsız → 1.0; cap'in altında, alt clamp (0.85) üst clamp (1.10) arasında
    f = af.weather_wind_factor(
        wind_speed_kmh=0.0, wind_bearing_deg=0.0, segment_bearing_deg=0.0
    )
    assert 0.85 <= f <= 1.10


def test_seasonal_factor_capped(monkeypatch):
    from app.config import settings as s
    from app.core.services.weather_service import WeatherService

    monkeypatch.setattr(s, "SEASONAL_FACTOR_MAX", 1.03)
    ws = WeatherService()
    # Kış normalde 1.10 → cap 1.03
    assert ws.get_seasonal_factor(date(2026, 1, 15)) <= 1.03 + 1e-9
    # Yaz normalde 1.05 → cap 1.03
    assert ws.get_seasonal_factor(date(2026, 7, 15)) <= 1.03 + 1e-9
    # Düşük dönem (mayıs) 1.0 → değişmez
    assert ws.get_seasonal_factor(date(2026, 5, 15)) == 1.0
