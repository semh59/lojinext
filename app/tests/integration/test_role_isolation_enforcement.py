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

from v2.modules.platform_infra.database.module_role import module_role_scope

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
