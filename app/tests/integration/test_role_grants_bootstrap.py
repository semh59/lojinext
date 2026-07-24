"""FAZ2 Wave 1 — verifies the role/grant matrix is actually correct in a real
Postgres instance. This is Wave 1's OWN verification, not an enforcement
test: nothing here ever calls `SET ROLE`/`SET LOCAL ROLE` — the application
still runs under its single login role. Wave 2 (a separate, later, DURMA
NOKTASI-gated task) adds the enforcement test that actually proves
`permission denied` on a wrong-module write attempt.

Driven directly from `v2/modules/platform_infra/database/role_grants.py`'s
own data structures (the single source of truth for the matrix), so this
test automatically tracks any future change to that module without needing
separate hand-maintenance.
"""

import pytest
from sqlalchemy import text

from v2.modules.platform_infra.database.role_grants import (
    _ALL_MODULE_SCHEMAS,
    ALL_ROLES,
    MODULE_SCHEMA_ROLES,
    OPS_ROLE,
    READER_SELECT_GRANTS,
    WRITE_EXCEPTIONS,
)

pytestmark = pytest.mark.integration

_WRITE_ONLY_PRIVS = {"INSERT", "UPDATE", "DELETE"}


async def _table_privileges(db_session, role: str, schema: str) -> dict[str, set[str]]:
    """{table_name: {privilege_type, ...}} for every table-level grant this
    role holds in this schema (does not distinguish column-scoped grants —
    see `_column_privileges` for that)."""
    result = await db_session.execute(
        text(
            "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = :role AND table_schema = :schema"
        ),
        {"role": role, "schema": schema},
    )
    out: dict[str, set[str]] = {}
    for row in result:
        out.setdefault(row.table_name, set()).add(row.privilege_type)
    return out


async def _column_privileges(
    db_session, role: str, schema: str, table: str
) -> dict[str, set[str]]:
    """{column_name: {privilege_type, ...}}."""
    result = await db_session.execute(
        text(
            "SELECT column_name, privilege_type FROM information_schema.role_column_grants "
            "WHERE grantee = :role AND table_schema = :schema AND table_name = :table"
        ),
        {"role": role, "schema": schema, "table": table},
    )
    out: dict[str, set[str]] = {}
    for row in result:
        out.setdefault(row.column_name, set()).add(row.privilege_type)
    return out


async def test_all_17_roles_exist(db_session):
    result = await db_session.execute(text("SELECT rolname FROM pg_roles"))
    live_roles = {row.rolname for row in result}
    missing = set(ALL_ROLES) - live_roles
    assert not missing, f"Roles missing from DB: {sorted(missing)}"


async def test_all_roles_are_nologin(db_session):
    result = await db_session.execute(
        text("SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname = ANY(:roles)"),
        {"roles": ALL_ROLES},
    )
    non_nologin = [row.rolname for row in result if row.rolcanlogin]
    assert not non_nologin, (
        f"These FAZ2 roles unexpectedly allow login (should all be NOLOGIN, "
        f"Wave 2 enforcement uses SET LOCAL ROLE, not real connections): {non_nologin}"
    )


@pytest.mark.parametrize("schema,role", sorted(MODULE_SCHEMA_ROLES.items()))
async def test_module_role_has_all_on_own_schema(db_session, schema, role):
    tables_result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
        {"schema": schema},
    )
    tables = [row.table_name for row in tables_result]
    assert tables, f"Schema {schema!r} has no tables — nothing to verify"

    privileges = await _table_privileges(db_session, role, schema)
    for table in tables:
        got = privileges.get(table, set())
        missing = {"SELECT", "INSERT", "UPDATE", "DELETE"} - got
        assert not missing, f"{role} missing {missing} on {schema}.{table} (own schema should be ALL)"


@pytest.mark.parametrize(
    "role,schema",
    sorted((role, schema) for role, schemas in READER_SELECT_GRANTS.items() for schema in schemas),
)
async def test_reader_has_select_only_on_granted_schema(db_session, role, schema):
    tables_result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
        {"schema": schema},
    )
    tables = [row.table_name for row in tables_result]
    assert tables, f"Schema {schema!r} has no tables — nothing to verify"

    write_exception_tables = {
        exc.table for exc in WRITE_EXCEPTIONS if exc.role == role and exc.schema == schema
    }

    privileges = await _table_privileges(db_session, role, schema)
    for table in tables:
        got = privileges.get(table, set())
        assert "SELECT" in got, f"{role} missing SELECT on {schema}.{table}"
        if table in write_exception_tables:
            # This table has its own narrower column-scoped write exception
            # test below (test_write_exception_is_precisely_scoped) — a
            # table-level INSERT/UPDATE/DELETE grant here would still be a
            # bug (the exception should be column-scoped, not table-wide),
            # so still assert none of those three appear at the table level.
            continue
        extra = got & _WRITE_ONLY_PRIVS
        assert not extra, (
            f"{role} has unexpected write privilege(s) {extra} on "
            f"{schema}.{table} (should be SELECT-only, no write exception registered here)"
        )


@pytest.mark.parametrize("exc", WRITE_EXCEPTIONS, ids=lambda e: f"{e.role}-{e.schema}.{e.table}")
async def test_write_exception_is_precisely_scoped(db_session, exc):
    if exc.columns is None:
        # Table-scoped (INSERT/DELETE — Postgres doesn't support column-scoped
        # INSERT restricted-to-columns in the same way; these are deliberately
        # whole-table per the plan's import_excel bulk-write case).
        privileges = await _table_privileges(db_session, exc.role, exc.schema)
        got = privileges.get(exc.table, set())
        missing = set(exc.privileges) - got
        assert not missing, f"{exc.role} missing {missing} on {exc.schema}.{exc.table}"
        return

    # Column-scoped: every listed column must carry every listed privilege,
    # and no OTHER column may carry any of these privileges (proves the
    # grant is actually narrow, not accidentally promoted to the whole table).
    col_privileges = await _column_privileges(db_session, exc.role, exc.schema, exc.table)
    for column in exc.columns:
        got = col_privileges.get(column, set())
        missing = set(exc.privileges) - got
        assert not missing, f"{exc.role} missing {missing} on {exc.schema}.{exc.table}.{column}"

    leaked_columns = {
        column
        for column, privs in col_privileges.items()
        if column not in exc.columns and (privs & set(exc.privileges))
    }
    assert not leaked_columns, (
        f"{exc.role} has {exc.privileges} on unexpected column(s) of "
        f"{exc.schema}.{exc.table} (grant leaked beyond the intended columns): {leaked_columns}"
    )


async def test_m_ops_has_all_on_every_module_schema(db_session):
    for schema in _ALL_MODULE_SCHEMAS:
        tables_result = await db_session.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
            ),
            {"schema": schema},
        )
        tables = [row.table_name for row in tables_result]
        if not tables:
            continue
        privileges = await _table_privileges(db_session, OPS_ROLE, schema)
        for table in tables:
            got = privileges.get(table, set())
            missing = {"SELECT", "INSERT", "UPDATE", "DELETE"} - got
            assert not missing, f"{OPS_ROLE} missing {missing} on {schema}.{table}"
