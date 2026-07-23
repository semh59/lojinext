"""
Unit tests for EnsembleFuelPredictor (ensemble_core.py) and related structures.

Mocks:
- Heavy sklearn/xgboost/lightgbm models are NOT mocked at import; they are
  optional — the class degrades gracefully if they are missing.
- Only joblib.load/dump and file-system calls are patched where needed.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sefer(
    mesafe_km=500.0,
    ton=20.0,
    ascent_m=800,
    descent_m=700,
    tuketim=32.0,
    tarih="2025-01-15",
    **kwargs,
):
    base = dict(
        mesafe_km=mesafe_km,
        ton=ton,
        ascent_m=ascent_m,
        descent_m=descent_m,
        flat_distance_km=300.0,
        tuketim=tuketim,
        tarih=tarih,
        zorluk="Normal",
        arac_yasi=5,
        yas_faktoru=1.0,
        mevsim_faktor=1.0,
        sofor_katsayi=1.0,
    )
    base.update(kwargs)
    return base


def _training_batch(n=15, base_tuketim=32.0):
    """Return n sefer dicts suitable for .fit()."""
    return [
        _make_sefer(
            mesafe_km=400 + i * 10,
            ton=18 + (i % 5),
            tuketim=base_tuketim + (i % 3),
            tarih=f"2025-{(i % 12) + 1:02d}-15",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnsemblePredictorInit:
    def test_basic_initialization(self):
        """EnsembleFuelPredictor instantiates with default args."""
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        assert predictor is not None
        assert predictor.is_trained is False
        assert "physics" in predictor.weights
        assert predictor.weights["physics"] == 0.80

    def test_default_weights_sum_to_one(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        total = sum(predictor.DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_feature_names_match_prepare_output(self):
        """prepare_features must return exactly len(FEATURE_NAMES) columns."""
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        seferler = [_make_sefer()]
        X = predictor.prepare_features(seferler)
        assert X.shape == (1, len(predictor.FEATURE_NAMES))


class TestEnsemblePredictorPhysicsFallback:
    def test_predict_before_training_returns_physics_fallback(self):
        """Before fit(), predict() must still return a valid PredictionResult."""
        from v2.modules.prediction_ml.domain.ensemble_core import (
            EnsembleFuelPredictor,
            PredictionResult,
        )

        predictor = EnsembleFuelPredictor()
        result = predictor.predict(_make_sefer())

        assert isinstance(result, PredictionResult)
        assert result.tahmin_l_100km > 0
        assert result.physics_weight == 1.0
        assert result.ml_correction == 0.0

    def test_predict_zero_mesafe_uses_default_100(self):
        """mesafe_km=0 triggers auto-correction to 100 km."""
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        result = predictor.predict(_make_sefer(mesafe_km=0))
        assert result.tahmin_l_100km > 0

    def test_predict_negative_mesafe_uses_default_100(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        result = predictor.predict(_make_sefer(mesafe_km=-50))
        assert result.tahmin_l_100km > 0

    def test_predict_empty_trip_reduces_consumption(self):
        """Empty trip (no cargo) should produce lower L/100km than loaded."""
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        loaded = predictor.predict(_make_sefer(ton=25, is_empty_trip=False))
        empty = predictor.predict(_make_sefer(ton=25, is_empty_trip=True))
        assert empty.tahmin_l_100km < loaded.tahmin_l_100km


class TestEnsemblePredictorFit:
    def test_fit_insufficient_data_returns_error(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        result = predictor.fit([_make_sefer()] * 5)  # less than 10
        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    def test_fit_success_sets_is_trained(self):
        from v2.modules.prediction_ml.domain.ensemble_core import (
            SKLEARN_AVAILABLE,
            EnsembleFuelPredictor,
        )

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not installed")

        predictor = EnsembleFuelPredictor()
        batch = _training_batch(20)
        result = predictor.fit(batch)
        assert result["success"] is True
        assert predictor.is_trained is True

    def test_fit_result_contains_expected_keys(self):
        from v2.modules.prediction_ml.domain.ensemble_core import (
            SKLEARN_AVAILABLE,
            EnsembleFuelPredictor,
        )

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not installed")

        predictor = EnsembleFuelPredictor()
        result = predictor.fit(_training_batch(20))
        assert "success" in result
        if result["success"]:
            assert "sample_count" in result
            assert "model_weights" in result

    def test_fit_all_zero_tuketim_returns_error(self):
        """All zero consumption labels must trigger label-leak guard → success=False."""
        from v2.modules.prediction_ml.domain.ensemble_core import (
            SKLEARN_AVAILABLE,
            EnsembleFuelPredictor,
        )

        if not SKLEARN_AVAILABLE:
            pytest.skip("sklearn not installed")

        predictor = EnsembleFuelPredictor()
        batch = [_make_sefer(tuketim=0) for _ in range(15)]
        result = predictor.fit(batch)
        assert result["success"] is False


class TestPredictionResult:
    def test_prediction_result_fields(self):
        from v2.modules.prediction_ml.domain.ensemble_core import PredictionResult

        pr = PredictionResult(
            tahmin_l_100km=32.5,
            physics_only=30.0,
            ml_correction=2.5,
            confidence_low=29.0,
            confidence_high=36.0,
            physics_weight=0.8,
            features_used={"ton": 20},
        )
        assert pr.tahmin_l_100km == 32.5
        assert pr.confidence_high > pr.confidence_low

    def test_security_error_is_exception(self):
        from v2.modules.prediction_ml.domain.ensemble_core import SecurityError

        with pytest.raises(SecurityError):
            raise SecurityError("test")


class TestPrepareFeatures:
    def test_multiple_seferler(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        batch = [_make_sefer() for _ in range(5)]
        X = predictor.prepare_features(batch)
        assert X.shape[0] == 5
        assert X.shape[1] == len(predictor.FEATURE_NAMES)

    def test_features_no_nan(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        X = predictor.prepare_features([_make_sefer(mesafe_km=1)])
        assert not np.any(np.isnan(X))

    def test_feature_names_length(self):
        from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()
        assert len(predictor.FEATURE_NAMES) > 0
