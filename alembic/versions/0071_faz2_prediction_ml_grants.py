"""FAZ2 Wave 2 pilot fix #12 — m_prediction_ml grant gaps (6 found).

Found live during the prediction_ml-module pilot (2026-07-29), via a
comprehensive public.py cross-module audit performed BEFORE wiring, PLUS
real HTTP testing that surfaced 3 more gaps the static audit missed
(buried repository methods, same pattern as the anomaly pilot).
`m_prediction_ml` previously only had `fleet` (from `scheduler_task.py`).

READER_SELECT_GRANTS additions (6 schemas):

- `trip`: `predictions.py`'s GET endpoints directly ORM-query
  `trip.public.SeferORM` (aliased `Sefer`); `ensemble_service.py`'s
  `train_for_vehicle`/`predict_consumption` use `trip.public.
  get_sefer_repo`. Found via direct public.py audit.
- `driver`: `predictions.py` does `db.get(driver.public.Sofor, ...)`;
  `ensemble_service.py` calls `driver.public.get_driver_stats`. Found via
  direct public.py audit.
- `admin_platform`: `prediction_service.py` calls `admin_platform.public.
  get_runtime_float("VEHICLE_AGE_DEGRADATION_RATE", ...)` — same
  `sistem_konfig`-read pattern already fixed for m_location (0068),
  m_route_simulation (0069), and m_anomaly (0070). Found via direct
  public.py audit.
- `location`: found live via real HTTP testing (`POST /predictions/
  train/{arac_id}`) — trip's OWN `sefer_repo.get_for_training()` (a
  buried-repository-method case, same class as the m_anomaly pilot's
  `get_cost_leakage_stats` finding) unqualified-LEFT-JOINs `seferler`
  with location's `lokasyonlar` for route-difficulty enrichment.
- `fuel` + `anomaly`: found live via real HTTP testing (`GET /admin/
  pilot-status`) — `admin_pilot.py` runs raw unqualified
  `COUNT(*) FROM yakit_alimlari` (fuel) and `COUNT(*) FROM anomalies`
  (anomaly) directly in the route handler.

Separately, a genuine PRE-EXISTING bug (unrelated to role grants — would
crash under any role, including unrestricted access) was found and fixed
in the same pilot: `ensemble_service.py::train_for_vehicle` used
`self.arac_repo`/`self.sefer_repo` (process-lifetime singletons with no
bound session) instead of opening a `UnitOfWork`, unconditionally
crashing with "Database session not initialized" on every call — the
sibling method `predict_consumption` already used the correct
`uow.arac_repo`/`uow.dorse_repo` pattern when a `uow` is passed.
`train_for_vehicle` now opens its own `UnitOfWork` for its DB reads.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0071_faz2_prediction_ml_grants
Revises: 0070_faz2_anomaly_admin_key
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0071_faz2_prediction_ml_grants"
down_revision: Union[str, Sequence[str], None] = "0070_faz2_anomaly_admin_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
