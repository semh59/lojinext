from v2.modules.trip.application.trip_prediction_enrichment import (
    extract_prediction_values,
)
from v2.modules.trip.infrastructure.sefer_timeline_repo import (
    _normalize_event_type,
)


def test_extract_prediction_values_prefers_canonical_field():
    value, meta = extract_prediction_values(
        {
            "tahmini_tuketim": 32.4,
            "prediction_liters": 999.0,
            "model_used": "ensemble",
            "model_version": "ensemble-v2",
            "confidence_score": 0.82,
        },
        quality_flags={"route_available": True},
    )

    assert value == 32.4
    assert meta is not None
    assert meta["model_used"] == "ensemble"
    assert meta["model_version"] == "ensemble-v2"
    assert meta["input_quality"]["route_available"] is True


def test_extract_prediction_values_rejects_alias_only_payload():
    value, meta = extract_prediction_values(
        {
            "prediction_liters": 41.7,
            "model_used": "physics",
        }
    )

    assert value is None
    assert meta is None


def test_timeline_event_type_normalization_prediction_refresh():
    event_type = _normalize_event_type(
        "UPDATE",
        [{"alan": "tahmini_tuketim", "eski": 30.1, "yeni": 31.0}],
    )
    assert event_type == "PREDICTION_REFRESH"


def test_timeline_event_type_normalization_status_change():
    event_type = _normalize_event_type(
        "UPDATE",
        [{"alan": "durum", "eski": "Planlandı", "yeni": "Tamamlandı"}],
    )
    assert event_type == "STATUS_CHANGE"


# test_ensemble_feature_alignment_* moved to
# v2/services/prediction_ml_service/tests/test_ensemble_feature_alignment.py
# (Task 5, 2026-08-04) -- EnsembleFuelPredictor only lives in that
# service's own package now.
