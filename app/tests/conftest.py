import asyncio
import os
import sys
import warnings
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import LargeBinary, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Suppress deprecation warnings during test bootstrap.
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Sentry must be mocked before any app import; otherwise sentry_sdk.init() fires
# with the real DSN from .env and test exceptions get sent to production Sentry.
from unittest.mock import MagicMock  # noqa: E402 (before app imports)

sys.modules.setdefault("sentry_sdk", MagicMock())
sys.modules.setdefault("sentry_sdk.integrations", MagicMock())
sys.modules.setdefault("sentry_sdk.integrations.fastapi", MagicMock())
sys.modules.setdefault("sentry_sdk.integrations.sqlalchemy", MagicMock())
sys.modules.setdefault("sentry_sdk.integrations.logging", MagicMock())

# Path setup
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR.parent))

# Environment defaults updated by fixtures as needed.
os.environ["OPENROUTESERVICE_API_KEY"] = "dummy_test_key"
os.environ["OPENROUTE_API_KEY"] = "dummy_test_key"
os.environ["CORS_ORIGINS"] = "http://localhost"
os.environ["MAPBOX_API_KEY"] = ""

import app.core.container as container_mod  # noqa: E402
import app.database.repositories.analiz_repo as analiz_mod  # noqa: E402
import app.database.repositories.arac_repo as arac_mod  # noqa: E402
import app.database.repositories.sefer_repo as sefer_mod  # noqa: E402
import app.database.repositories.sofor_repo as sofor_mod  # noqa: E402
import app.database.repositories.yakit_repo as yakit_mod  # noqa: E402
from app.database.models import Base  # noqa: E402


def pytest_collection_modifyitems(config, items):
    """Skip all @pytest.mark.integration tests if PostgreSQL is not reachable.

    The reachability probe targets the actual TEST_DATABASE_URL host:port (CI uses
    localhost:5432; a Docker-network runner uses e.g. db:5432) rather than a hard-coded
    localhost, so integration tests are not falsely skipped when the DB lives on a
    non-localhost host.
    """
    import socket

    host, port = "localhost", 5432
    test_url = os.getenv("TEST_DATABASE_URL")
    if test_url:
        try:
            from sqlalchemy.engine import make_url

            url = make_url(test_url)
            host = url.host or host
            port = url.port or port
        except Exception:
            pass

    try:
        s = socket.create_connection((host, port), timeout=1.0)
        s.close()
        # DB is reachable, proceed normally
        return
    except OSError:
        # DB is not reachable, skip integration tests
        skip = pytest.mark.skip(
            reason=f"PostgreSQL not reachable on {host}:{port} — skip integration tests"
        )
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def reset_all_singletons():
    # Reset repository singletons.
    arac_mod._arac_repo = None
    sefer_mod._sefer_repo = None
    sofor_mod._sofor_repo = None
    yakit_mod._yakit_repo = None
    analiz_mod._analiz_repo = None
    # Reset the container singleton.
    container_mod.reset_container()


@pytest.fixture(autouse=True)
def mock_redis_for_cache_manager():
    """0-mock: use a REAL Redis for CacheManager instead of an in-process MagicMock.

    Connects to the configured ``settings.REDIS_URL`` (a reachable Redis — the CI
    ``redis`` service or the dev compose container; point it at an isolated logical
    DB e.g. /15 for tests) and flushes it around each test for isolation. The
    fixture name is unchanged so tests that request it by name keep working; it now
    yields a real ``redis.Redis`` client rather than a mock.
    """
    import redis as _redis_sync

    import app.infrastructure.cache.cache_manager as cm_mod
    from app.config import settings

    client = _redis_sync.from_url(settings.REDIS_URL)
    try:
        client.flushdb()
    except Exception:
        pass

    # Reset singleton so each test gets a fresh CacheManager bound to real Redis
    cm_mod.CacheManager._instance = None
    yield client
    cm_mod.CacheManager._instance = None
    try:
        client.flushdb()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_event_bus_singleton():
    """Reset the EventBus singleton between tests so stale Redis state doesn't bleed.

    The singleton is lazy — resetting _instance forces re-init on next access,
    which picks up the fresh CacheManager that mock_redis_for_cache_manager sets up.
    """
    from app.infrastructure.events import event_bus as eb_mod

    eb_mod.EventBus._instance = None
    yield
    eb_mod.EventBus._instance = None


@pytest.fixture(autouse=True)
def bypass_token_blacklist(monkeypatch):
    async def _not_blacklisted(_token: str) -> bool:
        return False

    monkeypatch.setattr(
        "app.infrastructure.security.token_blacklist.blacklist.is_blacklisted",
        _not_blacklisted,
    )


