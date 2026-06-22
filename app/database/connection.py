"""Database engines and session factories.

Public surface:
    engine                — async engine (asyncpg / aiosqlite)
    AsyncSessionLocal     — async session factory
    get_db()              — FastAPI dependency yielding AsyncSession
    session_scope()       — async context manager yielding AsyncSession

Sync wrapper (kept solely for `app.infrastructure.routing.openroute_client`,
which still issues blocking SQL inside threadpool calls). Targeted for
removal in Phase-2 once that client becomes async.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# ── Engine wiring ─────────────────────────────────────────────────────────────
_url = make_url(settings.DATABASE_URL)

# Force asyncpg for postgres URLs that omit the dialect.
if _url.drivername.startswith("postgresql") and "+asyncpg" not in _url.drivername:
    _url = _url.set(drivername="postgresql+asyncpg")


def _build_async_connect_args(
    drivername: str, environment: str, command_timeout_s: float
) -> dict:
    """asyncpg ``connect_args`` for the async engine.

    Adds a per-statement ``command_timeout`` (DoS backstop, ARCH-016 follow-up)
    and, in production, ``ssl=require``. Only applies to postgresql/asyncpg —
    other drivers (e.g. aiosqlite in tests) reject these kwargs, so they get
    an empty dict.
    """
    if not drivername.startswith("postgresql"):
        return {}
    args: dict = {}
    if command_timeout_s and command_timeout_s > 0:
        args["command_timeout"] = command_timeout_s
    if environment == "prod":
        args["ssl"] = "require"
    return args


_engine_kwargs = dict(
    echo=settings.SQL_ECHO,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,  # ARCH-005: configurable (default 40)
    max_overflow=settings.DB_MAX_OVERFLOW,  # ARCH-005: configurable (default 5)
    pool_timeout=60,  # Increased from 30 to reduce timeout errors
    pool_recycle=900,  # Reduced from 1800 to recycle idle connections more frequently
    pool_reset_on_return="rollback",  # Reset session state on return
)
_async_connect_args = _build_async_connect_args(
    _url.drivername, settings.ENVIRONMENT, settings.DB_COMMAND_TIMEOUT_S
)
if _async_connect_args:
    _engine_kwargs["connect_args"] = _async_connect_args

engine = create_async_engine(_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async session. Rolls back on exception, always closes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager: commit on success, rollback on error, always close."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Sync wrapper (DEPRECATED — Phase-2 removal) ───────────────────────────────
_sync_url = (
    _url.set(drivername=_url.drivername.replace("+asyncpg", ""))
    if "+asyncpg" in _url.drivername
    else _url
)
sync_engine = create_engine(
    _sync_url,
    echo=settings.SQL_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DB_SYNC_POOL_SIZE,  # ARCH-005: configurable (default 10)
    max_overflow=settings.DB_SYNC_MAX_OVERFLOW,  # ARCH-005: configurable (default 5)
    pool_timeout=30,
    pool_recycle=1800,
    **(
        {"connect_args": {"sslmode": "require"}}
        if settings.ENVIRONMENT == "prod"
        and _sync_url.drivername.startswith("postgresql")
        else {}
    ),
)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_session() -> Iterator[Session]:
    """Sync session — auto-commits on success, rolls back on error."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Legacy alias kept for `app.scripts.benchmark`.
get_connection = get_sync_session
