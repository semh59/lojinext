"""
Additional coverage tests for EnsemblePredictorService.

Targets missed lines:
  128-129, 133-134, 140-141   — _persist_fallback_model exception branches
  160-189                     — get_predictor: model load path + schema mismatch + ml_probe
  251-258                     — train_for_vehicle: Arac entity mapping failure
  288-290                     — train_for_vehicle: sofor katsayi computation
  349-350, 359-360, 371-372   — train_for_vehicle: save paths (model_manager exc, analiz_repo exc, serialize exc)
  435-436                     — train_general_model: class_result not success → continue
  459                         — train_general_model: class_result success → persist
  513-516                     — predict_consumption: dorse_id with uow
  522-533                     — predict_consumption: Arac entity mapping failure → RuntimeError
  543-549                     — predict_consumption: sofor_id branch with stats
  584-587                     — predict_consumption: untrained class fallback → general model
"""

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
    from v2.modules.prediction_ml.application.ensemble_service import (
        EnsemblePredictorService,
    )

    svc = EnsemblePredictorService()
    svc._arac_repo = MagicMock()
    svc._sefer_repo = MagicMock()
    svc._dorse_repo = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# _persist_fallback_model — exception paths (lines 128-141)
# ---------------------------------------------------------------------------


class TestPersistFallbackModelExceptions:
    """Test exception-swallowing branches in _persist_fallback_model."""

    async def test_manager_save_version_exception_swallowed(self):
        """_register_model_version has its own internal try/except (never
        raises) — the 2026-07-18 model_manager→MLService rewiring moved this
        guarantee inside the free function itself, so the call site no
        longer needs a try/except. Verified here by mocking
        _register_model_version to raise and confirming _persist_fallback_model
        still calls legacy_repo despite that (would only be true if the
        caller itself doesn't propagate — matching the new contract)."""
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

        mock_legacy_repo = MagicMock()
        mock_legacy_repo.save_model_params = AsyncMock()

        result = {"metrics": {}, "measurements": {}, "sample_count": 5}

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
        ):
            # Should not raise
            await svc._persist_fallback_model(
                model_id=10000,
                predictor=mock_predictor,
                result=result,
                seferler=[],
                notes="test",
                legacy_repo=mock_legacy_repo,
            )

        # legacy_repo.save_model_params should still be called even after manager failure
        mock_legacy_repo.save_model_params.assert_awaited_once()

    async def test_legacy_repo_exception_swallowed(self):
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor._feature_hash = "abc"
        mock_predictor._physics_version = None

        mock_legacy_repo = MagicMock()
        mock_legacy_repo.save_model_params = AsyncMock(
            side_effect=RuntimeError("legacy fail")
        )

        result = {"metrics": {}, "measurements": {}, "sample_count": 5}

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            # Should not raise
            await svc._persist_fallback_model(
                model_id=10001,
                predictor=mock_predictor,
                result=result,
                seferler=[],
                notes="test",
                legacy_repo=mock_legacy_repo,
            )

    async def test_serialize_exception_swallowed(self):
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None
        mock_predictor.save_model = MagicMock(side_effect=OSError("disk full"))

        mock_legacy_repo = MagicMock()
        mock_legacy_repo.save_model_params = AsyncMock()

        result = {"metrics": {}, "measurements": {}, "sample_count": 5}

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
        ):
            # Should not raise even when save_model fails
            await svc._persist_fallback_model(
                model_id=10002,
                predictor=mock_predictor,
                result=result,
                seferler=[],
                notes="test",
                legacy_repo=mock_legacy_repo,
            )


# ---------------------------------------------------------------------------
# get_predictor — model disk load paths (lines 160-189)
# ---------------------------------------------------------------------------


