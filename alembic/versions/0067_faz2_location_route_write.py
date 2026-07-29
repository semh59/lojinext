"""FAZ2 Wave 2 pilot fix #7 — m_location needs INSERT on route_simulation.route_paths.

Found live in GitHub CI (frontend real-backend suite) immediately after
0066's READER_SELECT_GRANTS fix landed: 0066 fixed cache HITS on
`GET /locations/route-info` (SELECT permission), but cache MISSES still
failed with `InsufficientPrivilegeError: permission denied for table
route_paths` on the INSERT that persists the freshly-computed route back
into `route_simulation.route_paths`.

Same root cause as 0066 (module-role ContextVar is task-local, so it
propagates into `route_simulation.public.get_route_details()`'s nested
session/repository calls) — this is the write-side half of that fix.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0067_faz2_location_route_write
Revises: 0066_faz2_location_route_sim_fix
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0067_faz2_location_route_write"
down_revision: Union[str, Sequence[str], None] = "0066_faz2_location_route_sim_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
