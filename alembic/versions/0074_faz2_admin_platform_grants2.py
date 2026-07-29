"""FAZ2 Wave 2 pilot fix #15 — m_admin_platform grant gap #2: sistem_konfig/konfig_gecmis.

Found live via a real frontend CI test hitting the real backend (2026-07-29):
`PUT /admin/config/{key}` 500'd with "permission denied for table
sistem_konfig" (`KonfigurasyonPage.test.tsx`, real-backend frontend suite).

`sistem_konfig`/`konfig_gecmis` are admin_platform's own primary feature
(system config CRUD, `konfig_service.py`) but -- like `error_events` in
0072 -- physically live in the `platform` schema, not `admin_platform`:
migration 0059_admin_platform_schema_move moves entegrasyon_ayarlari/
admin_audit_log into the admin_platform schema, but that same migration's
own docstring routes sistem_konfig/konfig_gecmis/idempotency_keys to the
platform schema instead. This pilot's initial audit (0072) missed that
nuance by trusting the module's CLAUDE.md table-ownership summary at face
value instead of the migration itself.

`AdminConfigRepository.update_value()` runs `SELECT ... FOR UPDATE` on
`sistem_konfig` -- Postgres requires UPDATE privilege (not just SELECT) to
take a `FOR UPDATE` row lock. The pre-existing `READER_SELECT_GRANTS`
"platform" entry (added in 0072) only covers plain SELECT.

2 new WriteExceptions:
- `platform.sistem_konfig` UPDATE, columns=(deger, guncelleyen_id,
  son_guncelleme) -- the last one is the model's own `onupdate=func.now()`
  column, auto-included in every UPDATE statement.
- `platform.konfig_gecmis` INSERT -- the same call also inserts an
  audit-history row.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0074_faz2_admin_platform_grants2
Revises: 0073_faz2_import_excel_grants
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0074_faz2_admin_platform_grants2"
down_revision: Union[str, Sequence[str], None] = "0073_faz2_import_excel_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
