"""
Unit tests for v2.modules.driver.application.driver_stats — coverage push from 15% to ≥75%.

All DB calls are mocked; no real DB or Redis required.

NOT: eski ``SoforAnalizService`` sınıfı silindi (B.1 free-function split);
tüm metotlar artık ``uow: UnitOfWork | None = None`` alan modül-seviyeli
free function'lar (bkz. v2/modules/driver/CLAUDE.md).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.driver.application import driver_stats as driver_stats_mod
from v2.modules.driver.application.driver_stats import (
    _calc_elite_from_trips,
    calculate_elite_performance_score,
    calculate_performance_score,
    calculate_trend,
    compare_drivers,
    get_driver_stats,
    get_driver_trend,
    get_route_performance,
)
from v2.modules.driver.infrastructure import (
    driver_metrics_queries as driver_metrics_queries_mod,
)

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


# ---------------------------------------------------------------------------
# calculate_trend — pure function
# ---------------------------------------------------------------------------


class TestCalculateTrend:
    def test_insufficient_data_returns_stable(self):
        assert calculate_trend([30, 31, 32]) == "stable"

    def test_exactly_5_points_no_change_returns_stable(self):
        values = [30.0, 30.0, 30.0, 30.0, 30.0]
        assert calculate_trend(values) == "stable"

    def test_improving_trend_when_consumption_drops(self):
        # First half high, second half low → improving
        values = [40.0, 39.0, 38.0, 37.0, 36.0, 25.0, 24.0, 23.0, 22.0, 21.0]
        result = calculate_trend(values)
        assert result == "improving"

    def test_declining_trend_when_consumption_rises(self):
        # First half low, second half high → declining
        values = [20.0, 21.0, 22.0, 23.0, 24.0, 35.0, 36.0, 37.0, 38.0, 39.0]
        result = calculate_trend(values)
        assert result == "declining"

    def test_stable_within_5pct_threshold(self):
        # All values near 30 — change well within ±5%
        values = [30.0, 30.5, 30.2, 29.8, 30.1, 30.3, 30.0, 29.9, 30.4, 30.1]
        assert calculate_trend(values) == "stable"

    def test_zero_first_half_returns_stable(self):
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        assert calculate_trend(values) == "stable"


# ---------------------------------------------------------------------------
# calculate_performance_score — pure function
# ---------------------------------------------------------------------------


class TestCalculatePerformanceScore:
    def test_no_data_returns_50(self):
        assert calculate_performance_score(0.0, 0.0, 0) == 50.0

    def test_zero_fleet_avg_returns_50(self):
        assert calculate_performance_score(30.0, 0.0, 10) == 50.0

    def test_below_fleet_avg_gives_bonus(self):
        # Driver uses 25 vs fleet 30 → should score above 50
        score = calculate_performance_score(25.0, 30.0, 20)
        assert score > 50.0

    def test_above_fleet_avg_gives_penalty(self):
        # Driver uses 40 vs fleet 30 → should score below 50
        score = calculate_performance_score(40.0, 30.0, 20)
        assert score < 50.0

    def test_score_capped_at_100(self):
        # Extremely efficient driver
        score = calculate_performance_score(1.0, 40.0, 100)
        assert score <= 100.0

    def test_score_floored_at_0(self):
        # Extremely inefficient driver
        score = calculate_performance_score(100.0, 10.0, 5)
        assert score >= 0.0

    def test_experience_bonus_with_more_trips(self):
        score_few = calculate_performance_score(30.0, 30.0, 1)
        score_many = calculate_performance_score(30.0, 30.0, 100)
        assert score_many > score_few


# ---------------------------------------------------------------------------
# get_driver_stats
# ---------------------------------------------------------------------------


class TestGetDriverStats:
    async def test_empty_sefer_stats_returns_empty_list(self, mock_uow, monkeypatch):
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=[]),
        )
        result = await get_driver_stats(uow=mock_uow)
        assert result == []

    async def test_single_driver_no_elite_score(self, mock_uow, monkeypatch):
        stats = [_make_stats()]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await get_driver_stats(include_elite_score=False, uow=mock_uow)

        assert len(result) == 1
        ds = result[0]
        assert ds.sofor_id == 1
        assert ds.ort_tuketim == 32.0
        assert ds.performans_puani is None

    async def test_filo_karsilastirma_positive_when_below_avg(
        self, mock_uow, monkeypatch
    ):
        stats = [_make_stats(ort_tuketim=28.0)]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await get_driver_stats(include_elite_score=False, uow=mock_uow)
        assert result[0].filo_karsilastirma > 0

    async def test_filo_karsilastirma_zero_when_fleet_avg_zero(
        self, mock_uow, monkeypatch
    ):
        stats = [_make_stats()]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=0.0)

        result = await get_driver_stats(include_elite_score=False, uow=mock_uow)
        assert result[0].filo_karsilastirma == 0.0

    async def test_single_driver_with_sofor_id(self, mock_uow):
        stats = [_make_stats()]
        mock_uow.sofor_repo.get_sefer_stats = AsyncMock(return_value=stats)
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await get_driver_stats(
            sofor_id=1, include_elite_score=False, uow=mock_uow
        )
        assert len(result) == 1

    async def test_elite_score_exception_becomes_none(self, mock_uow, monkeypatch):
        stats = [_make_stats()]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)
        mock_uow.sefer_repo.get_recent_trips_batch = AsyncMock(
            return_value={1: [{"tuketim": 30.0}]}
        )

        with patch.object(
            driver_stats_mod,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            side_effect=RuntimeError("test error"),
        ):
            result = await get_driver_stats(include_elite_score=True, uow=mock_uow)

        assert result[0].performans_puani is None

    async def test_none_ort_tuketim_becomes_zero(self, mock_uow, monkeypatch):
        stats = [_make_stats(ort_tuketim=None)]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        result = await get_driver_stats(include_elite_score=False, uow=mock_uow)
        assert result[0].ort_tuketim == 0.0


# ---------------------------------------------------------------------------
# compare_drivers
# ---------------------------------------------------------------------------


class TestCompareDrivers:
    async def test_empty_returns_empty_structure(self, mock_uow, monkeypatch):
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=[]),
        )
        result = await compare_drivers(uow=mock_uow)
        assert result["en_verimli"] is None
        assert result["ranking"] == []

    async def test_filters_drivers_fewer_than_5_seferler(self, mock_uow, monkeypatch):
        stats = [_make_stats(toplam_sefer=3)]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        # compare_drivers internally calls get_driver_stats(); patch elite score calc
        with patch.object(
            driver_stats_mod,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await compare_drivers(uow=mock_uow)
        assert result["ranking"] == []

    async def test_valid_driver_appears_in_ranking(self, mock_uow, monkeypatch):
        stats = [_make_stats(toplam_sefer=10, performans_puani=80.0)]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        with patch.object(
            driver_stats_mod,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            return_value=80.0,
        ):
            result = await compare_drivers(uow=mock_uow)

        assert len(result["ranking"]) == 1
        assert result["en_verimli"].sofor_id == 1

    async def test_compare_filters_by_sofor_ids(self, mock_uow, monkeypatch):
        stats = [_make_stats(sofor_id=1), _make_stats(sofor_id=2, ad_soyad="Ali")]
        monkeypatch.setattr(
            driver_metrics_queries_mod,
            "get_bulk_driver_metrics",
            AsyncMock(return_value=stats),
        )
        mock_uow.analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=33.0)

        with patch.object(
            driver_stats_mod,
            "_calc_elite_from_trips",
            new_callable=AsyncMock,
            return_value=75.0,
        ):
            result = await compare_drivers(sofor_ids=[1], uow=mock_uow)

        ids = [s.sofor_id for s in result["ranking"]]
        assert 2 not in ids


# ---------------------------------------------------------------------------
# get_driver_trend
# ---------------------------------------------------------------------------


class TestGetDriverTrend:
    async def test_empty_tuketimler_returns_stable(self, mock_uow):
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=[])
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert result["trend"] == "stable"
        assert result["slope"] == 0.0

    async def test_fewer_than_5_values_returns_stable(self, mock_uow):
        records = [{"tuketim": v} for v in [30.0, 31.0, 32.0]]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert result["trend"] == "stable"

    async def test_improving_trend(self, mock_uow):
        values = [40.0, 39.0, 38.0, 37.0, 36.0, 25.0, 24.0, 23.0, 22.0, 21.0]
        records = [{"tuketim": v} for v in reversed(values)]  # repo returns desc
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert result["trend"] == "improving"

    async def test_slope_calculated_for_n_gte_3(self, mock_uow):
        values = [30.0, 32.0, 34.0, 36.0, 38.0]
        records = [{"tuketim": v} for v in reversed(values)]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert "slope" in result
        # Rising slope should be positive
        assert result["slope"] > 0

    async def test_moving_avg_length_matches_values(self, mock_uow):
        values = [30.0, 31.0, 32.0, 33.0, 34.0, 35.0]
        records = [{"tuketim": v} for v in reversed(values)]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert len(result["moving_avg"]) == len(result["values"])

    async def test_none_tuketim_filtered_out(self, mock_uow):
        records = [{"tuketim": None}, {"tuketim": 30.0}]
        mock_uow.sofor_repo.get_yakit_tuketimi = AsyncMock(return_value=records)
        result = await get_driver_trend(sofor_id=1, uow=mock_uow)
        assert result["values"] == [30.0]


# ---------------------------------------------------------------------------
# get_route_performance
# ---------------------------------------------------------------------------


class TestGetRoutePerformance:
    async def test_empty_returns_empty_list(self, mock_uow):
        mock_uow.sofor_repo.get_guzergah_performansi = AsyncMock(return_value=[])
        result = await get_route_performance(sofor_id=1, uow=mock_uow)
        assert result == []

    async def test_route_fark_positive_when_below_avg(self, mock_uow):
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

        result = await get_route_performance(sofor_id=1, uow=mock_uow)
        assert len(result) == 1
        assert result[0]["fark"] > 0

    async def test_route_fark_zero_when_fleet_avg_zero(self, mock_uow):
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

        result = await get_route_performance(sofor_id=1, uow=mock_uow)
        assert result[0]["fark"] == 0

    async def test_route_none_ort_tuketim_handled(self, mock_uow):
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

        result = await get_route_performance(sofor_id=1, uow=mock_uow)
        assert result[0]["ort_tuketim"] == 0.0


# ---------------------------------------------------------------------------
# calculate_elite_performance_score
# ---------------------------------------------------------------------------


class TestCalculateElitePerformanceScore:
    async def test_no_seferler_returns_none(self, mock_uow):
        mock_uow.sefer_repo.get_all = AsyncMock(return_value=[])

        with patch("v2.modules.driver.application.driver_stats.get_prediction_service"):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        assert result is None

    async def test_efficient_driver_scores_above_75(self, mock_uow):
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
            return_value={"tahmini_tuketim": 30.0}
        )

        with patch(
            "v2.modules.driver.application.driver_stats.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        # actual < expected → avg_dev < 0 → score = 75 + abs_dev*1.5 > 75
        assert score is not None
        assert score > 75.0

    async def test_inefficient_driver_scores_below_75(self, mock_uow):
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
            return_value={"tahmini_tuketim": 30.0}
        )

        with patch(
            "v2.modules.driver.application.driver_stats.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        assert score is not None
        assert score < 75.0

    async def test_no_valid_deviations_returns_none(self, mock_uow):
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
            "v2.modules.driver.application.driver_stats.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        assert result is None

    async def test_prediction_exception_returns_none_deviation(self, mock_uow):
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
            "v2.modules.driver.application.driver_stats.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                result = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        assert result is None

    async def test_score_clamped_between_0_and_100(self, mock_uow):
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
            return_value={"tahmini_tuketim": 100.0}
        )

        with patch(
            "v2.modules.driver.application.driver_stats.get_prediction_service",
            return_value=mock_pred_svc,
        ):
            with patch("app.config.settings") as mock_settings:
                mock_settings.ELITE_SCORE_TRIP_LIMIT = 20
                score = await calculate_elite_performance_score(
                    sofor_id=1, uow=mock_uow
                )

        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# _repos — analiz_repo / sofor_repo / sefer_repo fallback resolution
# ---------------------------------------------------------------------------


class TestReposFallback:
    def test_repos_uses_uow_when_set(self, mock_uow):
        analiz_repo, sofor_repo, sefer_repo = driver_stats_mod._repos(mock_uow)
        assert analiz_repo is mock_uow.analiz_repo
        assert sofor_repo is mock_uow.sofor_repo
        assert sefer_repo is mock_uow.sefer_repo

    def test_repos_falls_back_without_uow(self):
        with (
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=MagicMock(),
            ) as mock_analiz,
            patch(
                "v2.modules.driver.infrastructure.repository.get_sofor_repo",
                return_value=MagicMock(),
            ) as mock_sofor,
            patch(
                "v2.modules.trip.infrastructure.repository.get_sefer_repo",
                return_value=MagicMock(),
            ) as mock_sefer,
        ):
            driver_stats_mod._repos(None)
            mock_analiz.assert_called_once()
            mock_sofor.assert_called_once()
            mock_sefer.assert_called_once()


class TestCalcEliteFromTrips:
    async def test_empty_trips_returns_none(self):
        result = await _calc_elite_from_trips([])
        assert result is None
