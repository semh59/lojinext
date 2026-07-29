"""FAZ2 Wave 2 pilot fix #8 — m_location needs SELECT on admin_platform.entegrasyon_ayarlari.

Found live in the same location-pilot investigation as 0066/0067 (same
ContextVar-task-local mechanism). `openroute_geocode_client.py`'s
`_resolve_api_key()` reads `admin_platform.entegrasyon_ayarlari` via
`admin_platform.public.get_integration_secret()` (the DB-configured ORS
key takes priority over the `.env` fallback). Without this grant the read
silently fails — caught and logged as a WARNING inside
`get_integration_secret`, falling through to `.env` — which never
crashed a request (so it wasn't caught by the CI failures that surfaced
0066/0067), but is a real prod functional regression: a DB-configured ORS
key would be silently ignored for the location role once role
enforcement is live.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0068_faz2_location_admin_key
Revises: 0067_faz2_location_route_write
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0068_faz2_location_admin_key"
down_revision: Union[str, Sequence[str], None] = "0067_faz2_location_route_write"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
