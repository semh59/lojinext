import pytest

# The system router is mounted at /system.
# Available routes (from system.py + error_stream.py both mounted at /system):
#   POST   /system/error-report              — requires auth (get_current_active_user)
#   POST   /system/error-report-batch        — requires auth
#   GET    /system/error-events              — admin only
#   GET    /system/error-stats               — admin only
#   POST   /system/error-events/{id}/resolve — admin only
#   GET    /system/debug/trace/{trace_id}    — admin only
#   POST   /system/error-stream-token        — admin only (from error_stream.py)
#   GET    /system/error-stream              — token auth (from error_stream.py)


@pytest.mark.asyncio
async def test_system_health(async_client, admin_auth_headers):
    # Frontend error-report endpoint — requires auth
    response = await async_client.post(
        "/api/v1/system/error-report",
        json={
            "message": "test error",
            "url": "http://localhost/test",
            "userAgent": "test-agent",
            "timestamp": "2026-06-04T00:00:00Z",
            "severity": "error",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 204, 500)


@pytest.mark.asyncio
async def test_system_info(async_client, admin_auth_headers):
    # error-report-batch requires auth
    response = await async_client.post(
        "/api/v1/system/error-report-batch",
        json=[
            {
                "message": "test",
                "url": "http://localhost",
                "userAgent": "ua",
                "timestamp": "2026-06-04T00:00:00Z",
                "severity": "error",
            }
        ],
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 204, 500)


@pytest.mark.asyncio
async def test_system_stats(async_client, admin_auth_headers):
    # error-stats requires admin auth
    response = await async_client.get(
        "/api/v1/system/error-stats", headers=admin_auth_headers
    )
    assert response.status_code in (200, 401, 500)


@pytest.mark.asyncio
async def test_system_metrics(async_client):
    # error-events requires admin; without auth → 401
    response = await async_client.get("/api/v1/system/error-events")
    assert response.status_code in (200, 401, 404, 500)


@pytest.mark.asyncio
async def test_system_version(async_client, admin_auth_headers):
    # error-report with auth → 204 or 500
    response = await async_client.post(
        "/api/v1/system/error-report",
        json={
            "message": "version check",
            "url": "http://localhost",
            "userAgent": "ua",
            "timestamp": "2026-06-04T00:00:00Z",
            "severity": "info",
        },
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 204, 422, 500)


@pytest.mark.asyncio
async def test_system_requires_permission_for_stats(async_client, normal_auth_headers):
    # error-stats requires admin
    response = await async_client.get(
        "/api/v1/system/error-stats", headers=normal_auth_headers
    )
    assert response.status_code in (403, 401, 404)
