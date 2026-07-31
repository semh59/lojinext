"""FAZ2 Wave 2 pilot fixes #17/#18 — m_location route_paths UPDATE +
m_driver platform schema (sistem_konfig).

Found live via Sentry (2026-07-31), not CI: two pre-existing role-grant
gaps that CI's own test suite never exercised.

1. LOJINEXT-1E5 / LOJINEXT-17X (recurring since 2026-05-30):
   `RouteRepository.save_route()` (route_simulation/infrastructure/
   repository.py) checks `get_by_coords()` first and calls
   `self.update(existing["id"], **data)` when a bbox-tolerance match
   already exists, not just `create()`. 0067's WriteException only
   granted "INSERT" to m_location on route_simulation.route_paths (the
   cold-cache-miss path) -- a second `/locations/{id}/analyze` call for
   the same (or a nearby, within-tolerance) coordinate pair hits the
   UPDATE branch and was permission-denied. Now grants ("INSERT", "UPDATE").

2. LOJINEXT-1E3 (recurring since 2026-07-29): same schema-mislabeling bug
   class 0078 fixed for m_anomaly/m_prediction_ml (SistemKonfig lives in
   the "platform" schema, not "admin_platform"), just a third, missed
   caller -- driver/application/generate_coaching.py ->
   get_anomaly_detector() -> detect_consumption_anomalies() ->
   runtime_config.get_runtime_float("ANOMALY_Z_THRESHOLD") reads
   platform.sistem_konfig under m_driver's role (the coaching flow,
   not anomaly's own Celery task). Added "platform" to m_driver's
   READER_SELECT_GRANTS schema list.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0079_faz2_location_driver_grants
Revises: 0078_faz2_sistem_konfig_fix
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0079_faz2_location_driver_grants"
down_revision: Union[str, Sequence[str], None] = "0078_faz2_sistem_konfig_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
