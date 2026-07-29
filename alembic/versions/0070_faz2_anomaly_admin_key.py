"""FAZ2 Wave 2 pilot fix #10 — m_anomaly grant gaps (6 found).

Found live during the anomaly-module pilot (2026-07-29), via a
comprehensive public.py cross-module audit performed BEFORE wiring, PLUS
real HTTP testing that surfaced cascading issues the static audit missed
(buried repository methods and in-process event-bus subscriber chains).
`m_anomaly` already had `trip`, `driver`, `fleet` correctly set in Wave 1
(covering `get_anomaly_alarm_context()`'s unqualified anomalies/seferler/
soforler/araclar JOIN, `get_fleet_insights.py`'s uow.sefer_repo/arac_repo
reads, and `attribute_loss.override_attribution()`'s WriteException on
trip.seferler). Six additional gaps found in this pilot:

1. **admin_platform (READER_SELECT_GRANTS)**: `detect_anomaly.py`'s
   `detect_consumption_anomalies()` calls `admin_platform.public.
   get_runtime_float("ANOMALY_Z_THRESHOLD", ...)` (reads
   `admin_platform.sistem_konfig`) — found via the direct public.py audit.

2. **location + fuel (READER_SELECT_GRANTS)**: `GET /anomalies/fleet/
   insights` -> `get_fleet_insights.py`'s
   `uow.sefer_repo.get_cost_leakage_stats()` runs 3 raw SQL queries
   INSIDE TRIP'S OWN REPOSITORY that unqualified-touch location's
   lokasyonlar (JOIN) and fuel's yakit_alimlari (separate query) —
   invisible from a public.py import grep since they're buried inside
   another module's repository method, not anomaly's own code. Found via
   real HTTP testing (a class of transitive dependency beyond the direct
   public.py audit).

3. **notification (READER_SELECT_GRANTS)**: `attribute_loss.
   override_attribution()` publishes SEFER_UPDATED SYNCHRONOUSLY
   (in-process `get_event_bus().publish_async(...)`, not via the outbox
   relay) — notification's subscriber handler for that event runs INLINE
   in the same async task/request, inheriting m_anomaly's SET LOCAL ROLE,
   and needs to read `notification.bildirim_kurallari`. A new class of
   transitive dependency: in-process (non-outbox) event publishing
   propagates the publisher's role into every synchronous subscriber's
   queries.

4. **seferler.updated_at (WRITE_EXCEPTIONS column list)**: the Sefer ORM
   model's `updated_at` column carries a Python-side
   `onupdate=get_utc_now`, so SQLAlchemy auto-appends it to EVERY UPDATE
   — the original Wave 1 column list missed this (a pre-existing gap, not
   a regression from this pilot's own changes).

5. **seferler.tahmini_tuketim (WRITE_EXCEPTIONS column list)**: the same
   SEFER_UPDATED event from #3 also triggers prediction_ml's
   `PhysicsRecalculationHandler`, which writes `tahmini_tuketim` back to
   the same row — same in-process subscriber-inherits-publisher's-role
   mechanism as #3, but on the write side.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0070_faz2_anomaly_admin_key
Revises: 0069_faz2_route_sim_grants
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0070_faz2_anomaly_admin_key"
down_revision: Union[str, Sequence[str], None] = "0069_faz2_route_sim_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
