"""adjustment_factors — Phase 4.2 unit testler.

Her faktör için:
- Tipik (normal) senaryo
- Uç senaryo (clamp + edge case)
- None input → 1.0 (no-op)

Literatür uyum doğrulaması (P4.D5):
- Cold -10°C → %15-24 bant
- Headwind 10 km/h → ~%10
- Snowfall → minimum +%12
"""

from __future__ import annotations

import pytest

from app.core.ml.adjustment_factors import (
    combine_factors,
    weather_precipitation_factor,
    weather_temperature_factor,
    weather_wind_factor,
)

# ── temperature ───────────────────────────────────────────────────────


def test_temperature_normal_range_returns_1():
    # 5-28°C: optimal, 1.0
    assert weather_temperature_factor(15.0) == 1.0
    assert weather_temperature_factor(25.0) == 1.0
    assert weather_temperature_factor(5.0) == 1.0
    assert weather_temperature_factor(28.0) == 1.0


def test_temperature_cold_minus_10_matches_literature():
    """EPA cold -10°C → %15-24 bandı."""
    f = weather_temperature_factor(-10.0)
    assert f == pytest.approx(1.18, abs=0.01)  # 1.0 + 15 × 0.012
    assert 1.15 < f < 1.25


def test_temperature_hot_40_ac_load():
    """40°C → +%10 AC yükü."""
    f = weather_temperature_factor(40.0)
    assert f == pytest.approx(1.096, abs=0.01)  # 1.0 + 12 × 0.008
    assert 1.05 < f < 1.15


def test_temperature_clamp_upper():
    # -50°C ekstrem → clamp 1.20
    assert weather_temperature_factor(-50.0) == 1.20


def test_temperature_clamp_lower():
    # 50°C ekstrem → 1.0 + 22 × 0.008 = 1.176, clamp altında değil
    f = weather_temperature_factor(50.0)
    assert f == pytest.approx(1.176, abs=0.01)


def test_temperature_none_returns_1():
    assert weather_temperature_factor(None) == 1.0


# ── wind ──────────────────────────────────────────────────────────────


def test_wind_no_speed_returns_1():
    assert weather_wind_factor(None) == 1.0
    assert weather_wind_factor(0.0) == 1.0
    assert weather_wind_factor(-5.0) == 1.0


def test_wind_headwind_10kmh_matches_literature():
    """Headwind 10 km/h → ~%10 (drag ²× artış)."""
    # Sefer kuzey (0°), rüzgar güneyden geliyor (180°) → tam headwind
    f = weather_wind_factor(10.0, wind_bearing_deg=180.0, segment_bearing_deg=0.0)
    assert f == pytest.approx(1.10, abs=0.001)


def test_wind_tailwind_reduces_fuel():
    """Tailwind 20 km/h → -%4 yakıt (yardımcı rüzgar)."""
    # Sefer kuzey (0°), rüzgar da kuzeyden ileriye → tail (rüzgar arkadan)
    # wind_bearing = 0° (kuzeyden geliyor) ile segment 0° (kuzeye gidiyor)
    # → tailwind
    f = weather_wind_factor(20.0, wind_bearing_deg=0.0, segment_bearing_deg=0.0)
    assert f == pytest.approx(0.96, abs=0.001)


def test_wind_crosswind_minor():
    """Crosswind: az etki (+0.001 per km/h)."""
    # Sefer kuzey, rüzgar batıdan (90°) → crosswind
    f = weather_wind_factor(30.0, wind_bearing_deg=90.0, segment_bearing_deg=0.0)
    assert f == pytest.approx(1.03, abs=0.001)


def test_wind_no_direction_uses_midline_estimate():
    """Yön bilinmiyorsa orta katsayı."""
    f = weather_wind_factor(20.0)
    assert f == pytest.approx(1.10, abs=0.01)  # 1.0 + 20 × 0.005


def test_wind_clamp_storm():
    """Fırtına 50 km/h headwind → Faz 7 cap WEATHER_WIND_FACTOR_MAX (1.10)."""
    from app.config import settings

    f = weather_wind_factor(50.0, wind_bearing_deg=180.0, segment_bearing_deg=0.0)
    # 1.0 + 50 × 0.010 = 1.50 → clamp settings.WEATHER_WIND_FACTOR_MAX
    assert f == settings.WEATHER_WIND_FACTOR_MAX


def test_wind_tailwind_clamp_lower():
    """Çok güçlü tailwind 100 km/h → clamp 0.85."""
    f = weather_wind_factor(100.0, wind_bearing_deg=0.0, segment_bearing_deg=0.0)
    # 1.0 - 100 × 0.002 = 0.80 → clamp 0.85
    assert f == 0.85


