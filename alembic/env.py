import io
import os
import sys

# Set UTF-8 encoding for Windows console compatibility
if sys.stdout.encoding is None or sys.stdout.encoding.lower() == "ascii":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context

# PROJE AYARLARI
# Mevcut dizini sys.path'e ekle (app paketini bulabilmek için)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ALEMBIC_DIR = os.path.abspath(os.path.dirname(__file__))
ACTIVE_VERSION_DIR = os.path.join(ALEMBIC_DIR, "versions")

# models.py bölünmesi (dalga 16, task #58): tablo sınıfları taşındıkça
# v2/modules/<name>/infrastructure/models.py'ye gidiyor. Bu dosyalar aynı
# paylaşılan Base'i (v2.modules.shared_kernel.infrastructure.base) kullanır
# ama sınıfları Base.metadata'ya kaydettirmek için import EDİLMİŞ olmaları
# gerekir — aksi halde alembic bu tabloları "silinmiş" sanır (autogenerate/
# `alembic check` DROP TABLE üretir). Her yeni modül taşındığında buraya
# eklenmeli.
import v2.modules.admin_platform.infrastructure.models  # noqa: E402,F401
import v2.modules.anomaly.infrastructure.models  # noqa: E402,F401
import v2.modules.auth_rbac.infrastructure.models  # noqa: E402,F401
import v2.modules.driver.infrastructure.models  # noqa: E402,F401
import v2.modules.fleet.infrastructure.models  # noqa: E402,F401
import v2.modules.fuel.infrastructure.models  # noqa: E402,F401
import v2.modules.import_excel.infrastructure.models  # noqa: E402,F401
import v2.modules.location.infrastructure.models  # noqa: E402,F401
import v2.modules.notification.infrastructure.models  # noqa: E402,F401
import v2.modules.prediction_ml.infrastructure.models  # noqa: E402,F401
import v2.modules.reports.infrastructure.models  # noqa: E402,F401
import v2.modules.route_simulation.infrastructure.models  # noqa: E402,F401
import v2.modules.shared_kernel.infrastructure.error_monitoring_models  # noqa: E402,F401
import v2.modules.shared_kernel.infrastructure.outbox  # noqa: E402,F401
import v2.modules.trip.infrastructure.models  # noqa: E402,F401
from app.config import settings
from v2.modules.shared_kernel.infrastructure.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


# Dinamik URL set et (Alembic sync çalıştığı için asenkron kısımları temizle).
# asyncpg query parametreleri (ör. ?ssl=disable) psycopg2 tarafından
# reddedildiğinden URL'in query kısmı tamamen düşürülür.
def _to_sync_url(url: str) -> str:
    url = url.replace("+asyncpg", "").replace("+aiosqlite", "")
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


