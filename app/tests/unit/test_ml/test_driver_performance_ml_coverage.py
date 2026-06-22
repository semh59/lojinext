"""
Coverage tests for DriverPerformanceML (driver_performance_ml.py).
Uses LightGBM if available; gracefully skips deep training tests when absent.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver_stats(**overrides):
    base = {
        "toplam_sefer": 50,
        "toplam_km": 25000,
        "ort_tuketim": 32.5,
        "filo_karsilastirma": -5.0,
        "en_iyi_tuketim": 28.0,
        "en_kotu_tuketim": 38.0,
        "trend": "stable",
        "guzergah_sayisi": 8,
        "bos_sefer_sayisi": 5,
        "toplam_ton": 600000,
    }
    base.update(overrides)
    return base


def _make_driver_list(n=10, **overrides):
    return [_make_driver_stats(toplam_sefer=10 + i, **overrides) for i in range(n)]


def _fresh_model():
    from app.core.ml.driver_performance_ml import DriverPerformanceML

    return DriverPerformanceML()


# ---------------------------------------------------------------------------
# Tests: initialization
# ---------------------------------------------------------------------------


class TestDriverPerformanceMLInit:
    def test_init_creates_instance(self):
        model = _fresh_model()
        assert model is not None

    def test_is_not_trained_initially(self):
        model = _fresh_model()
        assert model.is_trained is False

    def test_ranker_not_trained_initially(self):
        model = _fresh_model()
        assert model.ranker_trained is False

    def test_feature_importance_empty(self):
        model = _fresh_model()
        assert model.feature_importance == {}


# ---------------------------------------------------------------------------
# Tests: prepare_features
# ---------------------------------------------------------------------------


class TestPrepareFeatures:
    def test_returns_numpy_array(self):
        model = _fresh_model()
        X = model.prepare_features(_make_driver_list(5))
        assert isinstance(X, np.ndarray)

    def test_shape_is_correct(self):
        model = _fresh_model()
        drivers = _make_driver_list(7)
        X = model.prepare_features(drivers)
        assert X.shape == (7, len(model.FEATURE_NAMES))

    def test_no_nan_in_features(self):
        model = _fresh_model()
        X = model.prepare_features(_make_driver_list(5))
        assert not np.any(np.isnan(X))

    def test_no_inf_in_features(self):
        model = _fresh_model()
        X = model.prepare_features(_make_driver_list(5))
        assert not np.any(np.isinf(X))

    def test_zero_sefer_bos_sefer_orani_is_zero(self):
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(toplam_sefer=0)])
        # bos_sefer_orani is index 7
        assert X[0, 7] == 0.0

    def test_zero_km_ton_per_km_is_zero(self):
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(toplam_km=0)])
        # ton_per_km is index 9
        assert X[0, 9] == 0.0

    def test_improving_trend_encodes_as_1(self):
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(trend="improving")])
        # trend_encoded is index 5
        assert X[0, 5] == 1.0

    def test_declining_trend_encodes_as_minus_1(self):
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(trend="declining")])
        assert X[0, 5] == -1.0

    def test_stable_trend_encodes_as_zero(self):
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(trend="stable")])
        assert X[0, 5] == 0.0

    def test_safe_division_when_ort_tuketim_zero(self):
        """tuketim_tutarliligi should not raise ZeroDivisionError when ort_tuketim=0."""
        model = _fresh_model()
        X = model.prepare_features([_make_driver_stats(ort_tuketim=0)])
        assert not np.any(np.isinf(X))

    def test_none_values_handled_gracefully(self):
        model = _fresh_model()
        stats = {
            "toplam_sefer": None,
            "toplam_km": None,
            "ort_tuketim": None,
            "filo_karsilastirma": None,
        }
        X = model.prepare_features([stats])
        assert not np.any(np.isnan(X))


# ---------------------------------------------------------------------------
# Tests: _get_grade
# ---------------------------------------------------------------------------


class TestGetGrade:
    def test_grade_a_above_85(self):
        model = _fresh_model()
        assert model._get_grade(90) == "A"

    def test_grade_b_70_to_85(self):
        model = _fresh_model()
        assert model._get_grade(75) == "B"

    def test_grade_c_55_to_70(self):
        model = _fresh_model()
        assert model._get_grade(60) == "C"

    def test_grade_d_40_to_55(self):
        model = _fresh_model()
        assert model._get_grade(45) == "D"

    def test_grade_f_below_40(self):
        model = _fresh_model()
        assert model._get_grade(20) == "F"

    def test_grade_at_boundary_85(self):
        model = _fresh_model()
        assert model._get_grade(85) == "A"


# ---------------------------------------------------------------------------
# Tests: train (insufficient data and no LightGBM)
# ---------------------------------------------------------------------------


class TestTrain:
    def test_returns_error_insufficient_data(self):
        model = _fresh_model()
        result = model.train(_make_driver_list(3), [70, 80, 60])
        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    def test_returns_error_when_lightgbm_unavailable(self):
        from app.core.ml import driver_performance_ml as dpm_mod

        original = dpm_mod.LIGHTGBM_AVAILABLE
        try:
            dpm_mod.LIGHTGBM_AVAILABLE = False
            model = _fresh_model()
            model.regressor = None
            result = model.train(_make_driver_list(10), [70.0] * 10)
            assert result["success"] is False
        finally:
            dpm_mod.LIGHTGBM_AVAILABLE = original

    def test_train_success_with_mocked_regressor(self):
        """Test successful training path via mocked LightGBM regressor."""
        model = _fresh_model()
        if model.regressor is None:
            pytest.skip("LightGBM not available")

        # Mock the regressor to avoid actual ML training
        mock_regressor = MagicMock()
        mock_regressor.predict.return_value = np.array([70.0] * 10, dtype=np.float32)
        mock_regressor.feature_importances_ = np.ones(len(model.FEATURE_NAMES)) / len(
            model.FEATURE_NAMES
        )
        model.regressor = mock_regressor

        with (
            patch(
                "app.core.ml.driver_performance_ml.mean_absolute_error",
                return_value=2.5,
            ),
            patch(
                "app.core.ml.driver_performance_ml.r2_score",
                return_value=0.85,
            ),
        ):
            result = model.train(_make_driver_list(10), [70.0] * 10)

        assert result["success"] is True
        assert "mae" in result
        assert "r2" in result
        assert "feature_importance" in result
        assert model.is_trained is True

    def test_train_exception_returns_error(self):
        """Simulate an exception inside train()."""
        model = _fresh_model()
        if model.regressor is None:
            pytest.skip("LightGBM not available")

        model.regressor = MagicMock()
        model.regressor.fit = MagicMock(side_effect=RuntimeError("fit exploded"))
        result = model.train(_make_driver_list(10), [70.0] * 10)
        assert result["success"] is False
        assert "fit exploded" in result["error"]


# ---------------------------------------------------------------------------
# Tests: train_ranker (insufficient data)
# ---------------------------------------------------------------------------


class TestTrainRanker:
    def test_returns_error_insufficient_data(self):
        model = _fresh_model()
        result = model.train_ranker(_make_driver_list(3), [1, 2, 3])
        assert result["success"] is False

    def test_returns_error_when_lightgbm_unavailable(self):
        from app.core.ml import driver_performance_ml as dpm_mod

        original = dpm_mod.LIGHTGBM_AVAILABLE
        try:
            dpm_mod.LIGHTGBM_AVAILABLE = False
            model = _fresh_model()
            model.ranker = None
            result = model.train_ranker(_make_driver_list(10), list(range(1, 11)))
            assert result["success"] is False
        finally:
            dpm_mod.LIGHTGBM_AVAILABLE = original

    def test_train_ranker_success_with_mocked_ranker(self):
        """Test successful ranker training path via mocked LightGBM ranker."""
        model = _fresh_model()
        if model.ranker is None:
            pytest.skip("LightGBM not available")

        mock_ranker = MagicMock()
        model.ranker = mock_ranker

        result = model.train_ranker(_make_driver_list(10), list(range(1, 11)))

        assert result["success"] is True
        assert result["sample_count"] == 10
        assert model.ranker_trained is True

    def test_train_ranker_exception_returns_error(self):
        model = _fresh_model()
        if model.ranker is None:
            pytest.skip("LightGBM not available")

        model.ranker = MagicMock()
        model.ranker.fit = MagicMock(side_effect=RuntimeError("ranker exploded"))
        result = model.train_ranker(_make_driver_list(10), list(range(1, 11)))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Tests: predict_score (fallback path — model not trained)
# ---------------------------------------------------------------------------


class TestPredictScore:
    def test_fallback_when_not_trained(self):
        from app.core.ml.driver_performance_ml import DriverScorePrediction

        model = _fresh_model()
        result = model.predict_score(_make_driver_stats(filo_karsilastirma=10.0))
        assert isinstance(result, DriverScorePrediction)
        assert 0 <= result.predicted_score <= 100
        assert result.confidence == 0.3

    def test_fallback_grade_assigned(self):
        model = _fresh_model()
        result = model.predict_score(_make_driver_stats(filo_karsilastirma=40.0))
        assert result.efficiency_grade in ["A", "B", "C", "D", "F"]

    def test_fallback_score_clamped_at_100(self):
        model = _fresh_model()
        result = model.predict_score(_make_driver_stats(filo_karsilastirma=200.0))
        assert result.predicted_score <= 100.0

    def test_fallback_score_clamped_at_0(self):
        model = _fresh_model()
        result = model.predict_score(_make_driver_stats(filo_karsilastirma=-200.0))
        assert result.predicted_score >= 0.0

    def test_trained_model_path(self):
        """Test predict_score when model is already trained (is_trained=True)."""
        model = _fresh_model()
        if model.regressor is None:
            pytest.skip("LightGBM not available")

        mock_regressor = MagicMock()
        mock_regressor.predict.return_value = np.array([78.5])
        model.regressor = mock_regressor
        model.is_trained = True
        model.feature_importance = {"toplam_sefer": 0.1}

        result = model.predict_score(_make_driver_stats())

        assert result.confidence == 0.8
        assert result.predicted_score == pytest.approx(78.5, abs=0.2)
        assert result.efficiency_grade in ["A", "B", "C", "D", "F"]


# ---------------------------------------------------------------------------
# Tests: predict_batch
# ---------------------------------------------------------------------------


class TestPredictBatch:
    def test_empty_list_returns_empty(self):
        model = _fresh_model()
        assert model.predict_batch([]) == []

    def test_returns_correct_count(self):
        model = _fresh_model()
        results = model.predict_batch(_make_driver_list(5))
        assert len(results) == 5

    def test_ranks_are_assigned(self):
        model = _fresh_model()
        results = model.predict_batch(_make_driver_list(3))
        ranks = [r.rank for r in results]
        assert sorted(ranks) == [1, 2, 3]

    def test_percentiles_vary(self):
        model = _fresh_model()
        results = model.predict_batch(
            [
                _make_driver_stats(filo_karsilastirma=40.0),
                _make_driver_stats(filo_karsilastirma=-10.0),
            ]
        )
        percentiles = [r.percentile for r in results]
        assert len(set(percentiles)) > 1  # they differ

    def test_all_grades_are_valid(self):
        model = _fresh_model()
        results = model.predict_batch(_make_driver_list(5))
        for r in results:
            assert r.efficiency_grade in ["A", "B", "C", "D", "F"]


# ---------------------------------------------------------------------------
# Tests: get_model_status
# ---------------------------------------------------------------------------


class TestGetModelStatus:
    def test_returns_dict_with_expected_keys(self):
        model = _fresh_model()
        status = model.get_model_status()
        assert "lightgbm_available" in status
        assert "regressor_trained" in status
        assert "ranker_trained" in status
        assert "feature_importance" in status

    def test_regressor_trained_false_initially(self):
        model = _fresh_model()
        assert model.get_model_status()["regressor_trained"] is False


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestDriverPerformanceMLSingleton:
    def test_get_driver_performance_ml_returns_instance(self):
        from app.core.ml.driver_performance_ml import (
            DriverPerformanceML,
            get_driver_performance_ml,
        )

        ml = get_driver_performance_ml()
        assert isinstance(ml, DriverPerformanceML)

    def test_get_driver_performance_ml_same_instance(self):
        from app.core.ml.driver_performance_ml import get_driver_performance_ml

        a = get_driver_performance_ml()
        b = get_driver_performance_ml()
        assert a is b
