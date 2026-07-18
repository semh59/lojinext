"""POST /admin/predictions/backfill endpoint testi."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_backfill_trigger_returns_summary(async_client, admin_auth_headers):
    with patch(
        "v2.modules.prediction_ml.application.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(
            return_value={"processed": 3, "filled": 3, "failed": 0, "skipped": 0}
        ),
    ):
        resp = await async_client.post(
            "/api/v1/admin/predictions/backfill?limit=10",
            headers=admin_auth_headers,
        )
    # Endpoint submits to BackgroundJobManager and returns 202 PROCESSING + task_id
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "PROCESSING"
    assert "task_id" in body


async def test_backfill_trigger_requires_admin(async_client, normal_auth_headers):
    resp = await async_client.post(
        "/api/v1/admin/predictions/backfill",
        headers=normal_auth_headers,
    )
    assert resp.status_code == 403
