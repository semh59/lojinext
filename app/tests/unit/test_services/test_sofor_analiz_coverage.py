"""
Unit tests for SoforAnalizService — coverage push from 15% to ≥75%.

All DB calls are mocked; no real DB or Redis required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.sofor_analiz_service import SoforAnalizService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_stats(**kwargs):
    defaults = dict(
        sofor_id=1,
        ad_soyad="Ahmet Yilmaz",
        toplam_sefer=10,
        toplam_km=5000.0,
        ort_tuketim=32.0,
        toplam_ton=200.0,
        bos_sefer_sayisi=1,
        toplam_yakit=1600.0,
        en_iyi_tuketim=28.0,
        en_kotu_tuketim=38.0,
        trend="stable",
        guzergah_sayisi=3,
    )
    defaults.update(kwargs)
    return defaults


@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.commit = AsyncMock()

    uow.analiz_repo = MagicMock()
    uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])
    uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

    uow.sofor_repo = MagicMock()
    uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=[])
    uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=[])
    uow.sofor_repo.get_guzergah_performansi = AsyncMock(return_value=[])

    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_all = AsyncMock(return_value=[])
    # AUDIT-045 refactor: elite skor artık get_recent_trips_batch + _calc_elite_from_trips
    # yolundan hesaplanıyor (eski calculate_elite_performance_score değil).
    uow.sefer_repo.get_recent_trips_batch = AsyncMock(return_value={})

    return uow


@pytest.fixture
def service(mock_uow):
    svc = SoforAnalizService(uow=mock_uow)
    return svc


# ---------------------------------------------------------------------------
# calculate_trend — pure method
# ---------------------------------------------------------------------------


class TestCalculateTrend:
    def test_insufficient_data_returns_stable(self):
        svc = SoforAnalizService()
        assert svc.calculate_trend([30, 31, 32]) == "stable"

    def test_exactly_5_points_no_change_returns_stable(self):
        svc = SoforAnalizService()
        values = [30.0, 30.0, 30.0, 30.0, 30.0]
        assert svc.calculate_trend(values) == "stable"

    def test_improving_trend_when_consumption_drops(self):
        svc = SoforAnalizService()
        # First half high, second half low → improving
        values = [40.0, 39.0, 38.0, 37.0, 36.0, 25.0, 24.0, 23.0, 22.0, 21.0]
        result = svc.calculate_trend(values)
        assert result == "improving"

    def test_declining_trend_when_consumption_rises(self):
        svc = SoforAnalizService()
        # First half low, second half high → declining
        values = [20.0, 21.0, 22.0, 23.0, 24.0, 35.0, 36.0, 37.0, 38.0, 39.0]
        result = svc.calculate_trend(values)
        assert result == "declining"

    def test_stable_within_5pct_threshold(self):
        svc = SoforAnalizService()
        # All values near 30 — change well within ±5%
        values = [30.0, 30.5, 30.2, 29.8, 30.1, 30.3, 30.0, 29.9, 30.4, 30.1]
        assert svc.calculate_trend(values) == "stable"

    def test_zero_first_half_returns_stable(self):
        svc = SoforAnalizService()
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        assert svc.calculate_trend(values) == "stable"


# ---------------------------------------------------------------------------
# calculate_performance_score — pure method
# ---------------------------------------------------------------------------


class TestCalculatePerformanceScore:
    def test_no_data_returns_50(self):
        svc = SoforAnalizService()
        assert svc.calculate_performance_score(0.0, 0.0, 0) == 50.0

    def test_zero_fleet_avg_returns_50(self):
        svc = SoforAnalizService()
        assert svc.calculate_performance_score(30.0, 0.0, 10) == 50.0

    def test_below_fleet_avg_gives_bonus(self):
        svc = SoforAnalizService()
        # Driver uses 25 vs fleet 30 → should score above 50
        score = svc.calculate_performance_score(25.0, 30.0, 20)
        assert score > 50.0

    def test_above_fleet_avg_gives_penalty(self):
        svc = SoforAnalizService()
        # Driver uses 40 vs fleet 30 → should score below 50
        score = svc.calculate_performance_score(40.0, 30.0, 20)
        assert score < 50.0

    def test_score_capped_at_100(self):
        svc = SoforAnalizService()
        # Extremely efficient driver
        score = svc.calculate_performance_score(1.0, 40.0, 100)
        assert score <= 100.0

    def test_score_floored_at_0(self):
        svc = SoforAnalizService()
        # Extremely inefficient driver
        score = svc.calculate_performance_score(100.0, 10.0, 5)
        assert score >= 0.0

    def test_experience_bonus_with_more_trips(self):
        svc = SoforAnalizService()
        score_few = svc.calculate_performance_score(30.0, 30.0, 1)
        score_many = svc.calculate_performance_score(30.0, 30.0, 100)
        assert score_many > score_few


# ---------------------------------------------------------------------------
# get_driver_stats
# ---------------------------------------------------------------------------


class TestGetDriverStats:
    async def test_empty_sefer_stats_returns_empty_list(self, service, mock_uow):
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])
        result = await service.get_driver_stats()
        assert result == []

    async def test_single_driver_no_elite_score(self, service, mock_uow):
        stats = [_make_stats()]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_driver_stats(include_elite_score=False)

        assert len(result) == 1
        ds = result[0]
        assert ds.sofor_id == 1
        assert ds.ort_tuketim == 32.0
        assert ds.performans_puani is None

    async def test_filo_karsilastirma_positive_when_below_avg(self, service, mock_uow):
        stats = [_make_stats(ort_tuketim=28.0)]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_driver_stats(include_elite_score=False)
        assert result[0].filo_karsilastirma > 0

    async def test_filo_karsilastirma_zero_when_fleet_avg_zero(self, service, mock_uow):
        stats = [_make_stats()]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=0.0)

        result = await service.get_driver_stats(include_elite_score=False)
        assert result[0].filo_karsilastirma == 0.0

    async def test_single_driver_with_sofor_id(self, service, mock_uow):
        stats = [_make_stats()]
        mock_uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_driver_stats(sofor_id=1, include_elite_score=False)
        assert len(result) == 1

    async def test_elite_score_exception_becomes_none(self, service, mock_uow):
        stats = [_make_stats()]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        with patch.object(
            service,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            side_effect=RuntimeError("test error"),
        ):
            result = await service.get_driver_stats(include_elite_score=True)

        assert result[0].performans_puani is None

    async def test_none_ort_tuketim_becomes_zero(self, service, mock_uow):
        stats = [_make_stats(ort_tuketim=None)]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_driver_stats(include_elite_score=False)
        assert result[0].ort_tuketim == 0.0


# ---------------------------------------------------------------------------
# compare_drivers
# ---------------------------------------------------------------------------


class TestCompareDrivers:
    async def test_empty_returns_empty_structure(self, service, mock_uow):
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])
        result = await service.compare_drivers()
        assert result["en_verimli"] is None
        assert result["ranking"] == []

    async def test_filters_drivers_fewer_than_5_seferler(self, service, mock_uow):
        stats = [_make_stats(toplam_sefer=3)]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        # compare_drivers internally calls get_driver_stats(); patch elite score calc
        with patch.object(
            service, "_calc_elite_from_trips", new_callable=AsyncMock, return_value=None
        ):
            result = await service.compare_drivers()
        assert result["ranking"] == []

    async def test_valid_driver_appears_in_ranking(self, service, mock_uow):
        stats = [_make_stats(toplam_sefer=10, performans_puani=80.0)]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        with patch.object(
            service,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            return_value=80.0,
        ):
            result = await service.compare_drivers()

        assert len(result["ranking"]) == 1
        assert result["en_verimli"].sofor_id == 1

    async def test_compare_filters_by_sofor_ids(self, service, mock_uow):
        stats = [_make_stats(sofor_id=1), _make_stats(sofor_id=2, ad_soyad="Ali")]
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        with patch.object(
            service, "_calc_elite_from_trips", new_callable=AsyncMock, return_value=75.0
        ):
            result = await service.compare_drivers(sofor_ids=[1])

        ids = [s.sofor_id for s in result["ranking"]]
        assert 2 not in ids


# ---------------------------------------------------------------------------
# get_driver_trend
# ---------------------------------------------------------------------------


class TestGetDriverTrend:
    async def test_empty_tuketimler_returns_stable(self, service, mock_uow):
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=[])
        result = await service.get_driver_trend(sofor_id=1)
        assert result["trend"] == "stable"
        assert result["slope"] == 0.0

    async def test_fewer_than_5_values_returns_stable(self, service, mock_uow):
        records = [{"tuketim": v} for v in [30.0, 31.0, 32.0]]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await service.get_driver_trend(sofor_id=1)
        assert result["trend"] == "stable"

    async def test_improving_trend(self, service, mock_uow):
        values = [40.0, 39.0, 38.0, 37.0, 36.0, 25.0, 24.0, 23.0, 22.0, 21.0]
        records = [{"tuketim": v} for v in reversed(values)]  # repo returns desc
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await service.get_driver_trend(sofor_id=1)
        assert result["trend"] == "improving"

    async def test_slope_calculated_for_n_gte_3(self, service, mock_uow):
        values = [30.0, 32.0, 34.0, 36.0, 38.0]
        records = [{"tuketim": v} for v in reversed(values)]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await service.get_driver_trend(sofor_id=1)
        assert "slope" in result
        # Rising slope should be positive
        assert result["slope"] > 0

    async def test_moving_avg_length_matches_values(self, service, mock_uow):
        values = [30.0, 31.0, 32.0, 33.0, 34.0, 35.0]
        records = [{"tuketim": v} for v in reversed(values)]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await service.get_driver_trend(sofor_id=1)
        assert len(result["moving_avg"]) == len(result["values"])

    async def test_none_tuketim_filtered_out(self, service, mock_uow):
        records = [{"tuketim": None}, {"tuketim": 30.0}]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await service.get_driver_trend(sofor_id=1)
        assert result["values"] == [30.0]


# ---------------------------------------------------------------------------
# get_route_performance
# ---------------------------------------------------------------------------


class TestGetRoutePerformance:
    async def test_empty_returns_empty_list(self, service, mock_uow):
        mock_uow.sofor_repo.get_guzergah_performansi = AsyncMock(return_value=[])
        result = await service.get_route_performance(sofor_id=1)
        assert result == []

    async def test_route_fark_positive_when_below_avg(self, service, mock_uow):
        guzergahlar = [
            {
                "guzergah": "ANK-IST",
                "sefer_sayisi": 5,
                "toplam_km": 2250,
                "ort_tuketim": 28.0,
                "en_iyi": 25.0,
                "en_kotu": 32.0,
            }
        ]
        mock_uow.sofor_repo.get_guzergah_performansi = AsyncMock(
            return_value=guzergahlar
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_route_performance(sofor_id=1)
        assert len(result) == 1
        assert result[0]["fark"] > 0

    async def test_route_fark_zero_when_fleet_avg_zero(self, service, mock_uow):
        guzergahlar = [
            {
                "guzergah": "IST-ANK",
                "sefer_sayisi": 3,
                "ort_tuketim": 30.0,
                "en_iyi": None,
                "en_kotu": None,
            }
        ]
        mock_uow.sofor_repo.get_guzergah_performansi = AsyncMock(
            return_value=guzergahlar
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=0.0)

        result = await service.get_route_performance(sofor_id=1)
        assert result[0]["fark"] == 0

    async def test_route_none_ort_tuketim_handled(self, service, mock_uow):
        guzergahlar = [
            {
                "guzergah": "IST-BUR",
                "sefer_sayisi": 2,
                "ort_tuketim": None,
                "en_iyi": None,
                "en_kotu": None,
            }
        ]
        mock_uow.sofor_repo.get_guzergah_performansi = AsyncMock(
            return_value=guzergahlar
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await service.get_route_performance(sofor_id=1)
        assert result[0]["ort_tuketim"] == 0.0


# ---------------------------------------------------------------------------
# calculate_elite_performance_score
# ---------------------------------------------------------------------------


class TestCalculateElitePerformanceScore:
    async def test_no_seferler_returns_none(self, service, mock_uow):
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=[])

        with patch("app.core.services.sofor_analiz_service.get_prediction_service"):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await service.calculate_elite_performance_score(sofor_id=1)

        assert result is None

    async def test_efficient_driver_scores_above_75(self, service, mock_uow):
        seferler = [
            {
                "arac_id": 1,
                "mesafe_km": 450.0,
                "net_kg": 20000,
                "ascent_m": 500,
                "descent_m": 500,
                "tuketim": 27.0,
            }
        ]
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=seferler)

        mock_pred_svc = MagicMock()
        mock_pred_svc.predict_consumption = AsyncMock(
            return_value={"prediction_l_100km": 30.0}
        )

        with patch(
            "app.core.services.sofor_analiz_service.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await service.calculate_elite_performance_score(sofor_id=1)

        # actual < expected → avg_dev < 0 → score = 75 + abs_dev*1.5 > 75
        assert score is not None
        assert score > 75.0

    async def test_inefficient_driver_scores_below_75(self, service, mock_uow):
        seferler = [
            {
                "arac_id": 1,
                "mesafe_km": 450.0,
                "net_kg": 20000,
                "ascent_m": 500,
                "descent_m": 500,
                "tuketim": 40.0,
            }
        ]
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=seferler)

        mock_pred_svc = MagicMock()
        mock_pred_svc.predict_consumption = AsyncMock(
            return_value={"prediction_l_100km": 30.0}
        )

        with patch(
            "app.core.services.sofor_analiz_service.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await service.calculate_elite_performance_score(sofor_id=1)

        assert score is not None
        assert score < 75.0

    async def test_no_valid_deviations_returns_none(self, service, mock_uow):
        # Trip with no actual tuketim
        seferler = [
            {
                "arac_id": 1,
                "mesafe_km": 450.0,
                "net_kg": 20000,
                "tuketim": None,
            }
        ]
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=seferler)

        mock_pred_svc = MagicMock()

        with patch(
            "app.core.services.sofor_analiz_service.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await service.calculate_elite_performance_score(sofor_id=1)

        assert result is None

    async def test_prediction_exception_returns_none_deviation(self, service, mock_uow):
        seferler = [
            {
                "arac_id": 1,
                "mesafe_km": 450.0,
                "net_kg": 20000,
                "tuketim": 30.0,
            }
        ]
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=seferler)

        mock_pred_svc = MagicMock()
        mock_pred_svc.predict_consumption = AsyncMock(
            side_effect=RuntimeError("prediction failed")
        )

        with patch(
            "app.core.services.sofor_analiz_service.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await service.calculate_elite_performance_score(sofor_id=1)

        assert result is None

    async def test_score_clamped_between_0_and_100(self, service, mock_uow):
        # Extremely efficient: actual=1, expected=100 → avg_dev ≈ -99%
        seferler = [
            {
                "arac_id": 1,
                "mesafe_km": 450.0,
                "net_kg": 20000,
                "tuketim": 1.0,
            }
        ]
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=seferler)

        mock_pred_svc = MagicMock()
        mock_pred_svc.predict_consumption = AsyncMock(
            return_value={"prediction_l_100km": 100.0}
        )

        with patch(
            "app.core.services.sofor_analiz_service.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await service.calculate_elite_performance_score(sofor_id=1)

        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# analiz_repo / sofor_repo property access
# ---------------------------------------------------------------------------


class TestPropertyFallback:
    def test_analiz_repo_uses_uow_when_set(self, service, mock_uow):
        repo = service.analiz_repo
        assert repo is mock_uow.analiz_repo

    def test_sofor_repo_uses_uow_when_set(self, service, mock_uow):
        repo = service.sofor_repo
        assert repo is mock_uow.sofor_repo

    def test_analiz_repo_falls_back_without_uow(self):
        svc = SoforAnalizService(uow=None)
        with patch(
            "app.database.repositories.analiz_repo.get_analiz_repo",
            return_value=MagicMock(),
        ) as mock_get:
            _ = svc.analiz_repo
            mock_get.assert_called_once()

    def test_sofor_repo_falls_back_without_uow(self):
        svc = SoforAnalizService(uow=None)
        with patch(
            "app.database.repositories.sofor_repo.get_sofor_repo",
            return_value=MagicMock(),
        ) as mock_get:
            _ = svc.sofor_repo
            mock_get.assert_called_once()
