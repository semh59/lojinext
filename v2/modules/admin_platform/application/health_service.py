import asyncio
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text

from app.config import settings
from app.database.connection import engine
from app.infrastructure.logging.logger import get_logger

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

logger = get_logger(__name__)


class HealthService:
    """
        Sistem bileşenlerinin sağlık durumunu denetler.
        (Database, AI Models, Cache, External APIs, Sentry Errors)

    TYPE: SINGLETON
    SCOPE: Application lifetime
    SINGLETON_REASON: Sağlık kontrolü — bağlantı ping'leri, stateless.
    CREATED_BY: v2/modules/platform_infra/container.py (lazy property)
    """

    def __init__(self):
        self.start_time = time.time()
        self._bg_tasks: set[asyncio.Task] = set()

    def _get_backup_manager(self):
        from app.infrastructure.database.backup_manager import DatabaseBackupManager

        return DatabaseBackupManager()

    async def check_db(self) -> Dict[str, Any]:
        """Veritabanı bağlantı testi"""
        start = time.time()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            logger.error(f"DB Health Check Failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def check_redis(self) -> Dict[str, Any]:
        """Redis bağlantı testi (Sentinel-aware — REDIS_USE_SENTINEL altında
        her zaman güncel master'ı sorgular, dead-hostname'e sabitlenmez)."""
        start = time.time()
        try:
            from v2.modules.platform_infra.cache.redis_client_factory import (
                get_async_redis_client,
            )

            client = get_async_redis_client(socket_connect_timeout=2, socket_timeout=2)
            await client.ping()
            await client.aclose()
            return {
                "status": "healthy",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def check_ai_readiness(self) -> Dict[str, Any]:
        """AI modellerinin yüklenme durumu"""
        try:
            from v2.modules.ai_assistant.public import get_rag_engine
            from v2.modules.platform_infra.container import get_container

            rag = get_rag_engine()
            rag_stats = rag.get_stats()

            try:
                ensemble = get_container().prediction_service.ensemble_service
                loaded_models = list(getattr(ensemble, "_models", {}).keys()) or [
                    "physics",
                    "lightgbm",
                    "xgboost",
                    "gb",
                    "rf",
                ]
            except Exception:
                loaded_models = ["physics", "lightgbm", "xgboost", "gb", "rf"]

            return {
                "status": "healthy" if rag_stats.get("initialized") else "degraded",
                "rag_engine": rag_stats,
                "models": loaded_models
                + (["rag"] if rag_stats.get("initialized") else []),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_sentry_summary(self) -> Dict[str, Any]:
        """Sentry entegrasyonunun gercek runtime durumunu raporla."""
        is_active = False
        if sentry_sdk is not None:
            is_active = sentry_sdk.Hub.current.client is not None
        elif settings.SENTRY_DSN:
            logger.warning("SENTRY_DSN is set but sentry_sdk package is not installed.")
        return {
            "enabled": bool(settings.SENTRY_DSN),
            "client_active": is_active,
            "environment": settings.ENVIRONMENT,
            "recent_errors_24h": None,
            "source": "sdk_runtime_only",
        }

    async def get_circuit_breakers(self) -> List[Dict[str, Any]]:
        """Sistemdeki gercek circuit breaker registry durumunu don."""
        from v2.modules.platform_infra.resilience.circuit_breaker import (
            CircuitBreakerRegistry,
        )

        return [
            {
                "service": breaker["name"],
                "status": breaker["state"],
                "failure_count": breaker["failure_count"],
                "fail_max": breaker["fail_max"],
                "reset_timeout": breaker["reset_timeout"],
            }
            for breaker in CircuitBreakerRegistry.get_all_status()
        ]

    async def get_backup_status(self) -> Dict[str, Any]:
        """Son yedekleme durumu ve zamanı"""
        backup_dir = Path(self._get_backup_manager().backup_dir)
        backups = (
            sorted(
                [
                    item
                    for pattern in ("*.sql", "*.sqlite3", "*.db")
                    for item in backup_dir.glob(pattern)
                ],
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            if backup_dir.exists()
            else []
        )
        last_backup = backups[0] if backups else None
        total_size_bytes = sum(item.stat().st_size for item in backups)

        return {
            "last_backup": (
                datetime.fromtimestamp(
                    last_backup.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat()
                if last_backup
                else None
            ),
            "status": "success" if last_backup else "missing",
            "storage": str(backup_dir),
            "backup_count": len(backups),
            "backup_dir_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        }

    async def reset_circuit_breaker(self, service_name: str) -> Dict[str, Any]:
        """Var olan breaker'i sifirla."""
        from fastapi import HTTPException

        from v2.modules.platform_infra.resilience.circuit_breaker import (
            CircuitBreakerRegistry,
        )

        if not CircuitBreakerRegistry.reset(service_name):
            raise HTTPException(
                status_code=404, detail=f"Servis bulunamadi: {service_name}"
            )

        return {
            "message": f"{service_name} icin devre kesici sifirlandi.",
            "success": True,
        }

    async def trigger_manual_backup(self) -> Dict[str, Any]:
        """Asenkron manuel backup gorevini tetikle."""
        task_id = f"backup_{uuid4().hex}"
        manager = self._get_backup_manager()
        task = asyncio.create_task(asyncio.to_thread(manager.create_backup))
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return {
            "message": "Yedekleme islemi baslatildi.",
            "task_id": task_id,
        }

    async def get_full_status(self) -> Dict[str, Any]:
        """Tüm sistemin sağlık özeti"""
        db_status, redis_status, ai_status = await asyncio.gather(
            self.check_db(),
            self.check_redis(),
            self.check_ai_readiness(),
        )

        if db_status["status"] != "healthy":
            overall = "unhealthy"
        elif redis_status["status"] != "healthy" or ai_status["status"] != "healthy":
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "status": overall,
            "uptime_seconds": int(time.time() - self.start_time),
            "components": {
                "database": db_status,
                "redis": redis_status,
                "ai_engine": ai_status,
            },
        }

    async def get_admin_health_details(self) -> Dict[str, Any]:
        """Admin paneli için detaylı teknik sağlık raporu"""
        status = await self.get_full_status()
        status["sentry"] = await self.get_sentry_summary()
        status["circuit_breakers"] = await self.get_circuit_breakers()
        status["backups"] = await self.get_backup_status()
        return status


# Thread-safe Singleton
_health_service: Optional["HealthService"] = None
_health_service_lock = threading.Lock()


def get_health_service() -> HealthService:
    """Thread-safe singleton getter"""
    global _health_service
    if _health_service is None:
        with _health_service_lock:
            if _health_service is None:
                _health_service = HealthService()
    return _health_service
