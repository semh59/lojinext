"""iceri_aktarim_gecmisi.yukleyen_id FK: ON DELETE SET NULL (SEC-008)

The yukleyen_id -> kullanicilar(id) FK was created without an ondelete policy, so
it defaulted to RESTRICT: a user who had ever run a bulk import could not be
deleted (ForeignKeyViolation). Other audit-style FKs (Arac.olusturan_id,
Sefer.created_by_id, anomalies.acknowledged_by/resolved_by — 0028) already use
ON DELETE SET NULL; this aligns the last remaining kullanicilar FK with them.

The column is nullable, so SET NULL is valid. Re-add under the same PostgreSQL
default constraint name so a create_all-built schema (tests) and a migrated DB
(prod) stay identical.

Revision ID: 0032_iceri_aktarim_fk_ondelete
Revises: 0031_fix_admin_role_yetkiler
Create Date: 2026-06-23

(Revision id kept <= 32 chars to fit alembic_version.version_num varchar(32).)
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0032_iceri_aktarim_fk_ondelete"
down_revision: Union[str, Sequence[str], None] = "0031_fix_admin_role_yetkiler"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "iceri_aktarim_gecmisi"
# Naming-convention FK name (alembic/env.py:
# fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s). Must match so
# `alembic check` sees no drift against the ORM metadata.
_FK = "fk_iceri_aktarim_gecmisi_yukleyen_id_kullanicilar"
# PG default name, in case an older DB created the FK before the convention.
_FK_LEGACY = "iceri_aktarim_gecmisi_yukleyen_id_fkey"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_FK};")
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_FK_LEGACY};")
    op.execute(
        f"""
        ALTER TABLE {_TABLE}
          ADD CONSTRAINT {_FK}
          FOREIGN KEY (yukleyen_id) REFERENCES kullanicilar(id)
          ON DELETE SET NULL;
        """
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_FK};")
    op.execute(
        f"""
        ALTER TABLE {_TABLE}
          ADD CONSTRAINT {_FK}
          FOREIGN KEY (yukleyen_id) REFERENCES kullanicilar(id);
        """
    )
