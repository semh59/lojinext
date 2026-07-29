"""FAZ2 Wave 2 pilot fix #5 — m_driver missing fleet/anomaly READER_SELECT_GRANTS.

Found live during the driver-module pilot (2026-07-29). `GET /coaching/
{id}/insights` (driver's coaching flow, via `DriverCoachingEngine` ->
`get_anomaly_detector().get_recent_anomalies(...)`) crashed with
``UndefinedTableError: relation "anomalies" does not exist`` once role
enforcement was actually turned on for driver's routes.

Root cause: `anomaly/infrastructure/anomaly_repository.py`'s
`get_anomalies()` runs one raw-SQL query joining four unqualified table
names — `anomalies` (anomaly schema), `seferler` (trip schema, already
granted to m_driver), `soforler` (driver's own schema, no grant needed),
and `araclar` (fleet schema, NOT granted). `m_driver` was only granted
`trip` in `READER_SELECT_GRANTS` — missing both `fleet` and `anomaly`.
Without USAGE on those schemas, m_driver can't resolve the unqualified
names via search_path at all (Postgres reports "relation does not exist",
not "permission denied").

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0065_faz2_driver_role_grants_fix
Revises: 0064_faz2_audit_log_universal
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0065_faz2_driver_role_grants_fix"
down_revision: Union[str, Sequence[str], None] = "0064_faz2_audit_log_universal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
