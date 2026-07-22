from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from v2.modules.admin_platform.application.health_service import HealthService
from v2.modules.platform_infra.resilience.circuit_breaker import CircuitBreakerRegistry


def test_env_examples_define_dev_cors_origins():
    for path in [Path(".env.example"), Path("app/.env.example")]:
        contents = path.read_text(encoding="utf-8")
        assert "CORS_ORIGINS=" in contents
        assert "localhost:3000" in contents


@pytest.mark.asyncio
async def test_health_service_reads_breaker_registry():
    CircuitBreakerRegistry.clear()
    breaker = CircuitBreakerRegistry.get_sync("weather_api", fail_max=1)
    breaker._on_failure_sync()

    service = HealthService()
    breakers = await service.get_circuit_breakers()

    assert breakers == [
        {
            "service": "weather_api",
            "status": "open",
            "failure_count": 1,
            "fail_max": 1,
            "reset_timeout": breaker.reset_timeout,
        }
    ]

    reset = await service.reset_circuit_breaker("weather_api")
    assert reset["success"] is True
    assert breaker.get_status()["failure_count"] == 0
    assert breaker.get_status()["state"] == "closed"


@pytest.mark.asyncio
async def test_health_service_reads_backup_directory(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    older = backup_dir / "older.sql"
    latest = backup_dir / "latest.sqlite3"
    older.write_text("old", encoding="utf-8")
    latest.write_text("new", encoding="utf-8")

    service = HealthService()
    with patch.object(
        service,
        "_get_backup_manager",
        return_value=SimpleNamespace(backup_dir=str(backup_dir)),
    ):
        status = await service.get_backup_status()

    assert status["status"] == "success"
    assert status["backup_count"] == 2
    assert status["storage"] == str(backup_dir)
    assert status["last_backup"] is not None


@pytest.mark.asyncio
async def test_health_service_trigger_manual_backup_returns_dynamic_task_id():
    service = HealthService()
    manager = SimpleNamespace(create_backup=lambda: "storage/backups/test.sqlite3")

    with (
        patch.object(service, "_get_backup_manager", return_value=manager),
        patch(
            "v2.modules.admin_platform.application.health_service.asyncio.to_thread",
            new=MagicMock(return_value="thread-job"),
        ) as mock_to_thread,
        patch(
            "v2.modules.admin_platform.application.health_service.asyncio.create_task"
        ) as mock_create_task,
    ):
        result = await service.trigger_manual_backup()

    assert result["task_id"].startswith("backup_")
    mock_to_thread.assert_called_once_with(manager.create_backup)
    mock_create_task.assert_called_once_with("thread-job")
