"""_build_async_connect_args — async-engine connect_args (ARCH-016 follow-up)."""

from __future__ import annotations

import pytest

from app.database.connection import _build_async_connect_args

pytestmark = pytest.mark.unit


def test_postgresql_dev_sets_command_timeout_only():
    args = _build_async_connect_args("postgresql+asyncpg", "dev", 60.0)
    assert args == {"command_timeout": 60.0}


def test_postgresql_prod_sets_timeout_and_ssl():
    args = _build_async_connect_args("postgresql+asyncpg", "prod", 30.0)
    assert args == {"command_timeout": 30.0, "ssl": "require"}


def test_command_timeout_zero_disables_it():
    # 0 = off → no command_timeout key; prod still requires ssl.
    assert _build_async_connect_args("postgresql+asyncpg", "prod", 0) == {
        "ssl": "require"
    }
    assert _build_async_connect_args("postgresql", "dev", 0) == {}


def test_non_postgresql_driver_gets_empty_args():
    # aiosqlite / sqlite reject command_timeout & ssl kwargs — must stay empty.
    assert _build_async_connect_args("sqlite+aiosqlite", "prod", 60.0) == {}
    assert _build_async_connect_args("sqlite", "dev", 60.0) == {}