@pytest.fixture(autouse=True)
def reset_rate_limiter_registry():
    from app.infrastructure.resilience.rate_limiter import RateLimiterRegistry

    RateLimiterRegistry._limiters.clear()
    yield
    RateLimiterRegistry._limiters.clear()


def resolve_test_db_url(url: str | None) -> str:
    """Integration test DB URL'ini doğrula.

    Guard 1: TEST_DATABASE_URL zorunlu — dev DB'ye (lojinext_db) düşen eski
    fallback kaldırıldı; async_db_engine bağlandığı DB'de DROP SCHEMA public
    CASCADE çalıştırdığı için yanlış hedef veri kaybı demek.
    Guard 2: veritabanı adı 'test' içermeli — dev/prod'a yanlışlıkla işaret
    eden explicit URL'leri de reddeder.
    """
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL env var zorunlu — integration testler explicit "
            "bir TEST veritabanı ister (örn. postgresql+asyncpg://postgres:"
            "postgres@localhost:5432/lojinext_test). Dev DB fallback'i veri "
            "kaybına yol açtığı için kaldırıldı."
        )
    from sqlalchemy.engine import make_url

    db_name = make_url(url).database or ""
    if "test" not in db_name.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL '{db_name}' veritabanına işaret ediyor — adı "
            "'test' içermeyen DB'lere şema reset'i reddedilir (DROP SCHEMA "
            "public CASCADE koruması)."
        )
    return url


@pytest.fixture(scope="session")
def temp_db_url():
    return resolve_test_db_url(os.getenv("TEST_DATABASE_URL"))