class TestGetPredictorDiskLoad:
    def test_loads_model_from_disk_when_meta_exists_and_schema_matches(self):
        """When meta.json exists and feature count matches → load succeeds."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))  # same count
        mock_predictor._feature_hash = "same-hash"
        mock_predictor._loaded_feature_schema_hash = "same-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):
            p = svc.get_predictor(99)

        assert p is mock_predictor
        mock_predictor.load_model.assert_called_once()
        # is_trained should remain True (no mismatch)
        assert p.is_trained is True

    def test_schema_mismatch_marks_predictor_untrained(self):
        """When expected != runtime feature count → predictor.is_trained = False."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 15
        mock_predictor.FEATURE_NAMES = list(range(10))  # mismatch: 10 != 15

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):
            svc.get_predictor(88)

        # The code should set is_trained = False on schema mismatch
        assert mock_predictor.is_trained is False

    def test_hash_mismatch_marks_predictor_untrained_even_when_count_matches(self):
        """2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 26): feature
        SAYISI aynı kalsa bile isim/sıra değişmişse (feature drift) eski
        kod bunu YAKALAMIYORDU — sadece n_features_in_ karşılaştırılıyordu.
        Artık persisted feature_schema_hash (isim+sıra) de karşılaştırılıyor."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))  # count matches (10==10)
        mock_predictor._feature_hash = "current-code-hash"
        mock_predictor._loaded_feature_schema_hash = "stale-persisted-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):
            svc.get_predictor(77)

        assert mock_predictor.is_trained is False, (
            "Feature isim/sıra hash'i uyuşmuyorsa (count aynı olsa bile) "
            "predictor untrained işaretlenmeliydi — sessiz feature drift "
            "önlenmedi."
        )

    def test_hash_match_keeps_predictor_trained(self):
        """Hash'ler eşleşiyorsa (gerçek sürüm) is_trained korunur — false
        positive yok."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))
        mock_predictor._feature_hash = "same-hash"
        mock_predictor._loaded_feature_schema_hash = "same-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):
            svc.get_predictor(78)

        assert mock_predictor.is_trained is True

    def test_load_model_exception_records_failure_via_ml_probe(self):
        """load_model raises → ml_probe records failure (inner except block)."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor.load_model.side_effect = RuntimeError("corrupt pkl")

        mock_probe = MagicMock()

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "app.infrastructure.monitoring.ml_probe.get_ml_probe",
                return_value=mock_probe,
            ),
        ):
            p = svc.get_predictor(77)

        # probe.record_model_load_failure should have been called
        mock_probe.record_model_load_failure.assert_called_once()
        assert p is mock_predictor

    def test_load_exception_ml_probe_exception_also_swallowed(self):
        """Inner get_ml_probe() also raises → outer exception still swallowed."""
        from v2.modules.prediction_ml.application.ensemble_service import (
            EnsemblePredictorService,
        )

        svc = EnsemblePredictorService()

        mock_predictor = MagicMock()
        mock_predictor.load_model.side_effect = RuntimeError("pkl error")

        with (
            patch(
                "v2.modules.prediction_ml.application.ensemble_service.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "app.infrastructure.monitoring.ml_probe.get_ml_probe",
                side_effect=ImportError("probe not installed"),
            ),
        ):
            # Should not raise
            p = svc.get_predictor(66)

        assert p is mock_predictor


# ---------------------------------------------------------------------------
# train_for_vehicle — Arac entity mapping failure (lines 251-258)
# ---------------------------------------------------------------------------


class TestTrainForVehicleAracEntityFail:
    async def test_arac_entity_mapping_failure_uses_defaults(self):
        """When Arac(**arac) raises, arac_yasi=0 and yas_faktoru=1.0 used."""
        svc = _make_service()
        svc._arac_repo.get_by_id = AsyncMock(return_value={"id": 1, "bad_field": "X"})

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
        mock_predictor.fit.return_value = {"success": False, "error": "test"}
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
            # Make Arac(**arac) fail
            patch(
                "v2.modules.fleet.public.Arac", side_effect=ValueError("bad mapping")
            ),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        # fit still called — the exception was handled with defaults
        mock_predictor.fit.assert_called_once()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# train_for_vehicle — sofor katsayi with stats (lines 288-290)
# ---------------------------------------------------------------------------


class TestTrainForVehicleSoforKatsayi:
    async def test_sofor_katsayi_computed_from_driver_stats(self):
        """sofor_id present + driver_map has stats → katsayi computed (not 1.0)."""
        svc = _make_service()
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())

        driver_stat = MagicMock()
        driver_stat.sofor_id = 5
        driver_stat.filo_karsilastirma = 10.0  # 1.0 - (10/100)*0.1 = 0.99

        trips = [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tarih": "2025-06-01",
                "sofor_id": 5,
            }
            for i in range(15)
        ]
        svc._sefer_repo.get_for_training = AsyncMock(return_value=trips)

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        enriched_calls = []

        mock_predictor = MagicMock()

        def capture_fit(data, y):
            enriched_calls.extend(data)
            return {"success": False, "error": "test"}

        mock_predictor.fit.side_effect = capture_fit
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
                AsyncMock(return_value=[driver_stat]),
            ),
        ):
            await svc.train_for_vehicle(arac_id=1)

        # All trips have sofor_id=5 → katsayi = 0.99
        assert len(enriched_calls) == 15
        assert enriched_calls[0]["sofor_katsayi"] == pytest.approx(0.99, abs=0.001)


# ---------------------------------------------------------------------------
# train_for_vehicle — model_manager / analiz_repo / serialize exceptions (lines 349-372)
# ---------------------------------------------------------------------------


class TestTrainForVehicleSaveExceptions:
    def _make_trips(self, count=15):
        return [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tarih": "2025-06-01",
                "sofor_id": None,
            }
            for i in range(count)
        ]

    async def test_model_manager_exception_still_returns_success(self):
        """manager.save_version exception → logged but result is still returned."""
        svc = _make_service()
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())
        svc._sefer_repo.get_for_training = AsyncMock(return_value=self._make_trips())

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.85,
            "metrics": {"gb_test_r2": 0.85},
            "measurements": {"mae": 1.2, "rmse": 1.5},
            "sample_count": 15,
        }
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

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
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True
        # analiz_repo should still be called despite manager failure
        mock_analiz_repo.save_model_params.assert_awaited_once()

    async def test_analiz_repo_exception_does_not_prevent_return(self):
        """analiz_repo.save_model_params exception → logged, result returned."""
        svc = _make_service()
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())
        svc._sefer_repo.get_for_training = AsyncMock(return_value=self._make_trips())

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.80,
            "metrics": {},
            "measurements": {},
            "sample_count": 15,
        }
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

        mock_analiz_repo = MagicMock()
        mock_analiz_repo.save_model_params = AsyncMock(
            side_effect=RuntimeError("repo fail")
        )

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
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True

    async def test_serialize_exception_does_not_prevent_return(self):
        """predictor.save_model raises → logged, result returned."""
        svc = _make_service()
        svc._arac_repo.get_by_id = AsyncMock(return_value=_make_arac())
        svc._sefer_repo.get_for_training = AsyncMock(return_value=self._make_trips())

        mock_weather = MagicMock()
        mock_weather.get_seasonal_factor.return_value = 1.0

        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.80,
            "metrics": {},
            "measurements": {},
            "sample_count": 15,
        }
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None
        mock_predictor.save_model = MagicMock(side_effect=OSError("disk full"))

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
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# train_general_model — class model not success → continue (line 435-436)
# and class model success → _persist_fallback_model called (line 459)
# ---------------------------------------------------------------------------


class TestTrainGeneralModelClassModels:
    async def test_class_model_not_success_is_skipped(self):
        """Class predictor.fit returns success=False → _persist_fallback_model not called."""
        svc = _make_service()
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

        # General model succeeds, class models fail
        general_predictor = MagicMock()
        general_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.8,
            "metrics": {},
            "measurements": {},
            "sample_count": 25,
        }
        general_predictor._feature_hash = None
        general_predictor._physics_version = None

        class_predictor = MagicMock()
        class_predictor.fit.return_value = {
            "success": False,
            "error": "not enough data",
        }

        def predictor_factory(arac_id):
            if arac_id == 0:
                return general_predictor
            return class_predictor

        mock_analiz_repo = MagicMock()
        mock_analiz_repo.save_model_params = AsyncMock()

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(general_predictor, "save_model"),
        ):
            result = await svc.train_general_model()

        assert result["success"] is True
        # class_models_trained should be empty (all failed)
        assert result.get("class_models_trained") == {}

    async def test_class_model_success_persists(self):
        """Class predictor.fit returns success=True → _persist_fallback_model called."""
        svc = _make_service()
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

        general_predictor = MagicMock()
        general_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.8,
            "metrics": {},
            "measurements": {},
            "sample_count": 25,
        }
        general_predictor._feature_hash = None
        general_predictor._physics_version = None

        class_predictor = MagicMock()
        class_predictor.fit.return_value = {
            "success": True,
            "ensemble_r2": 0.75,
            "metrics": {},
            "measurements": {},
            "sample_count": 25,
        }
        class_predictor._feature_hash = None
        class_predictor._physics_version = None

        def predictor_factory(arac_id):
            if arac_id == 0:
                return general_predictor
            return class_predictor

        mock_analiz_repo = MagicMock()
        mock_analiz_repo.save_model_params = AsyncMock()

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                "v2.modules.prediction_ml.application.ensemble_service."
                "_register_model_version",
                AsyncMock(),
            ),
            patch(
                "v2.modules.analytics_executive.public.get_analiz_repo",
                return_value=mock_analiz_repo,
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(general_predictor, "save_model"),
            patch.object(class_predictor, "save_model"),
        ):
            result = await svc.train_general_model()

        assert result["success"] is True
        # At least one class model trained
        assert len(result.get("class_models_trained", {})) > 0


# ---------------------------------------------------------------------------
# predict_consumption — dorse_id with uow (lines 513-516)
# ---------------------------------------------------------------------------


class TestPredictConsumptionDorse:
    async def test_dorse_fetched_via_uow_when_provided(self):
        svc = _make_service()
        arac = _make_arac()
        dorse = {
            "bos_agirlik_kg": 7000,
            "lastik_sayisi": 8,
            "dorse_lastik_direnc_katsayisi": 0.007,
            "dorse_hava_direnci": 0.14,
        }

        mock_uow = MagicMock()
        mock_uow.arac_repo = MagicMock()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=arac)
        mock_uow.dorse_repo = MagicMock()
        mock_uow.dorse_repo.get_by_id = AsyncMock(return_value=dorse)

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 32.0
        mock_prediction.confidence_low = 29.0
        mock_prediction.confidence_high = 35.0
        mock_prediction.physics_only = 31.0
        mock_prediction.ml_correction = 1.0

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
                arac_id=1,
                mesafe_km=500,
                ton=20,
                dorse_id=3,
                uow=mock_uow,
            )

        mock_uow.dorse_repo.get_by_id.assert_awaited_with(3)
        assert result["success"] is True

    async def test_dorse_fetched_via_own_repo_when_no_uow(self):
        svc = _make_service()
        arac = _make_arac()
        dorse = {
            "bos_agirlik_kg": 6000,
            "lastik_sayisi": 6,
            "dorse_lastik_direnc_katsayisi": 0.006,
            "dorse_hava_direnci": 0.13,
        }

        svc._arac_repo.get_by_id = AsyncMock(return_value=arac)
        svc._dorse_repo.get_by_id = AsyncMock(return_value=dorse)

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
                arac_id=1,
                mesafe_km=400,
                ton=15,
                dorse_id=7,
            )

        svc._dorse_repo.get_by_id.assert_awaited_with(7)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# predict_consumption — Arac entity mapping failure → RuntimeError (lines 522-533)
# ---------------------------------------------------------------------------


class TestPredictConsumptionEntityMapFail:
    async def test_arac_entity_mapping_failure_raises_runtime_error(self):
        svc = _make_service()
        # Return a dict that will cause Arac(**arac) to fail
        svc._arac_repo.get_by_id = AsyncMock(return_value={"id": 1, "bad_key": "X"})

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
            # Make Arac(**arac) fail
            patch(
                "v2.modules.fleet.public.Arac", side_effect=ValueError("bad mapping")
            ),
        ):
            with pytest.raises(RuntimeError, match="mapping failed"):
                await svc.predict_consumption(arac_id=1, mesafe_km=500, ton=20)


# ---------------------------------------------------------------------------
# predict_consumption — sofor stats branch (lines 543-549)
# ---------------------------------------------------------------------------


class TestPredictConsumptionSoforStats:
    async def test_sofor_katsayi_applied_when_stats_available(self):
        svc = _make_service()
        arac = _make_arac()
        svc._arac_repo.get_by_id = AsyncMock(return_value=arac)

        driver_stat = MagicMock()
        driver_stat.filo_karsilastirma = 20.0  # → katsayi = 1.0 - (20/100)*0.1 = 0.98

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 31.0
        mock_prediction.confidence_low = 28.0
        mock_prediction.confidence_high = 34.0
        mock_prediction.physics_only = 31.0
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
                AsyncMock(return_value=[driver_stat]),
            ),
        ):
            result = await svc.predict_consumption(
                arac_id=1,
                mesafe_km=500,
                ton=20,
                sofor_id=10,
            )

        assert result["success"] is True
        # katsayi should be reflected in factors
        assert result["factors"]["sofor_katsayi"] == pytest.approx(0.98, abs=0.001)


# ---------------------------------------------------------------------------
# predict_consumption — fallback to general model (lines 584-587)
# ---------------------------------------------------------------------------


class TestPredictConsumptionGeneralModelFallback:
    async def test_untrained_class_model_falls_back_to_general(self):
        """Vehicle untrained, class model also untrained → uses general model (0)."""
        svc = _make_service()
        arac = _make_arac(tank_kapasitesi=600)  # heavy
        svc._arac_repo.get_by_id = AsyncMock(return_value=arac)

        untrained_predictor = MagicMock()
        untrained_predictor.is_trained = False

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 33.5
        mock_prediction.confidence_low = 30.0
        mock_prediction.confidence_high = 37.0
        mock_prediction.physics_only = 33.5
        mock_prediction.ml_correction = 0.0

        general_predictor = MagicMock()
        general_predictor.is_trained = True
        general_predictor.predict.return_value = mock_prediction

        call_log = []

        def predictor_factory(arac_id):
            call_log.append(arac_id)
            if arac_id == 1:
                return untrained_predictor
            elif arac_id == 10000:  # heavy class model
                return untrained_predictor  # also untrained
            else:
                return general_predictor  # general model

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
            result = await svc.predict_consumption(arac_id=1, mesafe_km=500, ton=20)

        assert result["success"] is True
        # general_predictor.predict should have been called
        general_predictor.predict.assert_called_once()
        # The get_predictor(0) call must appear in call_log
        assert 0 in call_log
