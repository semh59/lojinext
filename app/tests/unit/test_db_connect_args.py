"""_build_async_connect_args — async-engine connect_args (ARCH-016 follow-up)."""

from __future__ import annotations

import pytest

from v2.modules.platform_infra.database.connection import _build_async_connect_args

pytestmark = pytest.mark.unit


def test_postgresql_dev_sets_command_timeout_only():
    args = _build_async_connect_args("postgresql+asyncpg", "dev", 60.0, False)
    assert args == {"command_timeout": 60.0}


def test_postgresql_prod_sets_timeout_and_ssl():
    args = _build_async_connect_args("postgresql+asyncpg", "prod", 30.0, False)
    assert args == {"command_timeout": 30.0, "ssl": "require"}


def test_command_timeout_zero_disables_it():
    # 0 = off → no command_timeout key; prod still requires ssl.
    assert _build_async_connect_args("postgresql+asyncpg", "prod", 0, False) == {
        "ssl": "require"
    }
    assert _build_async_connect_args("postgresql", "dev", 0, False) == {}


def test_non_postgresql_driver_gets_empty_args():
    # aiosqlite / sqlite reject command_timeout & ssl kwargs — must stay empty.
    assert _build_async_connect_args("sqlite+aiosqlite", "prod", 60.0, False) == {}
    assert _build_async_connect_args("sqlite", "dev", 60.0, False) == {}


def test_pgbouncer_forces_anonymous_prepared_statements():
    # Tier E madde 30: statement_cache_size=0 alone is NOT enough — SQLAlchemy's
    # asyncpg dialect still issues NAMED prepares even with caching off, which
    # collide across pooled backend connections under PgBouncer transaction
    # pooling. prepared_statement_name_func must force anonymous ("") prepares.
    args = _build_async_connect_args("postgresql+asyncpg", "dev", 60.0, True)
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_cache_size"] == 0
    assert args["prepared_statement_name_func"]() == ""


def test_pgbouncer_off_omits_prepared_statement_overrides():
    args = _build_async_connect_args("postgresql+asyncpg", "dev", 60.0, False)
    assert "prepared_statement_name_func" not in args
    assert "statement_cache_size" not in args
