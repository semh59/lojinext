"""FAZ2 Wave 2 pilot fix #9 — m_route_simulation missing fleet/trip/admin_platform grants.

Found live during the route_simulation-module pilot (2026-07-29) via a
COMPREHENSIVE public.py cross-module audit performed up front (a direct
lesson from the location pilot's 3-round trip, 0066/0067/0068 — this time
grepping every `from v2.modules.*.public import` in route_simulation
before wiring, instead of discovering one CI failure at a time):

- `fleet`: `create_route_simulation.py`'s `POST /simulate` handler does
  `db.get(Arac, arac_id)` directly to resolve vehicle specs.
- `trip`: `weather_routes.py`'s `GET /weather/dashboard-summary` calls
  `SeferService.get_all_paged(...)` (trip's request-scoped factory) to
  list planned trips for the weather-risk dashboard.
- `admin_platform`: both `openroute_client.py` and `mapbox_client.py`
  call `admin_platform.public.get_integration_secret` for DB-configured
  API keys (same `entegrasyon_ayarlari` table the location pilot's 0068
  fixed for m_location).

`m_route_simulation` previously only had `location` in
READER_SELECT_GRANTS.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0069_faz2_route_sim_grants
Revises: 0068_faz2_location_admin_key
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0069_faz2_route_sim_grants"
down_revision: Union[str, Sequence[str], None] = "0068_faz2_location_admin_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
