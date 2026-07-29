"""FAZ2 Wave 2 pilot fix #13 — m_admin_platform grant gaps (5 found).

Found live during the admin_platform-module pilot (2026-07-29), via a
comprehensive public.py cross-module audit performed BEFORE wiring.
`m_admin_platform` previously had zero grants beyond the universal
`auth_rbac` entry.

READER_SELECT_GRANTS additions (5 schemas):

- `driver`: `telegram_bridge.py` (the Telegram bot bridge, called from
  `api/internal_routes.py`) calls `driver.public.get_sofor_repo`/
  `get_by_telegram_id` throughout.
- `trip`: `driver.public.get_by_sofor_id` is a driver function that itself
  queries `trip.seferler` directly (`infrastructure/
  driver_trip_queries.py`) -- a buried-repository-method case, same class
  found in prior pilots. `driver.public.SoforSeferPDFService` also reads
  `trip.seferler` (+ `driver.soforler`) for PDF generation.
- `fleet`: `telegram_bridge.py::report_driver_breakdown`'s
  `_arac_plaka()` reads `uow.arac_repo.get_by_id` (fleet).
- `anomaly`: `driver.public.get_driver_coaching_engine`'s
  `DriverCoachingEngine.generate_coaching` reads anomalies via
  `get_anomaly_detector().get_recent_anomalies`.
- `platform`: `application/error_events.py`'s admin-facing read surface
  over `error_events`/`error_hourly_stats` (write path owned by
  `platform_infra.monitoring`, tables live in the `platform` schema since
  `0060_platform_schema_move`). `admin_audit_log` itself is
  admin_platform's OWN table, needs no grant.

3 WriteExceptions:

- `trip.sefer_belgeler` INSERT: `telegram_bridge.py::kaydet_belge()`
  inserts a `SeferBelge` row (Telegram photo upload + OCR-pending marker).
- `fleet.arac_bakimlari` INSERT: `telegram_bridge.py::
  report_driver_breakdown()` -> `fleet.public.create_breakdown()`.
- `platform.error_events` UPDATE (resolved_at/resolved_by columns):
  `application/error_events.py::resolve_error_event()`.

Separately, a genuine PRE-EXISTING bug (unrelated to role grants — same
bug class as `reports/api/dashboard_routes.py`'s fix in the reports
pilot) was found and fixed in the same pilot: `error_events.py`'s
`list_error_events`/`get_error_stats`/`get_trace_chain`/
`resolve_error_event` each opened their own bare `AsyncSessionLocal()`
instead of taking the caller's request-scoped session. Harmless in
production (a real per-call session closes on its own), but in the test
suite's shared-session fixture the never-explicitly-closed read-only
transactions stayed open, leaking their `SET LOCAL ROLE` into whatever
HTTP call the shared test session handled next. Fixed: all 4 functions
now take a `session: AsyncSession` parameter, and `system_routes.py`
passes `uow.session` from its own `UOWDep`.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0072_faz2_admin_platform_grants
Revises: 0071_faz2_prediction_ml_grants
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0072_faz2_admin_platform_grants"
down_revision: Union[str, Sequence[str], None] = "0071_faz2_prediction_ml_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
