"""SeferFuelEstimator unit tests — all external calls mocked."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_sim_result(avg_l=32.0, total_km=450.0, eta_sec=18000):
    """Build a minimal SimulationResult-like object."""
    summary = MagicMock()
    summary.avg_l_per_100km = avg_l
    summary.total_km = total_km
    summary.total_eta_sec = eta_sec
    summary.total_ascent_m = 120.0
    summary.total_descent_m = 100.0
    summary.segments = []

    result = MagicMock()
    result.summary = summary
    result.boundary_coords = [(32.0, 39.9), (35.0, 41.0)]
    result.elevation_coverage_pct = 0.8
    result.raw_segment_count = 200
    result.resampled_segment_count = 180
    return result


class TestSeferFuelEstimator:
    def test_service_exists(self):
        """SeferFuelEstimator and dataclasses are importable."""
        from app.core.services.sefer_fuel_estimator import (
            FactorBreakdown,
            SeferFuelEstimate,
            SeferFuelEstimator,
            SeferFuelInput,
        )

        assert SeferFuelEstimator is not None
        assert SeferFuelInput is not None
        assert SeferFuelEstimate is not None
        assert FactorBreakdown is not None

    async def test_basic_initialization(self):
        """SeferFuelEstimator initializes with injected simulator and weather."""
        from app.core.services.sefer_fuel_estimator import SeferFuelEstimator

        mock_sim = MagicMock()
        mock_weather = MagicMock()

        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)
        assert estimator._simulator is mock_sim
        assert estimator._weather is mock_weather

    async def test_default_physics_weight_is_one(self):
        """Cold-start DEFAULT_PHYSICS_WEIGHT should be 1.0 (ensemble bypass)."""
        from app.core.services.sefer_fuel_estimator import SeferFuelEstimator

        assert SeferFuelEstimator.DEFAULT_PHYSICS_WEIGHT == 1.0

    async def test_happy_path_returns_estimate(self):
        """predict() returns SeferFuelEstimate when all mocks succeed."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimate,
            SeferFuelEstimator,
            SeferFuelInput,
        )

        mock_sim = MagicMock()
        mock_sim.simulate = AsyncMock(return_value=_make_sim_result())
        mock_weather = MagicMock()
        mock_weather.get_route_weather_samples = AsyncMock(return_value=[])
        mock_weather.get_seasonal_factor = MagicMock(return_value=1.0)

        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        fake_arac = MagicMock()
        fake_arac.uretim_tarihi = date(2019, 1, 1)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            side_effect=lambda model, id_: fake_arac if id_ else None
        )

        inp = SeferFuelInput(
            arac_id=1,
            target_date=date(2024, 6, 1),
            ton=22.0,
            cikis_lat=39.9,
            cikis_lon=32.0,
            varis_lat=41.0,
            varis_lon=35.0,
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            with patch.object(estimator, "_persist", new=AsyncMock(return_value=99)):
                result = await estimator.predict(inp, persist=True)

        assert result is not None
        assert isinstance(result, SeferFuelEstimate)
        assert result.distance_km == 450.0
        assert result.simulation_id == 99
        assert result.tahmini_tuketim > 0

    async def test_predict_returns_none_when_arac_missing(self):
        """predict() returns None when arac lookup returns None."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimator,
            SeferFuelInput,
        )

        mock_sim = MagicMock()
        mock_weather = MagicMock()
        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)

        inp = SeferFuelInput(
            arac_id=999,
            target_date=date(2024, 1, 1),
            cikis_lat=39.9,
            cikis_lon=32.0,
            varis_lat=41.0,
            varis_lon=35.0,
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            result = await estimator.predict(inp)

        assert result is None

    async def test_predict_returns_none_when_route_coords_missing(self):
        """predict() returns None when no coordinates provided."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimator,
            SeferFuelInput,
        )

        mock_sim = MagicMock()
        mock_weather = MagicMock()
        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        fake_arac = MagicMock()
        fake_arac.uretim_tarihi = date(2019, 1, 1)
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=fake_arac)

        # No coordinates, no lokasyon_id → route resolution fails
        inp = SeferFuelInput(
            arac_id=1,
            target_date=date(2024, 1, 1),
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            result = await estimator.predict(inp)

        assert result is None

    async def test_predict_returns_none_when_mapbox_fails(self):
        """predict() returns None when RouteSimulator.simulate returns None."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimator,
            SeferFuelInput,
        )

        mock_sim = MagicMock()
        mock_sim.simulate = AsyncMock(return_value=None)
        mock_weather = MagicMock()
        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        fake_arac = MagicMock()
        fake_arac.uretim_tarihi = date(2019, 1, 1)
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=fake_arac)

        inp = SeferFuelInput(
            arac_id=1,
            target_date=date(2024, 1, 1),
            cikis_lat=39.9,
            cikis_lon=32.0,
            varis_lat=41.0,
            varis_lon=35.0,
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            result = await estimator.predict(inp)

        assert result is None

    async def test_edge_case_bos_sefer_sets_ton_zero(self):
        """bos_sefer=True forces ton=0 in physics simulation."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimator,
            SeferFuelInput,
        )

        captured_ton = {}

        async def fake_simulate(**kwargs):
            captured_ton["ton"] = kwargs.get("ton")
            return _make_sim_result()

        mock_sim = MagicMock()
        mock_sim.simulate = AsyncMock(side_effect=fake_simulate)
        mock_weather = MagicMock()
        mock_weather.get_route_weather_samples = AsyncMock(return_value=[])
        mock_weather.get_seasonal_factor = MagicMock(return_value=1.0)
        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        fake_arac = MagicMock()
        fake_arac.uretim_tarihi = date(2020, 1, 1)
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=fake_arac)

        inp = SeferFuelInput(
            arac_id=1,
            target_date=date(2024, 1, 1),
            ton=22.0,
            bos_sefer=True,
            cikis_lat=39.9,
            cikis_lon=32.0,
            varis_lat=41.0,
            varis_lon=35.0,
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            with patch.object(estimator, "_persist", new=AsyncMock(return_value=1)):
                await estimator.predict(inp, persist=True)

        assert captured_ton.get("ton") == 0.0

    async def test_edge_case_none_arac_yasi_defaults_to_5(self):
        """_derive_arac_yasi returns 5 when uretim_tarihi is None."""
        from app.core.services.sefer_fuel_estimator import SeferFuelEstimator

        estimator = SeferFuelEstimator.__new__(SeferFuelEstimator)
        arac = MagicMock()
        arac.uretim_tarihi = None
        assert estimator._derive_arac_yasi(arac) == 5

    async def test_derive_arac_yasi_none_arac_defaults_to_5(self):
        """_derive_arac_yasi returns 5 when there is no Arac row at all."""
        from app.core.services.sefer_fuel_estimator import SeferFuelEstimator

        estimator = SeferFuelEstimator.__new__(SeferFuelEstimator)
        assert estimator._derive_arac_yasi(None) == 5

    async def test_derive_arac_yasi_real_age_birthday_passed(self):
        """uretim_tarihi geçmiş gün → tam yıl farkı."""
        from datetime import date

        from app.core.services import sefer_fuel_estimator as mod

        estimator = mod.SeferFuelEstimator.__new__(mod.SeferFuelEstimator)
        arac = MagicMock()
        arac.uretim_tarihi = date(2014, 3, 10)
        with patch.object(mod, "dt_date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 10)  # 10 Mart geçti
            assert estimator._derive_arac_yasi(arac) == 12

    async def test_derive_arac_yasi_birthday_not_passed_subtracts_year(self):
        """Bu yılki üretim-günü henüz gelmediyse yaş 1 eksik."""
        from datetime import date

        from app.core.services import sefer_fuel_estimator as mod

        estimator = mod.SeferFuelEstimator.__new__(mod.SeferFuelEstimator)
        arac = MagicMock()
        arac.uretim_tarihi = date(2014, 11, 20)
        with patch.object(mod, "dt_date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 10)  # 20 Kasım gelmedi
            assert estimator._derive_arac_yasi(arac) == 11

    async def test_derive_arac_yasi_future_date_clamped_to_zero(self):
        """Gelecek üretim tarihi negatif yaş üretmez (max 0)."""
        from datetime import date

        from app.core.services import sefer_fuel_estimator as mod

        estimator = mod.SeferFuelEstimator.__new__(mod.SeferFuelEstimator)
        arac = MagicMock()
        arac.uretim_tarihi = date(2030, 1, 1)
        with patch.object(mod, "dt_date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 10)
            assert estimator._derive_arac_yasi(arac) == 0

    async def test_to_legacy_prediction_dict_shape(self):
        """to_legacy_prediction_dict returns the expected shape."""
        from app.core.services.sefer_fuel_estimator import (
            FactorBreakdown,
            SeferFuelEstimate,
        )

        bd = FactorBreakdown(
            physics_baseline=30.0,
            driver=1.0,
            vehicle_age=1.0,
            maintenance=1.0,
            weather_temperature=1.0,
            weather_wind=1.0,
            weather_precipitation=1.0,
            seasonal=1.0,
            ml_correction_weight=0.0,
            final=31.5,
        )
        estimate = SeferFuelEstimate(
            tahmini_tuketim=31.5,
            total_l=141.75,
            distance_km=450.0,
            duration_min=300.0,
            simulation_id=5,
            breakdown=bd,
        )
        d = estimate.to_legacy_prediction_dict()
        assert "tahmini_tuketim" in d
        assert "factors_used" in d
        assert d["factors_used"]["source"] == "SeferFuelEstimator"
        assert d["distance_km"] == 450.0
        assert d["simulation_id"] == 5

    async def test_weather_failure_is_non_fatal(self):
        """Weather fetch failure returns empty list and prediction continues."""
        from app.core.services.sefer_fuel_estimator import (
            SeferFuelEstimate,
            SeferFuelEstimator,
            SeferFuelInput,
        )

        mock_sim = MagicMock()
        mock_sim.simulate = AsyncMock(return_value=_make_sim_result())
        mock_weather = MagicMock()
        mock_weather.get_route_weather_samples = AsyncMock(
            side_effect=ConnectionError("Weather API down")
        )
        mock_weather.get_seasonal_factor = MagicMock(return_value=1.0)
        estimator = SeferFuelEstimator(simulator=mock_sim, weather=mock_weather)

        fake_arac = MagicMock()
        fake_arac.uretim_tarihi = date(2019, 1, 1)
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=fake_arac)

        inp = SeferFuelInput(
            arac_id=1,
            target_date=date(2024, 1, 1),
            cikis_lat=39.9,
            cikis_lon=32.0,
            varis_lat=41.0,
            varis_lon=35.0,
        )

        with patch(
            "app.core.services.sefer_fuel_estimator.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_session_cls.return_value = mock_ctx

            with patch.object(estimator, "_persist", new=AsyncMock(return_value=1)):
                result = await estimator.predict(inp, persist=True)

        # Should still return a result despite weather failure
        assert result is not None
        assert isinstance(result, SeferFuelEstimate)

    async def test_weather_failure_records_silent_fallback(self):
        """Weather fetch failure is recorded on the silent-fallback probe —
        sibling of the elevation degradation — so ops can alarm on a rate
        instead of grepping WARNING lines."""
        from app.core.services.sefer_fuel_estimator import SeferFuelEstimator

        mock_weather = MagicMock()
        mock_weather.get_route_weather_samples = AsyncMock(
            side_effect=ConnectionError("Weather API down")
        )
        estimator = SeferFuelEstimator(simulator=MagicMock(), weather=mock_weather)

        with patch(
            "app.infrastructure.monitoring.silent_fallback_probe.record_silent_fallback"
        ) as mock_record:
            samples = await estimator._fetch_weather_samples(_make_sim_result())

        assert samples == []
        mock_record.assert_called_once()
        assert mock_record.call_args.args[0] == "open_meteo_weather_failed"
