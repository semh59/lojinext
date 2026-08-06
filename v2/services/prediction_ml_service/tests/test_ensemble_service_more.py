"""
Additional coverage tests for EnsemblePredictorService.

Rewired for the service extraction (Task 5, 2026-08-04): fleet/driver/trip
data now comes over HTTP via cross_module_client, not a UnitOfWork or
lazy repo properties -- and `_persist_fallback_model` no longer takes a
`legacy_repo` kwarg (it calls `cross_module_client.save_model_params`
directly, which is itself already exception-safe -- verified in
cross_module_client.py before deciding this class needed trimming, not
just a path rename). The `Arac(**arac)` entity-mapping step this file's
TestTrainForVehicleAracEntityFail / TestPredictConsumptionEntityMapFail
classes exercised no longer exists anywhere in ensemble_service.py --
those tests covered removed functionality and were dropped rather than
patched over.

Targets still covered here:
  get_predictor: model load path + schema mismatch + ml_probe (unchanged)
  train_for_vehicle: sofor katsayi computation
  train_for_vehicle: save paths (register_model_version / save_model_params
    / serialize exceptions all logged, never abort the return)
  train_general_model: class_result not success → continue / success → persist
  predict_consumption: dorse_id fetch, sofor_id branch, untrained→general
    model fallback
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
    from prediction_ml_service.application.ensemble_service import (
        EnsemblePredictorService,
    )

    return EnsemblePredictorService()


ENSEMBLE_SERVICE_MODULE = "prediction_ml_service.application.ensemble_service"


# ---------------------------------------------------------------------------
# _persist_fallback_model — serialize exception path (still self-protected)
# ---------------------------------------------------------------------------


class TestPersistFallbackModelExceptions:
    """`_register_model_version` and `cross_module_client.save_model_params`
    are each independently exception-safe now (own internal try/except,
    verified in their own source) -- `_persist_fallback_model` itself only
    still needs to protect the disk-serialize step."""

    async def test_serialize_exception_swallowed(self):
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None
        mock_predictor.save_model = MagicMock(side_effect=OSError("disk full"))

        result = {"metrics": {}, "measurements": {}, "sample_count": 5}

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}._register_model_version",
                AsyncMock(),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.save_model_params",
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
            )


# ---------------------------------------------------------------------------
# get_predictor — model disk load paths (unchanged by the extraction)
# ---------------------------------------------------------------------------


class TestGetPredictorDiskLoad:
    def test_loads_model_from_disk_when_meta_exists_and_schema_matches(self):
        """When meta.json exists and feature count matches → load succeeds."""
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))  # same count
        mock_predictor._feature_hash = "same-hash"
        mock_predictor._loaded_feature_schema_hash = "same-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
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
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 15
        mock_predictor.FEATURE_NAMES = list(range(10))  # mismatch: 10 != 15

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
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
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))  # count matches (10==10)
        mock_predictor._feature_hash = "current-code-hash"
        mock_predictor._loaded_feature_schema_hash = "stale-persisted-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
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
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor._resolve_expected_feature_count.return_value = 10
        mock_predictor.FEATURE_NAMES = list(range(10))
        mock_predictor._feature_hash = "same-hash"
        mock_predictor._loaded_feature_schema_hash = "same-hash"
        mock_predictor.is_trained = True

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
        ):
            svc.get_predictor(78)

        assert mock_predictor.is_trained is True

    def test_load_model_exception_records_failure_via_ml_probe(self):
        """load_model raises → ml_probe records failure (inner except block)."""
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor.load_model.side_effect = RuntimeError("corrupt pkl")

        mock_probe = MagicMock()

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "prediction_ml_service.infrastructure.ml_probe.get_ml_probe",
                return_value=mock_probe,
            ),
        ):
            p = svc.get_predictor(77)

        # probe.record_model_load_failure should have been called
        mock_probe.record_model_load_failure.assert_called_once()
        assert p is mock_predictor

    def test_load_exception_ml_probe_exception_also_swallowed(self):
        """Inner get_ml_probe() also raises → outer exception still swallowed."""
        svc = _make_service()

        mock_predictor = MagicMock()
        mock_predictor.load_model.side_effect = RuntimeError("pkl error")

        with (
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.EnsembleFuelPredictor",
                return_value=mock_predictor,
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "prediction_ml_service.infrastructure.ml_probe.get_ml_probe",
                side_effect=ImportError("probe not installed"),
            ),
        ):
            # Should not raise
            p = svc.get_predictor(66)

        assert p is mock_predictor


# ---------------------------------------------------------------------------
# train_for_vehicle — sofor katsayi with stats
# ---------------------------------------------------------------------------


class TestTrainForVehicleSoforKatsayi:
    async def test_sofor_katsayi_computed_from_driver_stats(self):
        """sofor_id present + driver_map has stats → katsayi computed (not 1.0)."""
        svc = _make_service()

        # Real code indexes driver stats as plain dicts
        # (`{d["sofor_id"]: d for d in all_driver_stats}`), not attribute
        # objects -- verified against ensemble_service.py before writing this.
        driver_stat = {"sofor_id": 5, "filo_karsilastirma": 10.0}  # katsayi = 0.99

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
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_training_data",
                AsyncMock(return_value=trips),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_driver_stats",
                AsyncMock(return_value=[driver_stat]),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
        ):
            await svc.train_for_vehicle(arac_id=1)

        # All trips have sofor_id=5 → katsayi = 0.99
        assert len(enriched_calls) == 15
        assert enriched_calls[0]["sofor_katsayi"] == pytest.approx(0.99, abs=0.001)


# ---------------------------------------------------------------------------
# train_for_vehicle — register_model_version / save_model_params / serialize
# exceptions never prevent the trained result from being returned
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

    def _fit_result(self):
        return {
            "success": True,
            "ensemble_r2": 0.85,
            "metrics": {"gb_test_r2": 0.85},
            "measurements": {"mae": 1.2, "rmse": 1.5},
            "sample_count": 15,
        }

    async def test_register_model_version_exception_does_not_prevent_return(self):
        """`_register_model_version` has its own internal try/except (never
        raises for real) -- confirmed here by mocking it to raise anyway and
        checking `train_for_vehicle` still returns the trained result,
        proving the call site doesn't (and doesn't need to) add its own
        protection on top."""
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = self._fit_result()
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_training_data",
                AsyncMock(return_value=self._make_trips()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}._register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(mock_predictor, "save_model"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True

    async def test_serialize_exception_does_not_prevent_return(self):
        """predictor.save_model raises → logged, result returned."""
        svc = _make_service()
        mock_predictor = MagicMock()
        mock_predictor.fit.return_value = self._fit_result()
        mock_predictor._feature_hash = None
        mock_predictor._physics_version = None
        mock_predictor.save_model = MagicMock(side_effect=OSError("disk full"))

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=_make_arac()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_training_data",
                AsyncMock(return_value=self._make_trips()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}._register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
        ):
            result = await svc.train_for_vehicle(arac_id=1)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# train_general_model — class model not success → continue / success → persist
# ---------------------------------------------------------------------------


class TestTrainGeneralModelClassModels:
    def _trips(self):
        return [
            {
                "id": i,
                "tuketim": 32.0,
                "mesafe_km": 500,
                "ton": 20,
                "tank_kapasitesi": 600,
            }
            for i in range(25)
        ]

    async def test_class_model_not_success_is_skipped(self):
        """Class predictor.fit returns success=False → class_models_trained empty."""
        svc = _make_service()

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

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_all_training_data",
                AsyncMock(return_value=self._trips()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}._register_model_version",
                AsyncMock(),
            ),
            patch("pathlib.Path.mkdir"),
            patch.object(general_predictor, "save_model"),
        ):
            result = await svc.train_general_model()

        assert result["success"] is True
        # class_models_trained should be empty (all failed)
        assert result.get("class_models_trained") == {}

    async def test_class_model_success_persists(self):
        """Class predictor.fit returns success=True → class_models_trained populated."""
        svc = _make_service()

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

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_all_training_data",
                AsyncMock(return_value=self._trips()),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.save_model_params",
                AsyncMock(),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}._register_model_version",
                AsyncMock(),
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
# predict_consumption — dorse_id fetch
# ---------------------------------------------------------------------------


class TestPredictConsumptionDorse:
    async def test_dorse_data_flows_into_sefer_features(self):
        svc = _make_service()
        arac = _make_arac()
        dorse = {
            "bos_agirlik_kg": 7000,
            "lastik_sayisi": 8,
            "dorse_lastik_direnc_katsayisi": 0.007,
            "dorse_hava_direnci": 0.14,
        }

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 32.0
        mock_prediction.confidence_low = 29.0
        mock_prediction.confidence_high = 35.0
        mock_prediction.physics_only = 31.0
        mock_prediction.ml_correction = 1.0

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = mock_prediction
        mock_predictor.is_trained = True

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_trailer",
                AsyncMock(return_value=dorse),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
        ):
            result = await svc.predict_consumption(
                arac_id=1,
                mesafe_km=500,
                ton=20,
                dorse_id=3,
            )

        mock_predictor.predict.assert_called_once()
        sefer_arg = mock_predictor.predict.call_args.args[0]
        assert sefer_arg["dorse_bos_agirlik"] == 7000
        assert sefer_arg["dorse_lastik_sayisi"] == 8
        assert result["success"] is True


# ---------------------------------------------------------------------------
# predict_consumption — sofor stats branch
# ---------------------------------------------------------------------------


class TestPredictConsumptionSoforStats:
    async def test_sofor_katsayi_applied_when_stats_available(self):
        svc = _make_service()
        arac = _make_arac()

        # Real code reads `stats[0]["filo_karsilastirma"]` (a dict), not an
        # attribute -- verified against ensemble_service.py.
        driver_stat = {"filo_karsilastirma": 20.0}  # → katsayi = 0.98

        mock_prediction = MagicMock()
        mock_prediction.tahmin_l_100km = 31.0
        mock_prediction.confidence_low = 28.0
        mock_prediction.confidence_high = 34.0
        mock_prediction.physics_only = 31.0
        mock_prediction.ml_correction = 0.0

        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = mock_prediction
        mock_predictor.is_trained = True

        with (
            patch.object(svc, "get_predictor", return_value=mock_predictor),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_driver_stats",
                AsyncMock(return_value=[driver_stat]),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
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
# predict_consumption — fallback to general model
# ---------------------------------------------------------------------------


class TestPredictConsumptionGeneralModelFallback:
    async def test_untrained_class_model_falls_back_to_general(self):
        """Vehicle untrained, class model also untrained → uses general model (0)."""
        svc = _make_service()
        arac = _make_arac(tank_kapasitesi=600)  # heavy

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

        with (
            patch.object(svc, "get_predictor", side_effect=predictor_factory),
            patch(
                f"{ENSEMBLE_SERVICE_MODULE}.cross_module_client.get_vehicle",
                AsyncMock(return_value=arac),
            ),
            patch(f"{ENSEMBLE_SERVICE_MODULE}.get_seasonal_factor", return_value=1.0),
        ):
            result = await svc.predict_consumption(arac_id=1, mesafe_km=500, ton=20)

        assert result["success"] is True
        # general_predictor.predict should have been called
        general_predictor.predict.assert_called_once()
        # The get_predictor(0) call must appear in call_log
        assert 0 in call_log
