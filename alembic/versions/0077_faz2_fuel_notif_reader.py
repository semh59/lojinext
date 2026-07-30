"""FAZ2 Celery role-wiring fallout — m_fuel + m_notification reader grants.

Found live (2026-07-30) via the real CI Postgres log on the 1003cd1 push
(the previous import_excel grant fix): after that fix, the combined
coverage gate was STILL failing at 91%, and the same Postgres log showed
repeated `permission denied for table sistem_konfig` and `permission
denied for table araclar` errors throughout the whole test run — not a
single one-off, but recurring every few minutes, meaning a periodic
Celery beat task was hitting them.

Root cause: the FAZ2 Wave 2 Celery `task_prerun`/`task_postrun` role-
scoping wiring (f1de159) correctly restricts each mapped task to its
module's DB role for the first time -- exposing two grant gaps that were
invisible before that wiring existed (no role restriction meant no
permission-denied possible):

- `monitoring.fuel_coverage_check` (-> m_fuel) calls admin_platform.
  public.get_runtime_float("FUEL_COVERAGE_ALERT_THRESHOLD_PCT", ...),
  which reads SistemKonfig -- despite living in
  admin_platform/infrastructure/models.py, that table's own
  `__table_args__ = {"schema": "platform"}` puts it in the "platform"
  schema, not "admin_platform" (a different schema that entegrasyon_
  ayarlari lives in). m_fuel previously only had ["fleet", "trip"].
- `notifications.weekly_digest` (-> m_notification) calls reports.public.
  aggregate_today_triage(), which reads anomaly.anomalies (joined with
  fleet.araclar + trip.seferler), fuel.fuel_investigations (same join),
  a trip.seferler counter, and fleet.public.MaintenancePredictor()
  .predict_all() (fleet.araclar + fleet.arac_bakimlari + trip.seferler).
  m_notification previously had ZERO reader grants at all.

Neither task ever raised (both wrap the affected calls in try/except and
log-and-continue / fall back to a default), so no test failed -- the
errors only showed up in the raw Postgres log, and the combined coverage
gate dropped because the success-path branches after each failed read
never executed.

New READER_SELECT_GRANTS entries:
- `"m_fuel": ["fleet", "trip", "platform"]` (was `["fleet", "trip"]`)
- `"m_notification": ["fleet", "trip", "anomaly", "fuel"]` (was absent)

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0077_faz2_fuel_notif_reader
Revises: 0076_faz2_import_excel_reader
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0077_faz2_fuel_notif_reader"
down_revision: Union[str, Sequence[str], None] = "0076_faz2_import_excel_reader"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
