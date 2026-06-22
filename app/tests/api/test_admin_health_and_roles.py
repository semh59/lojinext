from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_admin_health_reset_missing_breaker(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/admin/health/circuit-breaker/reset",
        params={"service_name": "missing_breaker"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 404
    assert "Servis bulunamadi" in response.text


@pytest.mark.asyncio
async def test_admin_health_backup_trigger_uses_service_override(
    async_client, admin_auth_headers, monkeypatch
):
    mock_trigger = AsyncMock(
        return_value={
            "message": "Yedekleme islemi baslatildi.",
            "task_id": "backup_test_task",
        }
    )
    monkeypatch.setattr(
        "app.core.services.health_service.HealthService.trigger_manual_backup",
        mock_trigger,
    )

    response = await async_client.post(
        "/api/v1/admin/health/backup/trigger",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == "backup_test_task"


@pytest.mark.asyncio
async def test_admin_roles_reject_invalid_permission_payload(
    async_client, admin_auth_headers
):
    response = await async_client.post(
        "/api/v1/admin/roles/",
        json={"ad": "invalid-role", "yetkiler": {"sefer:read": "yes"}},
        headers=admin_auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_roles_accept_boolean_permission_map(
    async_client, admin_auth_headers
):
    response = await async_client.post(
        "/api/v1/admin/roles/",
        json={"ad": "phase10-role", "yetkiler": {"sefer:read": True}},
        headers=admin_auth_headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ad"] == "phase10-role"
    assert payload["yetkiler"] == {"sefer:read": True}
