"""
Coverage tests for KalmanFuelEstimator and KalmanEstimatorService (kalman_estimator.py).
Uses real numpy operations — no heavy mocking needed.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_features(**overrides):
    base = {"ton": 20.0, "ascent_m": 500.0, "arac_yasi": 5}
    base.update(overrides)
    return base


def _fresh_estimator(arac_id=1):
    from app.core.ml.kalman_estimator import KalmanFuelEstimator

    return KalmanFuelEstimator(arac_id=arac_id)


# ---------------------------------------------------------------------------
# Tests: KalmanState
# ---------------------------------------------------------------------------


class TestKalmanState:
    def test_default_state_shape(self):
        from app.core.ml.kalman_estimator import KalmanState

        ks = KalmanState()
        assert ks.state.shape == (4,)

    def test_default_covariance_shape(self):
        from app.core.ml.kalman_estimator import KalmanState

        ks = KalmanState()
        assert ks.P.shape == (4, 4)

    def test_default_observations_zero(self):
        from app.core.ml.kalman_estimator import KalmanState

        ks = KalmanState()
        assert ks.n_observations == 0

    def test_last_update_initially_none(self):
        from app.core.ml.kalman_estimator import KalmanState

        ks = KalmanState()
        assert ks.last_update is None


# ---------------------------------------------------------------------------
# Tests: _build_observation_matrix
# ---------------------------------------------------------------------------


class TestBuildObservationMatrix:
    def test_shape_is_4(self):
        est = _fresh_estimator()
        H = est._build_observation_matrix(_make_features())
        assert H.shape == (4,)

    def test_first_element_is_one(self):
        est = _fresh_estimator()
        H = est._build_observation_matrix(_make_features())
        assert H[0] == 1.0

    def test_zero_values_produce_ones_vector(self):
        est = _fresh_estimator()
        # ton=0, ascent=0, age=0 → [1, 0, 0, 0]
        H = est._build_observation_matrix({"ton": 0, "ascent_m": 0, "arac_yasi": 0})
        assert H[1] == 0.0
        assert H[2] == 0.0

    def test_ascent_converted_to_100m_units(self):
        est = _fresh_estimator()
        H = est._build_observation_matrix({"ton": 0, "ascent_m": 200, "arac_yasi": 0})
        assert H[2] == pytest.approx(2.0)

    def test_missing_keys_use_defaults(self):
        est = _fresh_estimator()
        H = est._build_observation_matrix({})
        assert H[0] == 1.0
        assert H[3] == 5.0  # default age=5


# ---------------------------------------------------------------------------
# Tests: predict
# ---------------------------------------------------------------------------


class TestKalmanPredict:
    def test_returns_tuple_of_two_floats(self):
        est = _fresh_estimator()
        result = est.predict(_make_features())
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)

    def test_prediction_is_positive(self):
        est = _fresh_estimator()
        consumption, uncertainty = est.predict(_make_features())
        assert consumption > 0

    def test_uncertainty_is_positive(self):
        est = _fresh_estimator()
        _, uncertainty = est.predict(_make_features())
        assert uncertainty > 0

    def test_prediction_increases_with_load(self):
        est = _fresh_estimator()
        low_load, _ = est.predict(_make_features(ton=5))
        high_load, _ = est.predict(_make_features(ton=30))
        assert high_load > low_load


# ---------------------------------------------------------------------------
# Tests: update
# ---------------------------------------------------------------------------


class TestKalmanUpdate:
    def test_returns_dict_with_expected_keys(self):
        est = _fresh_estimator()
        result = est.update(_make_features(), observed_consumption=32.0)
        assert "observed" in result
        assert "predicted" in result
        assert "innovation" in result
        assert "n_observations" in result
        assert "state" in result

    def test_observation_count_increments(self):
        est = _fresh_estimator()
        est.update(_make_features(), 32.0)
        est.update(_make_features(), 33.0)
        assert est.state.n_observations == 2

    def test_last_update_set_after_update(self):
        est = _fresh_estimator()
        est.update(_make_features(), 32.0)
        assert est.state.last_update is not None
        assert isinstance(est.state.last_update, datetime)

    def test_state_changes_after_update(self):
        est = _fresh_estimator()
        initial_state = est.state.state.copy()
        est.update(_make_features(), 50.0)  # large observation
        assert not np.allclose(est.state.state, initial_state)

    def test_covariance_remains_finite(self):
        est = _fresh_estimator()
        for _ in range(10):
            est.update(_make_features(), 32.0 + np.random.normal(0, 1))
        assert np.all(np.isfinite(est.state.P))

    def test_innovation_is_correct(self):
        est = _fresh_estimator()
        H = est._build_observation_matrix(_make_features())
        y_pred_before = float(np.dot(H, est.state.state))
        observed = 40.0
        result = est.update(_make_features(), observed)
        assert result["innovation"] == pytest.approx(observed - y_pred_before, abs=0.1)


# ---------------------------------------------------------------------------
# Tests: batch_update
# ---------------------------------------------------------------------------


class TestBatchUpdate:
    def test_batch_update_returns_updated_count(self):
        est = _fresh_estimator()
        observations = [
            {"features": _make_features(), "consumption": 32.0 + i} for i in range(5)
        ]
        result = est.batch_update(observations)
        assert result["updated"] == 5

    def test_batch_update_raises_on_oversized(self):
        est = _fresh_estimator()
        observations = [{"features": _make_features(), "consumption": 32.0}] * (
            est.MAX_BATCH_SIZE + 1
        )
        with pytest.raises(ValueError, match="aşılamaz"):
            est.batch_update(observations)

    def test_batch_update_increments_observations(self):
        est = _fresh_estimator()
        observations = [
            {"features": _make_features(), "consumption": 32.0} for _ in range(3)
        ]
        est.batch_update(observations)
        assert est.state.n_observations == 3


# ---------------------------------------------------------------------------
# Tests: get_coefficients
# ---------------------------------------------------------------------------


class TestGetCoefficients:
    def test_returns_dict_with_all_fields(self):
        est = _fresh_estimator()
        coeffs = est.get_coefficients()
        assert "base_consumption" in coeffs
        assert "load_factor" in coeffs
        assert "elevation_factor" in coeffs
        assert "age_factor" in coeffs
        assert "n_observations" in coeffs
        assert "uncertainty" in coeffs

    def test_uncertainty_is_list(self):
        est = _fresh_estimator()
        coeffs = est.get_coefficients()
        assert isinstance(coeffs["uncertainty"], list)
        assert len(coeffs["uncertainty"]) == 4


# ---------------------------------------------------------------------------
# Tests: save_state / load_state
# ---------------------------------------------------------------------------


class TestSaveLoadState:
    def test_save_state_returns_dict(self):
        est = _fresh_estimator(arac_id=7)
        state = est.save_state()
        assert isinstance(state, dict)
        assert "state" in state
        assert "P" in state
        assert state["arac_id"] == 7

    def test_load_state_restores_values(self):
        est = _fresh_estimator(arac_id=7)
        est.update(_make_features(), 35.0)
        snapshot = est.save_state()

        new_est = _fresh_estimator(arac_id=99)
        new_est.load_state(snapshot)

        assert new_est.arac_id == 7
        assert new_est.state.n_observations == 1
        assert np.allclose(new_est.state.state, est.state.state)

    def test_load_state_with_last_update_string(self):
        est = _fresh_estimator()
        est.update(_make_features(), 32.0)
        snapshot = est.save_state()
        # Ensure last_update is an ISO string
        assert snapshot["last_update"] is not None

        new_est = _fresh_estimator()
        new_est.load_state(snapshot)
        assert isinstance(new_est.state.last_update, datetime)

    def test_load_state_raises_on_missing_state(self):
        est = _fresh_estimator()
        with pytest.raises(ValueError, match="zorunludur"):
            est.load_state({"P": [[1, 0, 0, 0]] * 4})

    def test_load_state_raises_on_missing_P(self):
        est = _fresh_estimator()
        with pytest.raises(ValueError, match="zorunludur"):
            est.load_state({"state": [32, 0.12, 0.008, 0.015]})

    def test_load_state_raises_on_wrong_state_shape(self):
        est = _fresh_estimator()
        with pytest.raises(ValueError, match="state vektörü"):
            est.load_state({"state": [1, 2, 3], "P": np.eye(4).tolist()})

    def test_load_state_raises_on_nan_state(self):
        est = _fresh_estimator()
        with pytest.raises(ValueError, match="NaN/Inf"):
            est.load_state(
                {
                    "state": [float("nan"), 0.12, 0.008, 0.015],
                    "P": np.eye(4).tolist(),
                }
            )

    def test_load_state_raises_on_wrong_P_shape(self):
        est = _fresh_estimator()
        with pytest.raises(ValueError, match="P matrisi"):
            est.load_state({"state": [32, 0.12, 0.008, 0.015], "P": [[1, 0], [0, 1]]})

    def test_load_state_raises_on_non_positive_P_diag(self):
        est = _fresh_estimator()
        P_bad = np.eye(4)
        P_bad[0, 0] = -1.0
        with pytest.raises(ValueError, match="pozitif tanımlı"):
            est.load_state(
                {
                    "state": [32, 0.12, 0.008, 0.015],
                    "P": P_bad.tolist(),
                }
            )


# ---------------------------------------------------------------------------
# Tests: KalmanEstimatorService
# ---------------------------------------------------------------------------


class TestKalmanEstimatorService:
    def _make_service(self):
        from app.core.ml.kalman_estimator import KalmanEstimatorService

        svc = KalmanEstimatorService()
        mock_repo = MagicMock()
        mock_repo.get_model_params.return_value = None
        svc._analiz_repo = mock_repo
        return svc

    def test_get_estimator_creates_new(self):
        svc = self._make_service()
        est = svc.get_estimator(arac_id=10)
        assert est is not None
        assert est.arac_id == 10

    def test_get_estimator_returns_cached(self):
        svc = self._make_service()
        e1 = svc.get_estimator(10)
        e2 = svc.get_estimator(10)
        assert e1 is e2

    def test_lru_eviction_at_max(self):
        svc = self._make_service()
        svc.MAX_ESTIMATORS = 3
        for i in range(5):
            svc.get_estimator(i)
        assert len(svc.estimators) == 3

    def test_predict_returns_expected_keys(self):
        svc = self._make_service()
        result = svc.predict(arac_id=1, features=_make_features())
        assert "tahmin_l_100km" in result
        assert "uncertainty" in result
        assert "confidence_low" in result
        assert "confidence_high" in result
        assert "coefficients" in result

    def test_update_with_trip_increments_observations(self):
        svc = self._make_service()
        svc.analiz_repo.save_model_params = MagicMock()
        svc.update_with_trip(
            arac_id=1, features=_make_features(), observed_consumption=32.0
        )
        est = svc.get_estimator(1)
        assert est.state.n_observations == 1

    def test_loads_state_from_repo_when_available(self):
        from app.core.ml.kalman_estimator import KalmanEstimatorService

        svc = KalmanEstimatorService()
        mock_repo = MagicMock()
        # Simulate existing kalman state
        existing_est = _fresh_estimator(arac_id=5)
        existing_est.update(_make_features(), 35.0)
        snapshot = existing_est.save_state()

        # AUDIT-125: get_estimator artık get_model_params'ı asyncio.run ile çağırır
        # (await edilebilir olmalı) → AsyncMock.
        mock_repo.get_model_params = AsyncMock(
            return_value={"coefficients": {"kalman_state": snapshot}}
        )
        svc._analiz_repo = mock_repo

        loaded_est = svc.get_estimator(arac_id=5)
        assert loaded_est.state.n_observations == 1


# ---------------------------------------------------------------------------
# Tests: singleton
# ---------------------------------------------------------------------------


class TestKalmanSingleton:
    def test_get_kalman_service_returns_instance(self):
        from app.core.ml.kalman_estimator import (
            KalmanEstimatorService,
            get_kalman_service,
        )

        svc = get_kalman_service()
        assert isinstance(svc, KalmanEstimatorService)

    def test_get_kalman_service_same_instance(self):
        from app.core.ml.kalman_estimator import get_kalman_service

        a = get_kalman_service()
        b = get_kalman_service()
        assert a is b