@pytest.fixture(scope="session")
async def async_db_engine(temp_db_url):
    # NullPool: never reuse connections across tests. The default async
    # QueuePool can hand a later test a pooled connection left in an aborted
    # ("current transaction is aborted" / PendingRollbackError) state by an
    # earlier test that raised mid-flush — surfacing as a non-deterministic
    # "ERROR at setup" on whichever test happens to check that connection out.
    # NullPool disposes each connection on return, so every test starts on a
    # fresh backend connection. It also eliminates the "garbage collector is
    # trying to clean up non-checked-in connection" / "Event loop is closed"
    # teardown noise from pooled async connections outliving the event loop.
    engine = create_async_engine(
        temp_db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"command_timeout": 10},
    )

    # Initialize the schema through ORM metadata.
    async with engine.begin() as conn:
        # Set UTF-8 encoding for the session
        await conn.execute(text("SET client_encoding TO 'UTF8'"))

        # Terminate any other connections to allow schema drop
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

        # Dedicated test database: schema reset is faster and more deterministic
        # than metadata-driven drop_all on the full graph.
        # Drop the schema completely to avoid any corrupt data from SQL_ASCII encoding
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

        # Attempt to activate PostGIS via SAVEPOINT so a failure does NOT abort
        # the current transaction block.  Falls back to LargeBinary for the one
        # geometry column (RotaKalibrasyon.hedef_path) on plain PostgreSQL
        # installations without the extension.
        postgis_ok = False
        await conn.execute(text("SAVEPOINT _postgis_probe"))
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.execute(text("RELEASE SAVEPOINT _postgis_probe"))
            postgis_ok = True
        except Exception:
            await conn.execute(text("ROLLBACK TO SAVEPOINT _postgis_probe"))

        if not postgis_ok:
            import app.database.models as _db_models

            _db_models._LINESTRING_TYPE = LargeBinary()
            # Patch column types and remove auto-created GiST indexes so
            # create_all does not try to build a spatial index on bytea.
            for table in Base.metadata.tables.values():
                geo_col_names: set = set()
                for col in table.columns:
                    if col.type.__class__.__name__ in ("Geometry", "Geography"):
                        col.type = LargeBinary()
                        geo_col_names.add(col.name)
                # Drop any index that touches a patched geometry column
                if geo_col_names:
                    stale = [
                        idx
                        for idx in list(table.indexes)
                        if any(c.name in geo_col_names for c in idx.columns)
                    ]
                    for idx in stale:
                        table.indexes.discard(idx)

        # Create PostgreSQL enum types required by error monitoring tables.
        # These are defined with create_type=False in models.py so Alembic owns
        # them in production, but the test DB needs them before create_all runs.
        await conn.execute(
            text(
                "DO $$ BEGIN "
                "CREATE TYPE error_layer AS ENUM "
                "('db','celery','api','service','frontend','external','security','ml'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
        )
        await conn.execute(
            text(
                "DO $$ BEGIN "
                "CREATE TYPE error_severity AS ENUM "
                "('critical','error','warning','info'); "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
        )
        await conn.run_sync(Base.metadata.create_all)
        # Test parity: the stats endpoint expects the PostgreSQL materialized view.
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv"))
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
        # Test parity: error stats endpoint expects this materialized view.
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS error_hourly_stats"))
        await conn.execute(
            text("""
            CREATE MATERIALIZED VIEW error_hourly_stats AS
            SELECT
                date_trunc('hour', occurred_at) AS hour,
                layer,
                severity,
                COUNT(*) AS event_count
            FROM error_occurrences
            WHERE occurred_at > now() - INTERVAL '24 hours'
            GROUP BY 1, 2, 3
        """)
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX idx_error_hourly_stats "
                "ON error_hourly_stats(hour, layer, severity)"
            )
        )

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_db_engine, temp_db_url, monkeypatch):
    AsyncTestingSessionLocal = async_sessionmaker(
        bind=async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    session = AsyncTestingSessionLocal()

    # Monkeypatch components that rely on the global pool.
    # The wrapper prevents components from closing the shared fixture session.
    class NonClosingSession:
        def __init__(self, session):
            self._session = session

        def __call__(self):
            return self

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # Let the fixture close the session.
            pass

        def __getattr__(self, name):
            return getattr(self._session, name)

    wrapper = NonClosingSession(session)
    monkeypatch.setattr("app.database.connection.AsyncSessionLocal", wrapper)
    monkeypatch.setattr("app.database.unit_of_work.AsyncSessionLocal", wrapper)

    # Sync support
    sync_url = temp_db_url.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url, pool_pre_ping=True)
    SyncTestingSessionLocal = sessionmaker(
        bind=sync_engine, autocommit=False, autoflush=False
    )
    monkeypatch.setattr(
        "app.database.connection.SyncSessionLocal", SyncTestingSessionLocal
    )

    # Clear all user tables before each test so the session-scoped schema
    # stays clean.
    #
    # Use DELETE (ROW EXCLUSIVE) instead of TRUNCATE (ACCESS EXCLUSIVE).
    # With pytest-asyncio's session-scoped event loop, a concurrent async
    # coroutine (the previous test's SELECT still in-flight at an await point)
    # holds ACCESS SHARE.  TRUNCATE's ACCESS EXCLUSIVE conflicts with ACCESS
    # SHARE → deadlock.  DELETE's ROW EXCLUSIVE is compatible with ACCESS SHARE,
    # so the two can coexist without deadlocking.
    #
    # Delete in reverse-topological order to satisfy FK constraints.
    # Sequences are reset separately so IDs stay predictable.
    user_tables = [
        t.name
        for t in Base.metadata.sorted_tables
        if not t.name.startswith("spatial_ref_sys")
    ]
    if user_tables:
        for table_name in reversed(user_tables):
            await session.execute(text(f'DELETE FROM "{table_name}"'))
        # Reset all sequences in the public schema so IDs stay deterministic.
        await session.execute(
            text(
                "SELECT setval(quote_ident(schemaname) || '.' || quote_ident(sequencename), 1, false) "
                "FROM pg_sequences WHERE schemaname = 'public'"
            )
        )
        await session.commit()

    reset_all_singletons()
    try:
        yield session
    finally:
        await session.close()
        reset_all_singletons()


# --- Repository fixtures ---


@pytest.fixture
def arac_repo(db_session):
    from app.database.repositories.arac_repo import AracRepository

    return AracRepository(session=db_session)


@pytest.fixture
def sefer_repo(db_session):
    from app.database.repositories.sefer_repo import SeferRepository

    return SeferRepository(session=db_session)


@pytest.fixture
def yakit_repo(db_session):
    from app.database.repositories.yakit_repo import YakitRepository

    return YakitRepository(session=db_session)


@pytest.fixture
def sofor_repo(db_session):
    from app.database.repositories.sofor_repo import SoforRepository

    return SoforRepository(session=db_session)


@pytest.fixture
def analiz_repo(db_session):
    from app.database.repositories.analiz_repo import AnalizRepository

    return AnalizRepository(session=db_session)


@pytest.fixture
def dorse_repo(db_session):
    from app.database.repositories.dorse_repo import DorseRepository

    return DorseRepository(session=db_session)


# --- Service fixtures ---


@pytest.fixture
def arac_service(db_session):
    from app.core.services.arac_service import get_arac_service

    return get_arac_service()


@pytest.fixture
def sofor_service(db_session):
    from app.core.services.sofor_service import get_sofor_service

    return get_sofor_service()


