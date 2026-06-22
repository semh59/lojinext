"""anomaly_clustering testleri."""

import pytest

from app.core.ml.anomaly_clustering import cluster_anomalies

pytestmark = pytest.mark.unit


def _a(id, tip, kaynak_tip, severity, sapma):
    return {
        "id": id,
        "tip": tip,
        "kaynak_tip": kaynak_tip,
        "kaynak_id": 1,
        "severity": severity,
        "sapma_yuzde": sapma,
    }


def test_groups_similar_anomalies_into_a_cluster():
    rows = [
        _a(1, "tuketim", "arac", "high", 25.0),
        _a(2, "tuketim", "arac", "high", 26.0),
        _a(3, "tuketim", "arac", "high", 24.5),
        _a(4, "maliyet", "sefer", "low", 3.0),  # tek başına → noise
    ]
    clusters = cluster_anomalies(rows, eps=0.6, min_samples=2)
    assert len(clusters) >= 1
    top = clusters[0]
    assert top["size"] == 3
    assert top["dominant_tip"] == "tuketim"
    assert set(top["member_ids"]) == {1, 2, 3}
    assert isinstance(top["label"], str) and top["label"]


def test_empty_input_returns_empty():
    assert cluster_anomalies([]) == []


def test_too_few_returns_no_clusters():
    # min_samples=2 altında küme oluşmaz (noise)
    assert cluster_anomalies([_a(1, "tuketim", "arac", "high", 25.0)]) == []
