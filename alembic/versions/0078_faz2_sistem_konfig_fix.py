"""FAZ2 sistem_konfig schema mislabeling fix — m_anomaly + m_prediction_ml.

Found live (2026-07-30) IMMEDIATELY after pushing 0077 (the m_fuel/
m_notification fix): the "Combined coverage gate" was STILL failing at
91%, and the same run's Postgres log showed the exact same recurring
`permission denied for table sistem_konfig` errors, now traced to a much
older, broader bug: `SistemKonfig` (used by `admin_platform.public.
get_runtime_float`) despite living in `admin_platform/infrastructure/
models.py`, has `__table_args__ = {"schema": "platform"}` -- a genuinely
different schema from `entegrasyon_ayarlari`'s `"admin_platform"`.

Two PRE-EXISTING role_grants.py comments (written during the anomaly and
prediction_ml Wave 2 pilots, 2026-07-29 -- weeks before today's Celery
wiring) explicitly claimed the already-granted "admin_platform" schema
access "already fixed"/"same schema-wide grant" covered
`get_runtime_float`'s sistem_konfig read. It never did -- both modules'
`get_runtime_float` calls (`ANOMALY_Z_THRESHOLD` for anomaly,
`VEHICLE_AGE_DEGRADATION_RATE` for prediction_ml) have been silently
permission-denied (masked by `get_runtime_float`'s falls-back-to-default-
on-any-DB-error behavior) since those pilots landed -- this was a
genuinely pre-existing, wider-reaching bug than the m_fuel/m_notification
fix in 0077, just never surfaced because nothing until today's Celery
wiring + a full combined-coverage CI run happened to both exercise the
code path AND log the raw Postgres error where anyone would see it.

New schema added to READER_SELECT_GRANTS:
- `"m_anomaly": [..., "platform", ...]` (added alongside existing
  "admin_platform")
- `"m_prediction_ml": [..., "platform", ...]` (added alongside existing
  "admin_platform")

(`"m_fuel"` and `"m_notification"` were already fixed in 0077 -- this
migration is the same class of fix for the two OTHER get_runtime_float
callers.)

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0078_faz2_sistem_konfig_fix
Revises: 0077_faz2_fuel_notif_reader
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0078_faz2_sistem_konfig_fix"
down_revision: Union[str, Sequence[str], None] = "0077_faz2_fuel_notif_reader"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
