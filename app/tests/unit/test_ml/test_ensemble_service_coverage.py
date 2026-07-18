"""
Coverage tests for EnsemblePredictorService (ensemble_service.py).
Focuses on the service layer: LRU cache, training hash, vehicle class logic,
predict_consumption, and singleton accessor.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_arac(**overrides):
    base = {
        "id": 1,
        "plaka": "34ABC01",
        "marka": "MAN",
        "model": "TGX",
        "yil": 2018,
        "tank_kapasitesi": 600,
        "bos_agirlik_kg": 9000,
        "euro_sinifi": "EURO6",
        "aktif": True,
    }
    base.update(overrides)
    return base


def _make_service():
    from app.core.ml.ensemble_service import EnsemblePredictorService

    svc = EnsemblePredictorService()
    # Inject mock repos
    svc._arac_repo = MagicMock()
    svc._sefer_repo = MagicMock()
    svc._dorse_repo = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# Tests: Vehicle class logic
# ---------------------------------------------------------------------------


class TestVehicleClassLogic:
    def test_heavy_class_above_500(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        assert svc._get_vehicle_class({"tank_kapasitesi": 600}) == "heavy"

    def test_medium_class_200_to_500(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        assert svc._get_vehicle_class({"tank_kapasitesi": 300}) == "medium"

    def test_light_class_below_200(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        assert svc._get_vehicle_class({"tank_kapasitesi": 100}) == "light"

    def test_none_tank_defaults_to_light(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        assert svc._get_vehicle_class({"tank_kapasitesi": None}) == "light"

    def test_vehicle_class_model_id_heavy(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        mid = svc._get_vehicle_class_model_id({"tank_kapasitesi": 600})
        assert mid == EnsemblePredictorService.VEHICLE_CLASS_MODEL_IDS["heavy"]


# ---------------------------------------------------------------------------
# Tests: lazy repo properties
# ---------------------------------------------------------------------------


class TestLazyRepoProperties:
    def test_arac_repo_property_lazy_loads(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        mock_repo = MagicMock()

        with patch(
            "v2.modules.fleet.public.get_arac_repo",
            return_value=mock_repo,
        ):
            repo = svc.arac_repo

        assert repo is mock_repo

    def test_sefer_repo_property_lazy_loads(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        mock_repo = MagicMock()

        with patch(
            "app.database.repositories.sefer_repo.get_sefer_repo",
            return_value=mock_repo,
        ):
            repo = svc.sefer_repo

        assert repo is mock_repo

    def test_dorse_repo_property_lazy_loads(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        mock_repo = MagicMock()

        with patch(
            "v2.modules.fleet.public.get_dorse_repo",
            return_value=mock_repo,
        ):
            repo = svc.dorse_repo

        assert repo is mock_repo


# ---------------------------------------------------------------------------
# Tests: _resolve_trip_date
# ---------------------------------------------------------------------------


class TestResolveTripDate:
    def test_date_object_returned_as_is(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        d = date(2025, 6, 1)
        assert EnsemblePredictorService._resolve_trip_date(d) == d

    def test_iso_string_parsed(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        result = EnsemblePredictorService._resolve_trip_date("2025-03-15")
        assert result == date(2025, 3, 15)

    def test_invalid_string_returns_today(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        result = EnsemblePredictorService._resolve_trip_date("not-a-date")
        assert result == date.today()

    def test_none_returns_today(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        result = EnsemblePredictorService._resolve_trip_date(None)
        assert result == date.today()


# ---------------------------------------------------------------------------
# Tests: _extract_route_analysis
# ---------------------------------------------------------------------------


class TestExtractRouteAnalysis:
    def test_none_if_no_rota_detay(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        assert EnsemblePredictorService._extract_route_analysis({}) is None

    def test_none_if_rota_detay_not_dict(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        assert (
            EnsemblePredictorService._extract_route_analysis({"rota_detay": "string"})
            is None
        )

    def test_extracts_nested_route_analysis(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        sefer = {"rota_detay": {"route_analysis": {"terrain": "mountainous"}}}
        result = EnsemblePredictorService._extract_route_analysis(sefer)
        assert result == {"terrain": "mountainous"}

    def test_falls_back_to_rota_detay_if_no_route_analysis_key(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        sefer = {"rota_detay": {"some_key": 1}}
        result = EnsemblePredictorService._extract_route_analysis(sefer)
        assert result == {"some_key": 1}


# ---------------------------------------------------------------------------
# Tests: _calculate_training_hash
# ---------------------------------------------------------------------------


class TestCalculateTrainingHash:
    def test_empty_returns_empty_string(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        assert svc._calculate_training_hash([]) == "empty"

    def test_hash_is_string(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        seferler = [{"id": i, "mesafe_km": 500, "ton": 20} for i in range(5)]
        result = svc._calculate_training_hash(seferler)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_different_data_gives_different_hash(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        s1 = [{"id": 1, "mesafe_km": 500, "ton": 20}]
        s2 = [{"id": 2, "mesafe_km": 800, "ton": 30}]
        assert svc._calculate_training_hash(s1) != svc._calculate_training_hash(s2)

    def test_same_data_gives_same_hash(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        seferler = [{"id": i, "mesafe_km": 400 + i, "ton": 20} for i in range(10)]
        h1 = svc._calculate_training_hash(seferler)
        h2 = svc._calculate_training_hash(seferler)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Tests: get_predictor (LRU cache)
# ---------------------------------------------------------------------------


class TestGetPredictor:
    def test_creates_new_predictor(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        p = svc.get_predictor(42)
        assert p is not None

    def test_returns_same_predictor_second_call(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        p1 = svc.get_predictor(42)
        p2 = svc.get_predictor(42)
        assert p1 is p2

    def test_lru_eviction_at_limit(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        svc.MAX_PREDICTORS = 3

        # Patch model loading path to avoid file-system checks
        with patch("pathlib.Path.exists", return_value=False):
            for i in range(5):
                svc.get_predictor(i)

        # Only 3 should remain
        assert len(svc.predictors) == 3
        # The first two (0, 1) should have been evicted
        assert 0 not in svc.predictors
        assert 1 not in svc.predictors

    def test_lru_moves_to_end_on_access(self):
        from app.core.ml.ensemble_service import EnsemblePredictorService

        svc = EnsemblePredictorService()
        with patch("pathlib.Path.exists", return_value=False):
            svc.get_predictor(1)
            svc.get_predictor(2)
            svc.get_predictor(3)
            # Access 1 again — should become most recently used
            svc.get_predictor(1)

        # 1 should be at the end (most recently used)
        keys = list(svc.predictors.keys())
        assert keys[-1] == 1


# ---------------------------------------------------------------------------
# Tests: predict_consumption (unit — mocked arac + predictor)
# ---------------------------------------------------------------------------


class TestPredictConsumption:
    @pytest.fixture
    def svc(self):
        return _make_service()

    async def test_returns_error_when_arac_not_found(self, svc):
        svc._arac_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.predict_consumption(arac_id=999, mesafe_km=500, ton=20)

        assert result["success"] is False
        assert "Araç" in result["error"]

    async def test_success_with_valid_arac(self, svc):
        arac = _make_arac()
        svc._arac_repo.get_by_id = AsyncMock(return_value=arac)

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 32.5
        mock_prediction.confidence_low = 29.0
        mock_prediction.confidence_high = 36.0
        mock_prediction.physics_only = 30.0
        mock_prediction.ml_correction = 2.5

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = mock_prediction
        mock_predictor.is_trained = True

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await svc.predict_consumption(arac_id=1, mesafe_km=500, ton=20)

        assert result["success"] is True
        assert "tahmin_l_100km" in result
        assert "tahmin_litre" in result

    async def test_uses_uow_when_provided(self, svc):
        arac = _make_arac()
        mock_uow = AsyncMock()
        mock_uow.arac_repo = MagicMock()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)
        mock_uow.dorse_repo = MagicMock()
        mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 30.0
        mock_prediction.confidence_low = 27.0
        mock_prediction.confidence_high = 33.0
        mock_prediction.physics_only = 30.0
        mock_prediction.ml_correction = 0.0

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = mock_prediction
        mock_predictor.is_trained = True

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await svc.predict_consumption(
                arac_id=1, mesafe_km=300, ton=15, uow=mock_uow
            )

        # Should have used uow.arac_repo, not svc._arac_repo
        mock_uow.arac_repo.get_by_id.assert_awaited_once()
        assert result["success"] is True

    async def test_fallback_to_class_model_when_vehicle_untrained(self, svc):
        arac = _make_arac(tank_kapasitesi=600)  # heavy
        svc._arac_repo.get_by_id = AsyncMock(return_value=arac)

        # Untrained vehicle predictor
        untrained = MagicMock()
        untrained.is_trained = False

        # Trained class predictor
        trained = MagicMock()
        trained.is_trained = True
        mock_pred = MagicMock()
        mock_pred.tahmin_l_100km = 33.0
        mock_pred.confidence_low = 30.0
        mock_pred.confidence_high = 36.0
        mock_pred.physics_only = 33.0
        mock_pred.ml_correction = 0.0
        trained.predict.return_value = mock_pred

        def predictor_factory(arac_id):
            if arac_id == 1:
                return untrained
            elif arac_id == 10000:  # heavy class model
                return trained
            return untrained

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await svc.predict_consumption(arac_id=1, mesafe_km=400, ton=20)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests: train_for_vehicle (mocked heavy deps)
# ---------------------------------------------------------------------------


class TestTrainForVehicle:
    @pytest.fixture
    def svc(self):
        return _make_service()

    async def test_returns_error_when_arac_not_found(self, svc):
        svc._arac_repo.get_by_id = AsyncMock(return_value=None)
        result = await svc.train_for_vehicle(arac_id=999)
        assert result["success"] is False

    async def test_returns_error_on_insufficient_trips(self, svc):
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())
        svc._sefer_repo.get_for_training = AsyncMock(return_value=[{"tuketim": 30}] * 5)

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        with (
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    async def test_enrichment_and_fit_called_with_sufficient_data(self, svc):
        """Test the enrichment loop + model.fit call path."""
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())

        trips = [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tarih": "2025-06-01",
                "sofor_id": None,
            }
            for i in range(15)
        ]
        svc._sefer_repo.get_for_training = AsyncMock(return_value=trips)

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.05

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": False,
            "error": "not enough variance",
        }
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        # predictor.fit was called — the enrichment loop ran
        mock_predictor.fit.assert_called_once()
        # Result comes from the predictor's fit response
        assert result["success"] is False

    async def test_train_success_saves_model(self, svc):
        """Test the post-training save path when fit() succeeds."""
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())

        trips = [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tarih": "2025-06-01",
                "sofor_id": None,
            }
            for i in range(15)
        ]
        svc._sefer_repo.get_for_training = AsyncMock(return_value=trips)

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.85,
            "metrics": {"gb_test_r2": 0.85},
            "measurements": {"mae": 1.2, "rmse": 1.5},
            "sample_count": 15,
            "model_weights": {},
        }
        mock_predictor._feature_hash = "abc"
        mock_predictor._physics_version = "v1"

        mock_manager = AsyncMock()
        mock_manager.save_version = AsyncMock(return_value=1)
        mock_analiz_repo = MagicMock()
        mock_analiz_repo.save_model_params = AsyncMock()

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.core.ml.model_manager.get_model_manager",
                return_value=mock_manager,
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True
        mock_manager.save_version.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: train_general_model
# ---------------------------------------------------------------------------


class TestTrainGeneralModel:
    @pytest.fixture
    def svc(self):
        return _make_service()

    async def test_returns_error_on_insufficient_data(self, svc):
        svc._sefer_repo.get_all_for_training = AsyncMock(
            return_value=[{"tuketim": 30}] * 5
        )

        mock_analiz_repo = MagicMock()
        with patch(
            "v2.modules.analytics_executive.public.get_analiz_repo",
            return_value=mock_analiz_repo,
        ):
            result = await svc.train_general_model()

        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    async def test_returns_success_when_fit_succeeds(self, svc):
        trips = [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tank_kapasitesi": 600,
            }
            for i in range(25)
        ]
        svc._sefer_repo.get_all_for_training = AsyncMock(return_value=trips)

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.80,
            "metrics": {"gb_test_r2": 0.80},
            "measurements": {"mae": 1.5, "rmse": 2.0},
            "sample_count": 25,
        }
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

        mock_manager = AsyncMock()
        mock_manager.save_version = AsyncMock(return_value=1)
        mock_analiz_repo = MagicMock()
        mock_analiz_repo.save_model_params = AsyncMock()

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.ml.model_manager.get_model_manager",
                return_value=mock_manager,
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            result = await svc.train_general_model()

        assert result["success"] is True

    async def test_exception_in_train_returns_error(self, svc):
        svc._sefer_repo.get_all_for_training = AsyncMock(
            side_effect=RuntimeError("DB down")
        )
        mock_analiz_repo = MagicMock()
        with patch(
            "v2.modules.analytics_executive.public.get_analiz_repo",
            return_value=mock_analiz_repo,
        ):
            result = await svc.train_general_model()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Tests: predict_batch
# ---------------------------------------------------------------------------


class TestPredictBatch:
    async def test_returns_list_of_results(self):
        svc = _make_service()
        arac = _make_arac()

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 32.5
        mock_prediction.confidence_low = 29.0
        mock_prediction.confidence_high = 36.0
        mock_prediction.physics_only = 30.0
        mock_prediction.ml_correction = 2.5

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = mock_prediction
        mock_predictor.is_trained = True

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.arac_repo = MagicMock()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)
        mock_uow.dorse_repo = MagicMock()
        mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=None)

        requests = [{"arac_id": 1, "mesafe_km": 500, "ton": 20}]

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "app.core.services.weather_service.get_weather_service",
                return_value=mock_weather,
            ),
            patch(
                "v2.modules.driver.public.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            results = await svc.predict_batch(requests)

        assert len(results) == 1
        assert results[0]["success"] is True


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_ensemble_service_returns_instance(self):
        from app.core.ml.ensemble_service import (
            EnsemblePredictorService,
            get_ensemble_service,
        )

        svc = get_ensemble_service()
        assert isinstance(svc, EnsemblePredictorService)

    def test_get_ensemble_service_same_instance(self):
        from app.core.ml.ensemble_service import get_ensemble_service

        a = get_ensemble_service()
        b = get_ensemble_service()
        assert a is b
