"""
Coverage tests for v2/modules/route_simulation/application/weather_service.py
Targets: calculate_weather_fuel_impact branches, get_seasonal_factor,
get_route_weather_samples paths, get_trip_impact_analysis success,
condition warnings, recommendation strings.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service():
    from v2.modules.route_simulation.application.weather_service import WeatherService

    ext = MagicMock()
    ext.get_weather_forecast = AsyncMock(
        return_value={
            "daily": {
                "time": ["2024-06-01"],
                "temperature_2m_max": [20.0],
                "precipitation_sum": [0.0],
                "wind_speed_10m_max": [10.0],
            }
        }
    )
    ext.get_weather_current_batch = AsyncMock(return_value={"data": []})
    return WeatherService(external_service=ext)


# ---------------------------------------------------------------------------
# calculate_weather_fuel_impact — temperature branches
# ---------------------------------------------------------------------------


class TestWeatherFuelImpact:
    def test_temp_below_zero(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(-5.0, 0.0, 0.0)
        assert impact >= 1.08

    def test_temp_0_to_10(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(5.0, 0.0, 0.0)
        assert impact == pytest.approx(1.04)

    def test_temp_30_to_threshold(self):
        svc = _make_service()
        # 30 < temp <= WEATHER_TEMP_HIGH_THRESHOLD
        from app.config import settings

        threshold = settings.WEATHER_TEMP_HIGH_THRESHOLD
        temp = (30 + threshold) / 2  # between 30 and threshold
        impact = svc.calculate_weather_fuel_impact(temp, 0.0, 0.0)
        assert impact == pytest.approx(1.03)

    def test_temp_above_high_threshold(self):
        svc = _make_service()
        from app.config import settings

        temp = settings.WEATHER_TEMP_HIGH_THRESHOLD + 5
        impact = svc.calculate_weather_fuel_impact(temp, 0.0, 0.0)
        assert impact == pytest.approx(1.05)

    def test_temp_normal_no_impact(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, 0.0)
        assert impact == pytest.approx(1.0)

    # Precipitation branches
    def test_precip_above_20(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 25.0, 0.0)
        assert impact == pytest.approx(1.08)

    def test_precip_10_to_20(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 15.0, 0.0)
        assert impact == pytest.approx(1.05)

    def test_precip_2_to_10(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 5.0, 0.0)
        assert impact == pytest.approx(1.02)

    def test_precip_low_no_impact(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 1.0, 0.0)
        assert impact == pytest.approx(1.0)

    # Wind branches
    def test_wind_above_high_threshold(self):
        svc = _make_service()
        from app.config import settings

        wind = settings.WEATHER_WIND_HIGH_THRESHOLD + 10
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, wind)
        assert impact == pytest.approx(1.15)

    def test_wind_40_to_threshold(self):
        svc = _make_service()
        from app.config import settings

        threshold = settings.WEATHER_WIND_HIGH_THRESHOLD
        wind = (40 + threshold) / 2  # between 40 and threshold
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, wind)
        assert impact == pytest.approx(1.10)

    def test_wind_25_to_40(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, 30.0)
        assert impact == pytest.approx(1.05)

    def test_wind_15_to_25(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, 20.0)
        assert impact == pytest.approx(1.02)

    def test_wind_low_no_impact(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(15.0, 0.0, 5.0)
        assert impact == pytest.approx(1.0)

    def test_combined_bad_conditions(self):
        svc = _make_service()
        impact = svc.calculate_weather_fuel_impact(-10.0, 25.0, 80.0)
        # -10 → +0.08, precip 25 → +0.08, wind 80 → +0.15
        assert impact == pytest.approx(1.31)


# ---------------------------------------------------------------------------
# generate_weather_recommendation
# ---------------------------------------------------------------------------


class TestWeatherRecommendation:
    def test_low_impact_normal_plan(self):
        svc = _make_service()
        from app.config import settings

        result = svc.generate_weather_recommendation(
            settings.WEATHER_IMPACT_MEDIUM - 0.01
        )
        assert "normal" in result.lower() or "standart" in result.lower()

    def test_medium_impact_flexibility(self):
        svc = _make_service()
        from app.config import settings

        # between MEDIUM and HIGH
        val = (settings.WEATHER_IMPACT_MEDIUM + settings.WEATHER_IMPACT_HIGH) / 2
        result = svc.generate_weather_recommendation(val)
        assert "orta" in result.lower() or "esneklik" in result.lower()

    def test_high_impact_expand_plan(self):
        svc = _make_service()
        from app.config import settings

        result = svc.generate_weather_recommendation(settings.WEATHER_IMPACT_HIGH + 0.1)
        assert "olumsuz" in result.lower() or "genişletin" in result.lower()


# ---------------------------------------------------------------------------
# _get_condition_warnings
# ---------------------------------------------------------------------------


class TestConditionWarnings:
    def test_cold_warning(self):
        svc = _make_service()
        warnings = svc._get_condition_warnings(2.0, 0.0, 0.0)
        assert any("soğuk" in w.lower() for w in warnings)

    def test_precipitation_warning(self):
        svc = _make_service()
        warnings = svc._get_condition_warnings(15.0, 10.0, 0.0)
        assert any("yağış" in w.lower() for w in warnings)

    def test_wind_warning(self):
        svc = _make_service()
        warnings = svc._get_condition_warnings(15.0, 0.0, 40.0)
        assert any("rüzgar" in w.lower() for w in warnings)

    def test_no_warnings_normal_conditions(self):
        svc = _make_service()
        warnings = svc._get_condition_warnings(15.0, 1.0, 10.0)
        assert warnings == []


# ---------------------------------------------------------------------------
# get_seasonal_factor
# ---------------------------------------------------------------------------


class TestSeasonalFactor:
    # Faz 7 — get_seasonal_factor çıktısı settings.SEASONAL_FACTOR_MAX ile
    # cap'lenir. Ham mevsim değerleri (kış 1.10, yaz 1.05) cap altında kalır.
    def test_winter_months(self):
        from app.config import settings

        svc = _make_service()
        expected = min(1.10, settings.SEASONAL_FACTOR_MAX)
        for m in [12, 1, 2]:
            d = date(2024, m, 15)
            assert svc.get_seasonal_factor(d) == pytest.approx(expected)

    def test_spring_autumn_months(self):
        from app.config import settings

        svc = _make_service()
        expected = min(1.03, settings.SEASONAL_FACTOR_MAX)
        for m in [3, 4, 10, 11]:
            d = date(2024, m, 15)
            assert svc.get_seasonal_factor(d) == pytest.approx(expected)

    def test_summer_months(self):
        from app.config import settings

        svc = _make_service()
        expected = min(1.05, settings.SEASONAL_FACTOR_MAX)
        for m in [6, 7, 8]:
            d = date(2024, m, 15)
            assert svc.get_seasonal_factor(d) == pytest.approx(expected)

    def test_neutral_months(self):
        svc = _make_service()
        for m in [5, 9]:
            d = date(2024, m, 15)
            assert svc.get_seasonal_factor(d) == pytest.approx(1.0)

    def test_string_date_iso(self):
        from app.config import settings

        svc = _make_service()
        expected = min(1.05, settings.SEASONAL_FACTOR_MAX)
        assert svc.get_seasonal_factor("2024-07-15") == pytest.approx(expected)

    def test_invalid_string_falls_back_to_today(self):
        svc = _make_service()
        # Should not raise
        result = svc.get_seasonal_factor("not-a-date")
        assert isinstance(result, float)

    def test_datetime_object(self):
        from app.config import settings

        svc = _make_service()
        dt = datetime(2024, 1, 15)
        expected = min(1.10, settings.SEASONAL_FACTOR_MAX)
        assert svc.get_seasonal_factor(dt) == pytest.approx(expected)

    def test_invalid_type_falls_back(self):
        svc = _make_service()
        result = svc.get_seasonal_factor(12345)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# get_forecast_analysis_offline
# ---------------------------------------------------------------------------


class TestForecastAnalysisOffline:
    def test_offline_returns_unavailable_structure(self):
        svc = _make_service()
        result = svc.get_forecast_analysis_offline()
        assert result["success"] is False
        assert result["offline"] is True
        assert result["daily"] == []
        assert result["fuel_impact_factor"] is None

    def test_offline_with_error_dict(self):
        svc = _make_service()
        err = {"error": "network failure", "error_code": "TIMEOUT"}
        result = svc.get_forecast_analysis_offline(error=err)
        assert result["error"] == "network failure"
        assert result["error_code"] == "TIMEOUT"

    def test_offline_without_error_dict_uses_defaults(self):
        svc = _make_service()
        result = svc.get_forecast_analysis_offline(error=None)
        assert "unavailable" in result["error"].lower()
        assert result["error_code"] == "SERVICE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# get_forecast_analysis — success path
# ---------------------------------------------------------------------------


class TestGetForecastAnalysis:
    async def test_success_builds_7_day_forecast(self):
        svc = _make_service()
        dates = [f"2024-06-{i:02d}" for i in range(1, 8)]
        svc.external_service.get_weather_forecast = AsyncMock(
            return_value={
                "daily": {
                    "time": dates,
                    "temperature_2m_max": [20.0] * 7,
                    "precipitation_sum": [0.0] * 7,
                    "wind_speed_10m_max": [10.0] * 7,
                }
            }
        )
        result = await svc.get_forecast_analysis(41.0, 29.0)
        assert result["success"] is True
        assert len(result["daily"]) == 7
        assert result["offline"] is False
        assert "fuel_impact_factor" in result

    async def test_partial_data_uses_defaults(self):
        """Fewer temps/precips than dates → defaults 15°C / 0mm / 10 km/h."""
        svc = _make_service()
        svc.external_service.get_weather_forecast = AsyncMock(
            return_value={
                "daily": {
                    "time": ["2024-06-01", "2024-06-02"],
                    "temperature_2m_max": [20.0],  # only 1, second uses default
                    "precipitation_sum": [],
                    "wind_speed_10m_max": [],
                }
            }
        )
        result = await svc.get_forecast_analysis(41.0, 29.0)
        assert result["success"] is True
        assert len(result["daily"]) == 2


# ---------------------------------------------------------------------------
# get_trip_impact_analysis — success path
# ---------------------------------------------------------------------------


class TestTripImpactAnalysis:
    async def test_success_returns_impact_factor(self):
        svc = _make_service()
        good_weather = {
            "daily": {
                "temperature_2m_max": [20.0],
                "precipitation_sum": [0.0],
                "wind_speed_10m_max": [10.0],
            }
        }
        svc.external_service.get_weather_forecast = AsyncMock(return_value=good_weather)
        result = await svc.get_trip_impact_analysis(41.0, 29.0, 40.0, 32.0)
        assert result["success"] is True
        assert "fuel_impact_factor" in result
        assert "conditions" in result
        assert "weather_summary" in result

    async def test_error_in_start_returns_failure(self):
        svc = _make_service()
        error_weather = {"error": "API down", "error_code": "DOWN"}
        svc.external_service.get_weather_forecast = AsyncMock(
            return_value=error_weather
        )
        result = await svc.get_trip_impact_analysis(41.0, 29.0, 40.0, 32.0)
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# get_route_weather_samples
# ---------------------------------------------------------------------------


class TestRouteWeatherSamples:
    async def test_empty_midpoints_returns_empty(self):
        svc = _make_service()
        result = await svc.get_route_weather_samples([])
        assert result == []

    async def test_cache_hit_returns_cached_samples(self):
        svc = _make_service()
        from v2.modules.route_simulation.application.weather_service import (
            WeatherSample,
        )

        cached_sample = WeatherSample(temperature_2m=15.0, wind_speed_10m=10.0)
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=cached_sample)
        mock_cache.set = MagicMock()

        with patch(
            "v2.modules.platform_infra.public.get_cache_manager",
            return_value=mock_cache,
        ):
            result = await svc.get_route_weather_samples([(29.0, 41.0)])

        assert result[0] is cached_sample

    async def test_cache_miss_fetches_batch(self):
        svc = _make_service()
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)
        mock_cache.set = MagicMock()

        svc.external_service.get_weather_current_batch = AsyncMock(
            return_value={
                "data": [
                    {
                        "current": {
                            "temperature_2m": 22.0,
                            "wind_speed_10m": 15.0,
                            "wind_direction_10m": 90.0,
                            "precipitation": 0.0,
                            "snowfall": 0.0,
                        }
                    }
                ]
            }
        )

        with patch(
            "v2.modules.platform_infra.public.get_cache_manager",
            return_value=mock_cache,
        ):
            result = await svc.get_route_weather_samples([(29.0, 41.0)])

        assert result[0] is not None
        assert result[0].temperature_2m == 22.0

    async def test_batch_error_returns_nones(self):
        svc = _make_service()
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)
        mock_cache.set = MagicMock()

        svc.external_service.get_weather_current_batch = AsyncMock(
            return_value={"error": "provider down"}
        )

        with patch(
            "v2.modules.platform_infra.public.get_cache_manager",
            return_value=mock_cache,
        ):
            result = await svc.get_route_weather_samples([(29.0, 41.0), (30.0, 42.0)])

        assert result == [None, None]

    async def test_cache_get_exception_treated_as_miss(self):
        svc = _make_service()
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(side_effect=Exception("redis down"))
        mock_cache.set = MagicMock()

        svc.external_service.get_weather_current_batch = AsyncMock(
            return_value={"error": "offline"}
        )

        with patch(
            "v2.modules.platform_infra.public.get_cache_manager",
            return_value=mock_cache,
        ):
            result = await svc.get_route_weather_samples([(29.0, 41.0)])

        assert result == [None]

    async def test_deduplication_single_api_call_for_same_coords(self):
        svc = _make_service()
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)
        mock_cache.set = MagicMock()

        svc.external_service.get_weather_current_batch = AsyncMock(
            return_value={
                "data": [
                    {
                        "current": {
                            "temperature_2m": 18.0,
                            "wind_speed_10m": 8.0,
                            "wind_direction_10m": 180.0,
                            "precipitation": 0.0,
                            "snowfall": 0.0,
                        }
                    }
                ]
            }
        )

        # Same coord repeated
        with patch(
            "v2.modules.platform_infra.public.get_cache_manager",
            return_value=mock_cache,
        ):
            await svc.get_route_weather_samples([(29.0, 41.0), (29.0, 41.0)])

        # Batch should only be called with 1 unique coord
        call_args = svc.external_service.get_weather_current_batch.call_args[0][0]
        assert len(call_args) == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_weather_service_singleton():
    from v2.modules.route_simulation.application.weather_service import (
        get_weather_service,
    )

    s1 = get_weather_service()
    s2 = get_weather_service()
    assert s1 is s2
