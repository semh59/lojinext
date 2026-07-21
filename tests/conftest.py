import os
import sys
from contextlib import ExitStack
from unittest import mock
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import UserDefinedType

# Mock problematic dependencies globally for tests (that don't affect logic)
sys.modules["sentry_sdk"] = MagicMock()
sys.modules["sentry_sdk.integrations"] = MagicMock()
sys.modules["sentry_sdk.integrations.fastapi"] = MagicMock()
sys.modules["sentry_sdk.integrations.sqlalchemy"] = MagicMock()
sys.modules["groq"] = MagicMock()
sys.modules["shapely"] = MagicMock()
sys.modules["shapely.geometry"] = MagicMock()
sys.modules["prometheus_fastapi_instrumentator"] = MagicMock()

# --- PREVENT ML MODEL CACHE LOADING IN TESTS ---
from unittest.mock import patch  # noqa: E402


def mock_load_model(self, *args, **kwargs):
    raise RuntimeError("Loading mocked out for tests")


@pytest.fixture(scope="function", autouse=True)
def _mock_ml_load_model_for_tests():
    """
    Scoped to ``tests/`` only (autouse fixtures in a conftest only apply to the
    directory tree they live in).  Prevents on-disk ML model loading in unit
    tests where no trained .pkl files are available.

    ``app/tests/`` tests — including test_ensemble_security_checksum — do NOT
    get this mock, so they can exercise the real save/load path.

    NOTE: Must be function-scoped (not session) so the patcher is stopped
    after each test function and does NOT bleed into the app/tests/ subtree
    when both directories are collected in the same pytest session.
    """
    patcher = patch(
        "v2.modules.prediction_ml.domain.ensemble_core.EnsembleFuelPredictor.load_model",
        new=mock_load_model,
    )
    patcher.start()
    yield
    patcher.stop()


class MockGeometry(UserDefinedType):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def get_col_spec(self, **kw):
        return "TEXT"

    def bind_processor(self, dialect):
        def process(value):
            return value

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return value

        return process


sys.modules["geoalchemy2"] = MagicMock()
sys.modules["geoalchemy2"].Geometry = MockGeometry
sys.modules["geoalchemy2.shape"] = MagicMock()

# PostgreSQL Configuration from app config
from sqlalchemy.pool import NullPool  # noqa: E402

from app.config import settings  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL env var gerekli", allow_module_level=True)


