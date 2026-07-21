"""
App-boot smoke tests (Bölüm 2 P0).

These tests must remain fast and have zero external dependencies.
They verify that the application can be imported and its router
structure is intact — catching bootstrap import errors early.

Run these in CI before any other test suite:
    pytest tests/test_app_boot.py -q
"""

import importlib
import os
import sys

import pytest

# ── Minimal env overrides so Settings() doesn't blow up ──────────────────────
os.environ.setdefault("SECRET_KEY", "smoke-test-secret-key-000000000000000000")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost")
os.environ.setdefault("ADMIN_PASSWORD", "smoke-test-pass")

# Silence optional heavy dependencies that are not installed in CI
for _mod in (
    "sentry_sdk",
    "sentry_sdk.integrations",
    "sentry_sdk.integrations.fastapi",
    "sentry_sdk.integrations.sqlalchemy",
    "groq",
    "prometheus_fastapi_instrumentator",
    "shapely",
    "shapely.geometry",
):
    sys.modules.setdefault(
        _mod,
        pytest.importorskip(_mod, minversion=None)
        if False
        else __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(),
    )


class TestAppBootImport:
    """The application module must be importable without side effects."""

    def test_config_imports_cleanly(self):
        """Settings class loads without AttributeError."""
        from app.config import settings

        assert settings.PROJECT_NAME == "LojiNext"
        assert settings.API_V1_STR == "/api/v1"
        assert settings.ENVIRONMENT in ("dev", "test", "prod")

    def test_settings_has_all_required_fields(self):
        """Every field referenced in the codebase exists on settings."""
        from app.config import settings

        required = [
            "SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "CORS_ORIGINS",
            "ENVIRONMENT",
            "LOG_LEVEL",
            "SUPER_ADMIN_USERNAME",
            "API_V1_STR",
            "PROJECT_NAME",
            "OTEL_ENABLED",
            "SENTRY_DSN",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
            "EXTERNAL_API_RATE_LIMIT",
        ]
        for field in required:
            assert hasattr(settings, field), f"settings.{field} missing"

    def test_main_module_imports_cleanly(self):
        """app.main must be importable — catches shutdown/lifespan import errors."""
        import app.main  # noqa: F401 — side-effect is the test

    def test_app_object_exists(self):
        """The FastAPI app object must be created and titled correctly."""
        from app.main import app

        assert app.title == "LojiNext"

    def test_api_router_mounted(self):
        """API router must be mounted under /api/v1."""
        from app.main import app

        prefixes = [r.path for r in app.routes]
        assert any("/api/v1" in p for p in prefixes), (
            f"API router not mounted under /api/v1. Found: {prefixes}"
        )

    def test_health_liveness_route_exists(self):
        """/health/liveness must be registered."""
        from app.main import app

        paths = [r.path for r in app.routes]
        assert "/health/liveness" in paths, f"Missing /health/liveness. Routes: {paths}"

    def test_health_readiness_route_exists(self):
        """/health/readiness must be registered."""
        from app.main import app

        paths = [r.path for r in app.routes]
        assert "/health/readiness" in paths, (
            f"Missing /health/readiness. Routes: {paths}"
        )

    def test_unit_of_work_imports(self):
        """UoW must export get_uow — FastAPI dependency."""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import (  # noqa: F401
            UnitOfWork,
            get_uow,
            unit_of_work,
        )

        assert callable(get_uow)

    def test_all_repo_factories_importable(self):
        """All repositories UnitOfWork wires up must be importable from their
        owning v2 module (no central re-export hub — removed dalga 16)."""
        from v2.modules.analytics_executive.infrastructure.executive_read_models import (  # noqa: F401, E501
            AnalizRepository,
        )
        from v2.modules.auth_rbac.infrastructure.kullanici_repository import (  # noqa: F401, E501
            KullaniciRepository,
        )
        from v2.modules.driver.infrastructure.repository import (  # noqa: F401
            SoforRepository,
        )
        from v2.modules.fleet.infrastructure.trailer_repository import (  # noqa: F401
            DorseRepository,
        )
        from v2.modules.fleet.infrastructure.vehicle_repository import (  # noqa: F401
            AracRepository,
        )
        from v2.modules.fuel.infrastructure.repository import (  # noqa: F401
            YakitRepository,
        )
        from v2.modules.location.infrastructure.repository import (  # noqa: F401
            LokasyonRepository,
        )
        from v2.modules.trip.infrastructure.repository import (  # noqa: F401
            SeferRepository,
        )

    def test_no_circular_imports(self):
        """Re-importing the main module a second time must not raise."""
        import app.main

        # reload rebinds app.main.app to a brand-new FastAPI instance. Modules
        # that imported the app at import time (e.g. `from app.main import app`)
        # keep the old object, while runtime imports get the new one — a split
        # that 404s routes registered at runtime in later tests. Restore the
        # canonical app object after the circular-import check to avoid polluting
        # global state for the rest of the session.
        original_app = app.main.app
        try:
            importlib.reload(app.main)  # second import catches circular deps
        finally:
            app.main.app = original_app
