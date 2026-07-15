"""anomaly.cluster_scan task testi."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_cluster_scan_returns_cluster_count():
    rows = [
        {
            "id": i,
            "tip": "tuketim",
            "kaynak_tip": "arac",
            "kaynak_id": 1,
            "severity": "high",
            "sapma_yuzde": 25.0 + i,
        }
        for i in range(3)
    ]
    with patch(
        "v2.modules.anomaly.infrastructure.cluster_tasks.get_anomaly_detector"
    ) as mock_det:
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=rows)
        from v2.modules.anomaly.infrastructure.cluster_tasks import cluster_scan

        result = cluster_scan.run()

    assert result["clusters"] >= 1
    assert result["anomalies"] == 3