sync_url = _to_sync_url(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", sync_url)
config.set_main_option("version_locations", ACTIVE_VERSION_DIR)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# [B-03] Naming Convention Fix
# Ensures consistent index/constraint names across different database providers
# and prevents migration errors during schema changes.
target_metadata = Base.metadata
target_metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _include_object(obj, name, type_, reflected, compare_to):
    """Exclude objects that Alembic cannot autogenerate but that legitimately exist in the DB.

    - Partition child tables (e.g. error_occurrences_2026_05) are created by
      explicit SQL in migrations; Alembic sees them as orphan tables.
    - Materialized views are not in SQLAlchemy metadata at all.
    """
    if type_ == "table" and reflected:
        # Skip partition child tables for error_occurrences
        if name.startswith("error_occurrences_") and name != "error_occurrences":
            return False
        # Skip materialized views reported as tables (older SQLAlchemy/Alembic combos)
        if name.endswith("_stats") or name.endswith("_mv"):
            return False
    return True


def _compare_type(
    context, inspected_column, metadata_column, inspected_type, metadata_type
):
    """Skip type comparisons for GeoAlchemy2 Geometry columns.

    On plain PostgreSQL (no PostGIS) the DB stores these as BYTEA; geoalchemy2
    registers its own autogenerate comparator that would flag every geometry
    column as changed on every run.  Returning False suppresses the diff.
    """
    try:
        from geoalchemy2 import Geometry as _Geo

        if isinstance(metadata_type, _Geo) or isinstance(inspected_type, _Geo):
            return False  # No change
    except ImportError:
        pass
    return None  # Fall through to default comparator


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=_compare_type,
        include_object=_include_object,
        include_schemas=True,
        version_table_schema="platform",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # FAZ2 (schema-per-module): the app's DB role has its persistent
        # search_path extended per schema-move migration (`ALTER ROLE
        # CURRENT_USER SET search_path = public, <schema>, ...`, see e.g.
        # `0047_import_excel_schema_move.py`) so its OWN raw-SQL call sites
        # keep resolving bare table names. But Postgres's `schema=None`
        # ("default schema") table enumeration is search_path-driven too —
        # so alembic's autogenerate/`check` comparison (which does one pass
        # for `schema=None` and one pass per named schema) would see moved
        # tables show up in BOTH the default-schema pass and their own
        # named-schema pass, a phantom duplicate that autogenerate reports
        # as a spurious drop (confirmed with a real Postgres instance).
        # Migrations here are already explicitly schema-qualified (`CREATE
        # SCHEMA`/`ALTER TABLE ... SET SCHEMA`/`ALTER INDEX <schema>.<name>`)
        # so they never rely on the expanded search_path — pin this
        # session to `public` only, for the reflection/comparison alembic
        # itself does.
        # Committed in its own mini-transaction — SQLAlchemy 2.0 Connections
        # auto-begin a transaction on first execute(), and leaving it open
        # (uncommitted) here would get silently ROLLED BACK when this `with`
        # block exits, taking every subsequent migration in this same run
        # down with it (found the hard way: a full `upgrade head` run
        # appeared to succeed — no error — but left an EMPTY database,
        # because `context.begin_transaction()` joined this already-open
        # transaction instead of owning a fresh one). Committing this one
        # statement immediately keeps it fully isolated from whatever
        # transaction alembic itself manages next.
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        # `version_table_schema="platform"` below means alembic writes its
        # OWN bookkeeping table as `platform.alembic_version`. On a brand
        # new database that schema doesn't exist yet — alembic does not
        # auto-create it, so bootstrapping revision 0001 from empty would
        # fail before anything else runs. Pre-create it unconditionally
        # (idempotent, harmless once 0060_platform_schema_move's own
        # `CREATE SCHEMA IF NOT EXISTS platform` also runs later in the
        # chain). This only covers fresh databases; an existing database
        # that already has data up to a pre-0060 revision needs the
        # documented two-phase cutover instead — see
        # `scripts/faz2_move_alembic_version_to_platform.py`.
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS platform"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=_compare_type,
            include_object=_include_object,
            include_schemas=True,
            # FAZ2 (schema-per-module), platform-schema dalgası (0060):
            # alembic_version taşındı (bkz. scripts/faz2_move_alembic_
            # version_to_platform.py) — bu satır alembic'in kendi versiyon
            # takibini "platform"a şema-nitelenmiş olarak yapmasını
            # sağlıyor. Yukarıdaki "SET search_path TO public" pinini
            # "platform" da içerecek şekilde GENİŞLETMEYE gerek yok:
            # version_table_schema verildiğinde alembic kendi Table
            # objesini HER ZAMAN "platform.alembic_version" olarak
            # şema-nitelenmiş üretir (search_path'e güvenmez) — pini
            # genişletmek yalnızca platform şemasındaki tabloların
            # `schema=None` enumeration geçişinde hayalet-duplicate
            # üretmesine yol açardı (yukarıdaki yorumun asıl kaçındığı
            # sorun). Bu değişiklik, "platform" şeması + alembic_version
            # taşındıktan SONRA canlıya alınmalı — bkz. cutover script'inin
            # kendi docstring'i.
            version_table_schema="platform",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