def test_wind_direction_180_offset_is_headwind():
    """Wind 270° (batıdan), segment 90° (doğuya) → relative=180 → headwind.

    Cap altında kalması için düşük hız (8 km/h) seçilir; yön mantığı sınanır,
    Faz 7 cap (1.10) müdahale etmez.
    """
    f = weather_wind_factor(8.0, wind_bearing_deg=270.0, segment_bearing_deg=90.0)
    # 1.0 + 8 × 0.010 = 1.08 (headwind, cap 1.10 altında)
    assert f == pytest.approx(1.08, abs=0.001)


# ── precipitation ─────────────────────────────────────────────────────


def test_precip_dry_returns_1():
    assert weather_precipitation_factor(0.0) == 1.0
    assert weather_precipitation_factor(0.3) == 1.0  # < 0.5mm threshold
    assert weather_precipitation_factor(None) == 1.0


def test_precip_light_rain():
    assert weather_precipitation_factor(2.0) == 1.03


def test_precip_moderate_rain():
    assert weather_precipitation_factor(10.0) == 1.06


def test_precip_heavy_rain():
    assert weather_precipitation_factor(25.0) == 1.10


def test_precip_snow_minimum_12pct():
    """Kar varsa minimum %12 (slippery + dikkat sürüş)."""
    # Sadece kar, yağmur yok
    assert weather_precipitation_factor(0.0, snowfall_cm=5.0) == 1.12
    # Kar + şiddetli yağmur: 1.10 vs 1.12 → kar baskın
    assert weather_precipitation_factor(25.0, snowfall_cm=3.0) == 1.12


def test_precip_clamp_upper():
    # Ekstrem yağış (50mm/h hard-coded 1.10) clamp altında
    assert weather_precipitation_factor(50.0) == 1.10


# ── combine_factors ───────────────────────────────────────────────────


def test_combine_all_neutral_returns_1():
    assert combine_factors() == 1.0


def test_combine_multiplicative():
    """Her faktör doğru çarpılmalı."""
    f = combine_factors(
        driver=1.1,
        vehicle_age=1.05,
        maintenance=1.02,
        weather_temperature=1.0,
        weather_wind=1.05,
        weather_precipitation=1.03,
        seasonal=1.0,
    )
    # 1.1 × 1.05 × 1.02 × max(1.0, 1.0) × 1.05 × 1.03 = ~1.275
    assert f == pytest.approx(1.275, abs=0.01)


def test_combine_temp_overrides_seasonal_when_higher():
    """Gerçek sıcaklık (cold start +%18) seasonal (+%10) baskın olmalı."""
    f = combine_factors(weather_temperature=1.18, seasonal=1.10)
    assert f == pytest.approx(1.18, abs=0.001)


def test_combine_seasonal_used_when_temp_unavailable():
    """Hava verisi yoksa (temperature=1.0) seasonal fallback."""
    f = combine_factors(weather_temperature=1.0, seasonal=1.10)
    assert f == pytest.approx(1.10, abs=0.001)


def test_combine_clamp_upper():
    """Aşırı kombinasyon → clamp 1.5 (sıra dışı sonuç koruması)."""
    f = combine_factors(
        driver=1.2,
        vehicle_age=1.12,
        maintenance=1.25,
        weather_temperature=1.20,
        weather_wind=1.30,
        weather_precipitation=1.20,
        seasonal=1.10,
    )
    # Worst case: 1.2 × 1.12 × 1.25 × 1.20 × 1.30 × 1.20 = ~3.14 → 1.5
    assert f == 1.5


def test_combine_clamp_lower():
    """Çok düşük driver + tailwind → clamp 0.7."""
    f = combine_factors(
        driver=0.8,
        vehicle_age=1.0,
        maintenance=0.95,
        weather_temperature=1.0,
        weather_wind=0.85,
        weather_precipitation=1.0,
        seasonal=1.0,
    )
    # 0.8 × 1.0 × 0.95 × 1.0 × 0.85 = ~0.646 → clamp 0.7
    assert f == 0.7


# ── Literatür uyum sanity ─────────────────────────────────────────────


def test_realistic_winter_morning_scenario():
    """Kışsabah: -5°C, hafif yağış, headwind 15 km/h.

    Beklenen: ~%25-35 toplam ek tüketim.
    """
    temp = weather_temperature_factor(-5.0)  # 1.0 + 10×0.012 = 1.12
    wind = weather_wind_factor(15.0, 180.0, 0.0)  # 1.0 + 15×0.010 = 1.15
    rain = weather_precipitation_factor(3.0)  # 1.03
    seasonal = 1.10  # kış

    total = combine_factors(
        weather_temperature=temp,
        weather_wind=wind,
        weather_precipitation=rain,
        seasonal=seasonal,
    )
    # max(1.12, 1.10) × 1.15 × 1.03 = 1.327
    assert 1.25 < total < 1.40
