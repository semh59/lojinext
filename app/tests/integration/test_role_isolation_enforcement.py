"""FAZ2 Wave 2 — proves `SET LOCAL ROLE` (via `module_role_scope` +
`connection.py`'s `after_begin` listener) actually enforces the Wave 1
grant matrix at the database level: a session scoped to the wrong
module's role gets a real `permission denied`, and a session scoped to
its own module's role can read/write normally.

Uses a fresh engine/session bound directly to `temp_db_url` instead of the
shared `db_session` fixture: the fixture's session begins its cleanup
transaction before the test body runs (with no role set), so
`module_role_scope` entered inside the test body would be too late for
`after_begin` to see it on that shared session. A fresh session's first
transaction begins strictly after the role is set, matching how real
request/task code will use `AsyncSessionLocal()` once Wave 2's wiring
step lands.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from v2.modules.platform_infra.database.module_role import (
    _module_role,
    module_role_scope,
    open_role_scoped_session,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def fresh_session_factory(temp_db_url, db_session):
    """`db_session` isn't used directly — it's what triggers the
    session-scoped `async_db_engine` fixture's one-time schema/table/role
    creation (`Base.metadata.create_all` + `apply_role_grants_async`) that
    this fresh, separately-created engine depends on existing already."""
    engine = create_async_engine(temp_db_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    yield factory
    await engine.dispose()


async def test_wrong_module_write_is_denied(fresh_session_factory):
    """m_trip scoped session writing into fleet's schema -> permission denied."""
    with module_role_scope("m_trip"):
        async with fresh_session_factory() as session:
            async with session.begin():
                with pytest.raises(DBAPIError, match="permission denied"):
                    await session.execute(
                        text(
                            "INSERT INTO fleet.araclar (plaka, marka, model, yil) "
                            "VALUES ('99 ZZ 99', 'enforcement-test', 'x', 2020)"
                        )
                    )


async def test_own_module_write_is_allowed(fresh_session_factory):
    """m_fleet scoped session writing into its OWN fleet schema -> succeeds."""
    with module_role_scope("m_fleet"):
        async with fresh_session_factory() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "INSERT INTO fleet.araclar (plaka, marka, model, yil) "
                        "VALUES ('99 YY 99', 'enforcement-test', 'x', 2020)"
                    )
                )
                count = (
                    await session.execute(
                        text(
                            "SELECT COUNT(*) FROM fleet.araclar WHERE plaka = '99 YY 99'"
                        )
                    )
                ).scalar_one()
                assert count == 1
                await session.rollback()


async def test_role_resets_after_transaction(fresh_session_factory):
    """`SET LOCAL ROLE`'s scope ends with the transaction — a later,
    unscoped session on the same engine is NOT stuck as m_trip."""
    with module_role_scope("m_trip"):
        async with fresh_session_factory() as session:
            async with session.begin():
                role = (await session.execute(text("SELECT current_user"))).scalar_one()
                assert role == "m_trip"

    async with fresh_session_factory() as session:
        async with session.begin():
            role = (await session.execute(text("SELECT current_user"))).scalar_one()
            assert role != "m_trip"


async def test_open_role_scoped_session_returns_scoped_session(temp_db_url, db_session):
    """`open_role_scoped_session` (the m_ops-script entry point) returns a
    session already running as the given role — end to end, no manual
    `module_role_scope` needed by the caller."""
    async with open_role_scoped_session("m_ops") as session:
        async with session.begin():
            role = (await session.execute(text("SELECT current_user"))).scalar_one()
            assert role == "m_ops"


async def test_write_exception_insert_with_returning_succeeds(fresh_session_factory):
    """Real regression found in the trip-module pilot (2026-07-28):
    `m_trip` scoped to `platform.outbox_events` (a WriteException, not its
    own schema) could INSERT but the ORM-style `RETURNING id` clause failed
    with `permission denied` even though `current_user` was confirmed
    `m_trip` and the plain INSERT grant was confirmed present — Postgres
    requires SELECT on a RETURNING column in addition to INSERT.
    `_write_exception_stmts` now grants both; this proves it end to end."""
    with module_role_scope("m_trip"):
        async with fresh_session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        text(
                            "INSERT INTO platform.outbox_events "
                            "(event_type, payload, correlation_id, created_at, "
                            "updated_at, processed, retry_count) "
                            "VALUES ('sefer_added', '{}', 'returning-test', "
                            "now(), now(), false, 0) "
                            "RETURNING id"
                        )
                    )
                ).scalar_one()
                assert row is not None


async def test_apply_module_role_listener_rejects_bypassed_unknown_role(
    fresh_session_factory,
):
    """Defense-in-depth check in `connection.py`'s `after_begin` listener:
    even if something sets the private ContextVar directly (bypassing
    `module_role_scope`'s own validation), the listener still refuses an
    unknown role instead of sending it to Postgres."""
    token = _module_role.set("m_totally_made_up")
    try:
        async with fresh_session_factory() as session:
            # `after_begin` only fires once a real connection is acquired for
            # the FIRST actual statement — entering `session.begin()` alone
            # (with no query) doesn't touch the database yet, so this needs
            # a real `execute()` to trigger the listener.
            with pytest.raises(ValueError, match="Refusing to SET LOCAL ROLE"):
                async with session.begin():
                    await session.execute(text("SELECT 1"))
    finally:
        _module_role.reset(token)
