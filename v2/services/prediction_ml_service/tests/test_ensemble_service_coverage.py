"""
Coverage tests for EnsemblePredictorService (ensemble_service.py).
Focuses on the service layer: LRU cache, training hash, vehicle class logic,
predict_consumption, and singleton accessor.

Rewired for the service extraction (Task 5, 2026-08-04): the class no
longer holds arac_repo/sefer_repo/dorse_repo lazy properties or accepts a
`uow` kwarg on predict_consumption -- all fleet/driver/trip data now comes
over HTTP via `prediction_ml_service.infrastructure.cross_module_client`,
verified against the real current ensemble_service.py source before
rewriting (not guessed).
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    from prediction_ml_service.application.ensemble_service import (
        EnsemblePredictorService,
    )

    return EnsemblePredictorService()


# ---------------------------------------------------------------------------
# Tests: Vehicle class logic
# ---------------------------------------------------------------------------


class TestVehicleClassLogic:
    def test_heavy_class_above_500(self):
        svc = _make_service()
        assert svc._get_vehicle_class({"tank_kapasitesi": 600}) == "heavy"

    def test_medium_class_200_to_500(self):
        svc = _make_service()
        assert svc._get_vehicle_class({"tank_kapasitesi": 300}) == "medium"

    def test_light_class_below_200(self):
        svc = _make_service()
        assert svc._get_vehicle_class({"tank_kapasitesi": 100}) == "light"

    def test_none_tank_defaults_to_light(self):
        svc = _make_service()
        assert svc._get_vehicle_class({"tank_kapasitesi": None}) == "light"

    def test_vehicle_class_model_id_heavy(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = _make_service()
        mid = svc._get_vehicle_class_model_id({"tank_kapasitesi": 600})
        assert mid == EnsemblePredictorService.VEHICLE_CLASS_MODEL_IDS["heavy"]


# ---------------------------------------------------------------------------
# Tests: _resolve_trip_date
# ---------------------------------------------------------------------------


class TestResolveTripDate:
    def test_date_object_returned_as_is(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        d = date(2025, 6, 1)
        assert EnsemblePredictorService._resolve_trip_date(d) == d

    def test_iso_string_parsed(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        result = EnsemblePredictorService._resolve_trip_date("2025-03-15")
        assert result == date(2025, 3, 15)

    def test_invalid_string_returns_today(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        result = EnsemblePredictorService._resolve_trip_date("not-a-date")
        assert result == date.today()

    def test_none_returns_today(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        result = EnsemblePredictorService._resolve_trip_date(None)
        assert result == date.today()


# ---------------------------------------------------------------------------
# Tests: _extract_route_analysis
# ---------------------------------------------------------------------------


class TestExtractRouteAnalysis:
    def test_none_if_no_rota_detay(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        assert EnsemblePredictorService._extract_route_analysis({}) is None

    def test_none_if_rota_detay_not_dict(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        assert (
            EnsemblePredictorService._extract_route_analysis({"rota_detay": "string"})
            is None
        )

    def test_extracts_nested_route_analysis(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        sefer = {"rota_detay": {"route_analysis": {"terrain": "mountainous"}}}
        result = EnsemblePredictorService._extract_route_analysis(sefer)
        assert result == {"terrain": "mountainous"}

    def test_falls_back_to_rota_detay_if_no_route_analysis_key(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        sefer = {"rota_detay": {"some_key": 1}}
        result = EnsemblePredictorService._extract_route_analysis(sefer)
        assert result == {"some_key": 1}


# ---------------------------------------------------------------------------
# Tests: _calculate_training_hash
# ---------------------------------------------------------------------------


class TestCalculateTrainingHash:
    def test_empty_returns_empty_string(self):
        svc = _make_service()
        assert svc._calculate_training_hash([]) == "empty"

    def test_hash_is_string(self):
        svc = _make_service()
        seferler = [{"id": i, "mesafe_km": 500, "ton": 20} for i in range(5)]
        result = svc._calculate_training_hash(seferler)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_different_data_gives_different_hash(self):
        svc = _make_service()
        s1 = [{"id": 1, "mesafe_km": 500, "ton": 20}]
        s2 = [{"id": 2, "mesafe_km": 800, "ton": 30}]
        assert svc._calculate_training_hash(s1) != svc._calculate_training_hash(s2)

    def test_same_data_gives_same_hash(self):
        svc = _make_service()
        seferler = [{"id": i, "mesafe_km": 400 + i, "ton": 20} for i in range(10)]
        h1 = svc._calculate_training_hash(seferler)
        h2 = svc._calculate_training_hash(seferler)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Tests: get_predictor (LRU cache)
# ---------------------------------------------------------------------------


class TestGetPredictor:
    def test_creates_new_predictor(self):
        svc = _make_service()
        p = svc.get_predictor(42)
        assert p is not None

    def test_returns_same_predictor_second_call(self):
        svc = _make_service()
        p1 = svc.get_predictor(42)
        p2 = svc.get_predictor(42)
        assert p1 is p2

    def test_lru_eviction_at_limit(self):
        svc = _make_service()
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
        svc = _make_service()
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
# Tests: predict_consumption (unit — mocked cross_module_client + predictor)
# ---------------------------------------------------------------------------


class TestPredictConsumption:
    @pytest.fixture
    def svc(self):
        return _make_service()

    async def test_returns_error_when_arac_not_found(self, svc):
        with patch(
            "prediction_ml_service.application.ensemble_service"
            ".cross_module_client.get_vehicle",
            AsyncMock(return_value=None),
        ):
            result = await svc.predict_consumption(arac_id=999, mesafe_km=500, ton=20)

        assert result["success"] is False
        assert "Araç" in result["error"]

    async def test_success_with_valid_arac(self, svc):
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

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".get_seasonal_factor",
                return_value=1.0,
            ),
        ):
            result = await svc.predict_consumption(arac_id=1, mesafe_km=500, ton=20)

        assert result["success"] is True
        assert "tahmin_l_100km" in result
        assert "tahmin_litre" in result

    async def test_fallback_to_class_model_when_vehicle_untrained(self, svc):
        arac = _make_arac(tank_kapasitesi=600)  # heavy

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

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".get_seasonal_factor",
                return_value=1.0,
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
        with patch(
            "prediction_ml_service.application.ensemble_service"
            ".cross_module_client.get_vehicle",
            AsyncMock(return_value=None),
        ):
            result = await svc.train_for_vehicle(arac_id=999)
        assert result["success"] is False

    async def test_returns_error_on_insufficient_trips(self, svc):
        with (
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_training_data",
                AsyncMock(return_value=[{"tuketim": 30}] * 5),
            ),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    async def test_enrichment_and_fit_called_with_sufficient_data(self, svc):
        """Test the enrichment loop + model.fit call path."""
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
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_training_data",
                AsyncMock(return_value=trips),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".get_seasonal_factor",
                return_value=1.05,
            ),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        # predictor.fit was called — the enrichment loop ran
        mock_predictor.fit.assert_called_once()
        # Result comes from the predictor's fit response
        assert result["success"] is False

    async def test_train_success_saves_model(self, svc):
        """Test the post-training save path when fit() succeeds."""
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

        mock_register = AsyncMock()

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_training_data",
                AsyncMock(return_value=trips),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".get_seasonal_factor",
                return_value=1.0,
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                "._register_model_version",
                mock_register,
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True
        mock_register.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: train_general_model
# ---------------------------------------------------------------------------


class TestTrainGeneralModel:
    @pytest.fixture
    def svc(self):
        return _make_service()

    async def test_returns_error_on_insufficient_data(self, svc):
        with patch(
            "prediction_ml_service.application.ensemble_service"
            ".cross_module_client.get_all_training_data",
            AsyncMock(return_value=[{"tuketim": 30}] * 5),
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

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_all_training_data",
                AsyncMock(return_value=trips),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                "._register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            result = await svc.train_general_model()

        assert result["success"] is True

    async def test_exception_in_train_returns_error(self, svc):
        with patch(
            "prediction_ml_service.application.ensemble_service"
            ".cross_module_client.get_all_training_data",
            AsyncMock(side_effect=RuntimeError("DB down")),
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

        requests = [{"arac_id": 1, "mesafe_km": 500, "ton": 20}]

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(
                "prediction_ml_service.application.ensemble_service"
                ".get_seasonal_factor",
                return_value=1.0,
            ),
        ):
            results = await svc.predict_batch(requests)

        assert len(results) == 1
        assert results[0]["success"] is True


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_ensemble_service_returns_instance(self):
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
            get_ensemble_service,
        )

        svc = get_ensemble_service()
        assert isinstance(svc, EnsemblePredictorService)

    def test_get_ensemble_service_same_instance(self):
        from prediction_ml_service.application.ensemble_service import (
            get_ensemble_service,
        )

        a = get_ensemble_service()
        b = get_ensemble_service()
        assert a is b