async def _terminate_other_test_connections(conn) -> None:
    await conn.execute(
        text(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
            """
        )
    )


async def _reset_public_schema(conn) -> None:
    await _terminate_other_test_connections(conn)
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    user = os.getenv("POSTGRES_USER", "lojinext_user")
    await conn.execute(text(f"GRANT ALL ON SCHEMA public TO {user}"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


@pytest.fixture(autouse=True)
def bypass_token_blacklist(monkeypatch):
    async def _not_blacklisted(_token: str) -> bool:
        return False

    monkeypatch.setattr(
        "v2.modules.auth_rbac.infrastructure.token_blacklist.blacklist.is_blacklisted",
        _not_blacklisted,
    )


@pytest.fixture(autouse=True)
def reset_rate_limiter_registry():
    from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry

    RateLimiterRegistry._limiters.clear()
    yield
    RateLimiterRegistry._limiters.clear()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Session scoped engine to avoid attached to a different loop errors."""
    if not TEST_DATABASE_URL.startswith("postgresql"):
        pytest.fail(
            "Legacy tests require a PostgreSQL TEST_DATABASE_URL. "
            f"Resolved value: {TEST_DATABASE_URL}"
        )

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    if engine.dialect.name != "postgresql":
        await engine.dispose()
        pytest.fail(
            f"Legacy tests are PostgreSQL-only. Resolved dialect: {engine.dialect.name}"
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
def db_session_factory(db_engine, monkeypatch):
    """Session scoped session maker that also patches the globally used SessionLocals."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    import app.database.connection  # noqa: E402
    import app.database.unit_of_work  # noqa: E402

    monkeypatch.setattr(app.database.connection, "AsyncSessionLocal", factory)
    monkeypatch.setattr(app.database.unit_of_work, "AsyncSessionLocal", factory)

    return factory


@pytest_asyncio.fixture(scope="function")
async def setup_test_db(db_engine, db_session_factory):
    from app.database.models import (
        Base,
        Kullanici,
        Rol,
    )

    original_environment = settings.ENVIRONMENT
    original_alembic_ready = settings.ALEMBIC_READY
    settings.ENVIRONMENT = "test"
    settings.ALEMBIC_READY = True

    from app.api.deps import get_db
    from app.main import app
    from v2.modules.auth_rbac.domain.security import get_password_hash

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        async with db_engine.begin() as conn:
            await _reset_public_schema(conn)
            await conn.run_sync(Base.metadata.drop_all)
            for stmt in (
                "DO $$ BEGIN CREATE TYPE error_layer AS ENUM "
                "('db','celery','api','service','frontend','external','security','ml'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$",
                "DO $$ BEGIN CREATE TYPE error_severity AS ENUM "
                "('critical','error','warning','info'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$",
            ):
                await conn.execute(text(stmt))
            await conn.run_sync(Base.metadata.create_all)
            # Test parity with app/tests/conftest.py: the stats endpoint
            # expects the PostgreSQL materialized view. Without it, any test
            # under tests/ that creates a sefer spams the DB log with
            # "relation sefer_istatistik_mv does not exist" noise.
            await conn.execute(
                text("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv")
            )
            await conn.execute(
                text(
                    """
                    CREATE MATERIALIZED VIEW sefer_istatistik_mv AS
                    SELECT
                        durum,
                        COUNT(id) AS toplam_sefer,
                        COALESCE(SUM(mesafe_km), 0) AS toplam_km,
                        COALESCE(SUM(otoban_mesafe_km), 0) AS highway_km,
                        COALESCE(SUM(ascent_m), 0) AS total_ascent,
                        COALESCE(SUM(net_kg / 1000.0), 0) AS total_weight,
                        MAX(created_at) AS last_updated
                    FROM seferler
                    WHERE is_deleted = FALSE
                    GROUP BY durum
                    """
                )
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX idx_sefer_istatistik_mv_durum "
                    "ON sefer_istatistik_mv (durum)"
                )
            )

        # Seed mandatory users for tests
        async with db_session_factory() as session:
            # Create Roles
            super_rol = Rol(ad="super_admin", yetkiler={"*": True})
            user_rol = Rol(
                ad="user",
                yetkiler={
                    "read": True,
                    "write": True,
                    "sefer:read": True,
                    "sefer:write": True,
                    "fuel:read": True,
                    "fuel:write": True,
                },
            )
            session.add_all([super_rol, user_rol])
            await session.commit()
            await session.refresh(super_rol)
            await session.refresh(user_rol)

            # Create Users
            admin_user = Kullanici(
                email=settings.SUPER_ADMIN_USERNAME,
                ad_soyad="Test Admin",
                sifre_hash=get_password_hash("test_pass"),
                rol_id=super_rol.id,
                aktif=True,
            )
            normal_user = Kullanici(
                email="user@example.com",
                ad_soyad="Test User",
                sifre_hash=get_password_hash("test_pass"),
                rol_id=user_rol.id,
                aktif=True,
            )
            session.add_all([admin_user, normal_user])
            await session.commit()

        yield
    finally:
        app.dependency_overrides.clear()
        async with db_engine.begin() as conn:
            await _reset_public_schema(conn)
            await conn.run_sync(Base.metadata.drop_all)
        settings.ENVIRONMENT = original_environment
        settings.ALEMBIC_READY = original_alembic_ready


@pytest_asyncio.fixture(scope="function")
async def db_session(db_session_factory, setup_test_db):
    """Async database session fixture (requires setup_test_db implicitly)"""
    async with db_session_factory() as session:
        yield session
        await session.rollback()


# ============== API TEST FIXTURES ==============


@pytest.fixture(scope="function")
def client(setup_test_db):
    """FastAPI TestClient fixture (Sync)"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def async_client(setup_test_db):
    """Async FastAPI TestClient fixture"""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def async_superuser_token_headers(async_client):
    """Admin token simulation"""
    from v2.modules.auth_rbac.domain.jwt_handler import create_access_token

    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "typ": "access", "is_super": True}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def async_normal_user_token_headers(async_client):
    """Normal user token simulation"""
    from v2.modules.auth_rbac.domain.jwt_handler import create_access_token

    token = create_access_token(data={"sub": "user@example.com", "typ": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def mocker():
    """Minimal pytest-mock compatible fixture for legacy tests."""

    class SimpleMocker:
        Mock = mock.Mock
        MagicMock = mock.MagicMock
        AsyncMock = mock.AsyncMock
        call = mock.call
        ANY = mock.ANY

        def __init__(self):
            self._stack = ExitStack()

        def patch(self, target, *args, **kwargs):
            return self._stack.enter_context(mock.patch(target, *args, **kwargs))

        def patch_object(self, target, attribute, *args, **kwargs):
            return self._stack.enter_context(
                mock.patch.object(target, attribute, *args, **kwargs)
            )

        def spy(self, obj, name):
            original = getattr(obj, name)
            wrapper = mock.Mock(wraps=original)
            self._stack.enter_context(mock.patch.object(obj, name, wrapper))
            return wrapper

        def stopall(self):
            self._stack.close()

    fixture = SimpleMocker()
    try:
        yield fixture
    finally:
        fixture.stopall()


@pytest_asyncio.fixture(scope="function")
async def sofor_id(db_session_factory, setup_test_db):
    """Seed a disposable driver record for legacy delete smoke tests."""
    from v2.modules.driver.public import Sofor

    async with db_session_factory() as session:
        sofor = Sofor(
            ad_soyad="Delete Test Driver",
            telefon="05000000000",
            ehliyet_sinifi="E",
            aktif=True,
            is_deleted=False,
        )
        session.add(sofor)
        await session.commit()
        await session.refresh(sofor)
        yield sofor.id
