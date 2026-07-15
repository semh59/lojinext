"""GET /anomalies/clusters testleri."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_ROWS = [
    {
        "id": 1,
        "tip": "tuketim",
        "kaynak_tip": "arac",
        "kaynak_id": 1,
        "severity": "high",
        "sapma_yuzde": 25.0,
    },
    {
        "id": 2,
        "tip": "tuketim",
        "kaynak_tip": "arac",
        "kaynak_id": 1,
        "severity": "high",
        "sapma_yuzde": 26.0,
    },
    {
        "id": 3,
        "tip": "tuketim",
        "kaynak_tip": "arac",
        "kaynak_id": 2,
        "severity": "high",
        "sapma_yuzde": 24.0,
    },
]


async def test_clusters_returns_patterns(async_client, normal_auth_headers):
    with patch(
        "v2.modules.anomaly.api.anomaly_routes.get_anomaly_detector"
    ) as mock_det:
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=_ROWS)
        resp = await async_client.get(
            "/api/v1/anomalies/clusters?days=30", headers=normal_auth_headers
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["clusters"][0]["size"] == 3
    assert body["clusters"][0]["dominant_tip"] == "tuketim"


async def test_clusters_requires_auth(async_client):
    resp = await async_client.get("/api/v1/anomalies/clusters")
    assert resp.status_code == 401


async def test_clusters_llm_failure_does_not_block(
    async_client, normal_auth_headers, monkeypatch
):
    monkeypatch.setattr("app.config.settings.ANOMALY_CLUSTER_LLM_ENABLED", True)
    with (
        patch("v2.modules.anomaly.api.anomaly_routes.get_anomaly_detector") as mock_det,
        patch(
            "v2.modules.anomaly.api.anomaly_routes._cluster_insight",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ),
    ):
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=_ROWS)
        resp = await async_client.get(
            "/api/v1/anomalies/clusters", headers=normal_auth_headers
        )
    assert resp.status_code == 200
    assert resp.json()["clusters"][0]["insight"] is None
