"""
Split off app/tests/unit/test_services/test_sefer_prediction_contract.py
(missed in the original Task 5 test-fix punch list, caught by a real CI
lint run 2026-08-05): EnsembleFuelPredictor only lives in this service's
own package now. Mechanical import-path fix only, no behavioral changes.
"""

import numpy as np
import pytest
from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor


class _DummyModel:
    def __init__(self, n_features_in_: int):
        self.n_features_in_ = n_features_in_


def test_ensemble_feature_alignment_raises_for_extra_runtime_features():
    """
    When the runtime feature matrix has MORE columns than the persisted model
    was trained on, _align_feature_matrix must raise RuntimeError and mark the
    predictor as untrained — silent truncation would cause prediction corruption.
    (This supersedes the old 'truncates_for_legacy_model' behaviour.)
    """
    predictor = EnsembleFuelPredictor()
    predictor.scaler = _DummyModel(n_features_in_=24)
    predictor.is_trained = True
    X = np.ones((1, 26), dtype=float)

    with pytest.raises(RuntimeError, match="Feature schema mismatch"):
        predictor._align_feature_matrix(X)

    assert predictor.is_trained is False, (
        "is_trained must be False after schema mismatch so physics fallback activates"
    )


def test_ensemble_feature_alignment_rejects_missing_runtime_features():
    predictor = EnsembleFuelPredictor()
    predictor.scaler = _DummyModel(n_features_in_=26)
    X = np.ones((1, 24), dtype=float)

    with pytest.raises(RuntimeError, match="Feature schema mismatch"):
        predictor._align_feature_matrix(X)
