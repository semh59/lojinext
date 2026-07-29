"""FAZ2 Wave 2 pilot fix #14 — m_import_excel grant gaps (3 found).

Found live during the import_excel-module pilot (2026-07-29), via a
comprehensive public.py cross-module audit performed BEFORE wiring.
`m_import_excel` previously had 5 WriteExceptions (fleet.araclar,
driver.soforler, driver.sofor_ad_soyad_trigram, trip.seferler,
fuel.yakit_alimlari — all from `execute_import.py`'s intentional raw-SQL
repository bypass, already documented in driver/CLAUDE.md), but 2 OTHER
call paths were missed:

- `route_importer.py::import_routes()` -> `location.public.
  create_location(uow.lokasyon_repo, ...)` INSERTs a new `lokasyonlar` row,
  or on the "reactivate a passive route" branch UPDATEs an existing one at
  arbitrary caller-supplied fields (full-table UPDATE, not column-scoped).
- `yakit_importer.py` -> `fuel.public.recalculate_vehicle_periods()`:
  `uow.yakit_repo.save_fuel_periods(periods, clear_existing=True)` does a
  DELETE + bulk INSERT into `fuel.yakit_periyotlari` (distinct from
  `yakit_alimlari`, needed its own grant); `uow.sefer_repo.
  update_trips_fuel_data(...)` does a bulk ORM UPDATE on `trip.seferler`
  limited to 3 columns (dagitilan_yakit/tuketim/periyot_id) -- a separate
  WriteException from the existing INSERT/DELETE one on the same table
  (that one covers execute_import's raw-SQL bulk sefer import, not this
  UPDATE path).

3 new WriteExceptions:
- `location.lokasyonlar` INSERT + UPDATE (full-table).
- `fuel.yakit_periyotlari` INSERT + DELETE.
- `trip.seferler` UPDATE, columns=(dagitilan_yakit, tuketim, periyot_id).

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0073_faz2_import_excel_grants
Revises: 0072_faz2_admin_platform_grants
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0073_faz2_import_excel_grants"
down_revision: Union[str, Sequence[str], None] = "0072_faz2_admin_platform_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
