"""FAZ2 Wave 2 pilot fix #6 — m_location missing route_simulation READER_SELECT_GRANTS.

Found live during the location-module pilot (2026-07-29), and confirmed
as a REAL regression (not a flaky test) via two consecutive identical CI
failures on `GET /locations/route-info` (frontend real-backend suite:
`LocationFormModal.test.tsx` + `location-service.test.ts::getRouteInfo`).

Root cause: `GET /locations/route-info` reads a cached route via
`route_simulation.public.get_route_details()`, which queries
`route_simulation.route_paths` (a bbox lookup on cached routes). This
nested call opens its own session, but the module-role `ContextVar` set
by `require_module_role("location")` is task-local (not session-local) —
it propagates into every `AsyncSessionLocal()` created anywhere during
the same async request, including this nested route_simulation session.
So `m_location` itself (not just `m_route_simulation`) needs SELECT on
route_simulation's tables. Without it: `InsufficientPrivilegeError:
permission denied for schema route_simulation` — surfaced to the CI
frontend suite as a raw network/CORS failure (jsdom's XHR layer reports
an aborted/errored response as "Cross origin ... forbidden" rather than
a clean 500, since the connection dies mid-response under the unhandled
exception).

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0066_faz2_location_route_sim_fix
Revises: 0065_faz2_driver_role_grants_fix
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0066_faz2_location_route_sim_fix"
down_revision: Union[str, Sequence[str], None] = "0065_faz2_driver_role_grants_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
