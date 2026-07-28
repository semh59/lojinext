"""FAZ2 Wave 2 pilot fix #4 — admin_audit_log needs to be reachable by every role.

Found live during the fleet-module pilot (2026-07-28), after 0062/0063's
fixes: fleet's own tests failed with
`InFailedSQLTransactionError: current transaction is aborted` on a request
that itself never touched anything outside fleet's own schema.

Root cause: `platform_infra.audit.audit_logger`'s `@audit_log`/
`log_audit_event` writes an unqualified `INSERT INTO admin_audit_log (...)`
on EVERY module's write endpoints (not just admin_platform's own) — this
table lives in the `admin_platform` schema. A role with no USAGE grant on
that schema can't resolve the unqualified name via search_path at all —
Postgres reports this as "relation does not exist" (not "permission
denied": without USAGE, a role can't even see that the schema exists).

This alone is caught and logged by audit_logger's own try/except, but the
audit-persist code's `session.begin_nested()` SAVEPOINT guard (meant to
protect the caller's real transaction from exactly this kind of failure)
only applies when `session.in_transaction()` is already true at that point
— fleet's smart-delete flow calls `uow.commit()` inline *before* the audit
decorator's own post-processing runs, so by then there's no active
transaction to protect, and the (real, role-driven) UndefinedTableError
poisons the shared session for the rest of the request/test with no
recovery path.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0064_faz2_audit_log_universal
Revises: 0063_faz2_returning_fix
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0064_faz2_audit_log_universal"
down_revision: Union[str, Sequence[str], None] = "0063_faz2_returning_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
