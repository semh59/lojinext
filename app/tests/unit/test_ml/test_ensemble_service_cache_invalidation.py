"""Redis-backed model-version cache invalidation için karakterizasyon testleri."""

import pytest

from v2.modules.prediction_ml.application.ensemble_service import (
    EnsemblePredictorService,
)

pytestmark = pytest.mark.unit


def test_bump_model_version_increments_and_is_readable():
    svc = EnsemblePredictorService()
    v0 = svc._get_model_version(999)
    assert v0 == 0

    svc._bump_model_version(999)
    v1 = svc._get_model_version(999)
    assert v1 == 1

    svc._bump_model_version(999)
    v2 = svc._get_model_version(999)
    assert v2 == 2


def test_get_predictor_reloads_when_redis_version_is_newer():
    svc = EnsemblePredictorService()
    # Seed an in-memory cached predictor at version 0
    predictor = svc.get_predictor(998)
    predictor._cached_model_version = 0

    # Simulate another worker having trained a newer version
    svc._bump_model_version(998)

    reloaded = svc.get_predictor(998)
    assert reloaded._cached_model_version == 1
