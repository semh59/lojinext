"""FAZ2 Wave 2 pilot fixes #2/#3 — RETURNING needs SELECT + auth needs auth_rbac.

Two more real gaps found live during the same Wave 2 pilot as 0062
(2026-07-28), each surfacing only after the previous one was fixed:

#2: after 0062, creating a trip still failed with `permission denied for
table outbox_events`, despite `current_user` being confirmed as `m_trip`
and the INSERT grant being confirmed present (isolated with a raw asyncpg
repro to rule out an app-level bug). Root cause: SQLAlchemy's ORM does
`INSERT ... RETURNING <pk>` on every `flush()` to read back an
autoincrement primary key — Postgres genuinely requires SELECT on the
returned column(s) for this, INSERT privilege alone isn't enough.
`_write_exception_stmts` (role_grants.py) now grants table-wide SELECT
alongside INSERT — fixed for `m_trip` -> outbox_events AND, since this is
a structural DDL-generation fix (not a per-role patch), for the 5
pre-existing WriteExceptions too (they'd have hit the exact same wall the
moment their own module gets wired).

#3: after #2, the broader RBAC/idempotency/API-contract test suites (not
just the manual super-admin pilot smoke-test, which has its own
break-glass fallback masking this) still failed: EVERY protected
endpoint's `get_current_user` dependency reads `auth_rbac.kullanicilar` to
resolve the JWT's user id, on whatever role is active for that request —
not module-specific at all, every module role needs it. `READER_SELECT_GRANTS`
now grants every module role (except `m_auth_rbac`, which owns the schema,
and `m_ops`, which already gets ALL) SELECT on `auth_rbac`.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0063_faz2_returning_fix
Revises: 0062_faz2_trip_role_grants_fix
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0063_faz2_returning_fix"
down_revision: Union[str, Sequence[str], None] = "0062_faz2_trip_role_grants_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