@pytest.fixture
def sefer_service(db_session, mock_event_bus):
    from app.core.services.sefer_service import SeferService
    from app.database.repositories.sefer_repo import SeferRepository

    return SeferService(
        repo=SeferRepository(session=db_session), event_bus=mock_event_bus
    )


@pytest.fixture
def mock_event_bus():
    bus = Mock()
    bus.publish = Mock()
    bus.publish_async = AsyncMock()
    bus.subscribe = Mock()
    bus.unsubscribe = Mock()
    return bus


@pytest.fixture
def yakit_service(db_session):
    from app.core.services.yakit_service import get_yakit_service

    return get_yakit_service()


@pytest.fixture
def report_service(db_session):
    from app.core.services.report_service import ReportService

    return ReportService(session=db_session)


@pytest.fixture
def analiz_service(db_session):
    from app.core.services.analiz_service import get_analiz_service

    return get_analiz_service()


@pytest.fixture
def dashboard_service(db_session):
    from app.core.services.dashboard_service import get_dashboard_service

    return get_dashboard_service()


# --- Sample data fixtures ---


@pytest.fixture
def sample_arac_data():
    return {
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 30.5,
    }


@pytest.fixture
def sample_sofor_data():
    return {
        "ad_soyad": "Ahmet Yilmaz",
        "telefon": "0532 123 45 67",
        "ehliyet_sinifi": "E",
        "ise_baslama_tarihi": date.today(),
    }


@pytest.fixture
def sample_sefer_data():
    return {
        "arac_id": 1,
        "sofor_id": 1,
        "tarih": date.today(),
        "mesafe_km": 450,
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "baslangic_km": 100000,
        "bitis_km": 100450,
        "baslangic_tarihi": datetime.now(timezone.utc),
        "bitis_tarihi": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_yakit_data():
    return {
        "arac_id": 1,
        "tarih": date.today(),
        "litre": Decimal("100.50"),
        "fiyat_tl": Decimal("40.25"),
        "km_sayac": 100500,
    }


@pytest.fixture
async def async_client(db_session):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def auth_headers():
    """Admin/Superuser auth headers for tests via virtual super-admin token."""
    from datetime import timedelta

    from app.config import settings
    from app.core.security import create_access_token

    token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True},
        expires_delta=timedelta(minutes=30),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_auth_headers(auth_headers):
    return auth_headers


@pytest.fixture
async def async_superuser_token_headers(auth_headers):
    """Alias for admin_auth_headers — used by app/tests/integration tests."""
    return auth_headers


@pytest.fixture
async def normal_auth_headers(db_session):
    """Normal user auth headers for tests - Ensures testuser exists in DB"""
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.security import create_access_token, get_password_hash
    from app.database.models import Kullanici, Rol

    # Ensure role exists
    role_result = await db_session.execute(select(Rol).where(Rol.ad == "izleyici"))
    role = role_result.scalar_one_or_none()
    if not role:
        role = Rol(ad="izleyici", yetkiler={"sefer:read": True})
        db_session.add(role)
        await db_session.flush()

    # Ensure test user exists
    result = await db_session.execute(
        select(Kullanici).where(Kullanici.email == "testuser@lojinext.test")
    )
    user = result.scalar_one_or_none()

    if not user:
        user = Kullanici(
            email="testuser@lojinext.test",
            sifre_hash=get_password_hash("userpassword"),
            ad_soyad="Regular User",
            rol_id=role.id,
            aktif=True,
        )
        db_session.add(user)
        await db_session.commit()

    token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=30),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def no_trip_read_auth_headers(db_session):
    """Auth headers for a user that does not have sefer:read permission."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.security import create_access_token, get_password_hash
    from app.database.models import Kullanici, Rol

    role_name = "kisitli"
    role_result = await db_session.execute(select(Rol).where(Rol.ad == role_name))
    role = role_result.scalar_one_or_none()
    if not role:
        role = Rol(ad=role_name, yetkiler={"dashboard:read": True})
        db_session.add(role)
        await db_session.flush()

    user_email = "noread@lojinext.test"
    result = await db_session.execute(
        select(Kullanici).where(Kullanici.email == user_email)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = Kullanici(
            email=user_email,
            sifre_hash=get_password_hash("userpassword"),
            ad_soyad="No Read User",
            rol_id=role.id,
            aktif=True,
        )
        db_session.add(user)
    elif user.rol_id != role.id:
        user.rol_id = role.id

    await db_session.commit()

    token = create_access_token(
        data={"sub": user_email},
        expires_delta=timedelta(minutes=30),
    )
    return {"Authorization": f"Bearer {token}"}
