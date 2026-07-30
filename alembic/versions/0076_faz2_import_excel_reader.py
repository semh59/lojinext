"""FAZ2 combined-coverage-gate CI failure fix — m_import_excel reader grants.

Found live (2026-07-30) via a real CI "hard-gates" failure on the
`f775f0e` push: the combined coverage gate dropped from 92% to 91% because
`sefer_upload_importer.py`'s `uow.arac_repo.get_all(sadece_aktif=False)`
hit `permission denied for table arac_bakimlari` under `m_import_excel`
(an "Integration — remaining" test exercised this path; the error was
caught and degraded gracefully rather than raising, so no test failed --
it just meant the success-path branches after this call never ran).

`m_import_excel` previously had 0 entries in READER_SELECT_GRANTS -- only
5 narrow WriteExceptions for its own bulk-write columns (0073). But every
importer validates/looks up existing rows across fleet/driver/trip/
location/fuel BEFORE writing (see role_grants.py's new
"m_import_excel" comment for the full call-site audit: arac_repo.get_all,
sofor_repo.get_all, dorse_repo.get_all, lokasyon_repo.get_all/
get_all_route_keys, and fuel.public.recalculate_vehicle_periods's own
yakit_repo.get_all read before rewriting yakit_periyotlari).

New READER_SELECT_GRANTS entry: `"m_import_excel": ["fleet", "driver",
"trip", "location", "fuel"]`.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0076_faz2_import_excel_reader
Revises: 0075_faz2_ai_assistant_grants
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0076_faz2_import_excel_reader"
down_revision: Union[str, Sequence[str], None] = "0075_faz2_ai_assistant_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
