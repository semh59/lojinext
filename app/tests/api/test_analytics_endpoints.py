"""Analytics endpoint testleri."""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_record_page_view(async_client, normal_auth_headers):
    resp = await async_client.post(
        "/api/v1/analytics/page-view",
        json={"route": "/trips"},
        headers=normal_auth_headers,
    )
    assert resp.status_code == 204


async def test_record_requires_auth(async_client):
    resp = await async_client.post(
        "/api/v1/analytics/page-view", json={"route": "/trips"}
    )
    assert resp.status_code == 401


async def test_admin_stats_aggregates(async_client, admin_auth_headers):
    for _ in range(2):
        await async_client.post(
            "/api/v1/analytics/page-view",
            json={"route": "/fuel"},
            headers=admin_auth_headers,
        )
    resp = await async_client.get(
        "/api/v1/admin/analytics/page-views?days=30",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_views"] >= 2
    assert any(r["route"] == "/fuel" for r in body["top_routes"])


async def test_admin_stats_requires_admin(async_client, normal_auth_headers):
    resp = await async_client.get(
        "/api/v1/admin/analytics/page-views", headers=normal_auth_headers
    )
    assert resp.status_code == 403
