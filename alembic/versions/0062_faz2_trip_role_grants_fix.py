"""FAZ2 Wave 2 pilot fix — m_trip was missing from READER_SELECT_GRANTS.

Found live during the Wave 2 pilot (2026-07-28): with `trip`'s own routers
wired to `require_module_role("trip")`, creating a trip failed with a real
`permission denied for schema fleet` — `add_trip.py`'s own `arac_repo`/
`sofor_repo` FK-validation reads (fleet/driver), plus `bulk_add_trips.py`/
`sla.py`/`trip_prediction_enrichment.py`'s `lokasyon_repo` (location) and
`reconcile_costs.py`'s `yakit_repo` (fuel), all run under whatever role is
active for the request — `m_trip` had zero cross-schema SELECT grants in
Wave 1's original matrix (an oversight, not a Wave-1-time design decision).

Re-runs `apply_role_grants_sync` — idempotent (GRANT statements are safe to
re-issue), picks up `role_grants.py`'s now-corrected `READER_SELECT_GRANTS`
entry for `m_trip`.

Revision ID: 0062_faz2_trip_role_grants_fix
Revises: 0061_faz2_role_grants
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0062_faz2_trip_role_grants_fix"
down_revision: Union[str, Sequence[str], None] = "0061_faz2_role_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
