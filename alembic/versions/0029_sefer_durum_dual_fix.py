"""fix seferler.durum: drop the stale Turkish CHECK left beside the English one

Migration 0022 canonicalised durum to English by dropping/creating a constraint
named ``check_sefer_durum_enum`` (un-prefixed) — but the ORM's naming convention
had created the original Turkish constraint as ``ck_seferler_check_sefer_durum_enum``
(``ck_<table>_`` prefix). 0022's ``DROP ... IF EXISTS check_sefer_durum_enum`` was a
no-op against the prefixed name, so BOTH constraints survived on the migrated DB:

  * ck_seferler_check_sefer_durum_enum  -> Turkish set (Bekliyor/Planlandı/.../İptal)
  * check_sefer_durum_enum              -> English set (Planned/Completed/Cancelled)

A row must satisfy every CHECK, and the two value sets are disjoint, so NO durum
value could be inserted — every sefer create/import failed with CheckViolationError.
(Test DBs build the schema from models.py via create_all, so they only ever had the
correct prefixed English constraint and never hit this; the bug is migration-only.)

This migration consolidates to a single constraint that matches the ORM naming
convention + English values (models.py: name="check_sefer_durum_enum" ->
ck_seferler_check_sefer_durum_enum).

Revision ID: 0029_sefer_durum_dual_fix
Revises: 0028_missing_fk_constraints
Create Date: 2026-06-18

(Revision id kept <= 32 chars to fit alembic_version.version_num varchar(32).)
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0029_sefer_durum_dual_fix"
down_revision: Union[str, Sequence[str], None] = "0028_missing_fk_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop both existing durum CHECKs (the disjoint pair that blocked all inserts).
    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_durum_enum;")
    op.execute(
        "ALTER TABLE seferler DROP CONSTRAINT IF EXISTS ck_seferler_check_sefer_durum_enum;"
    )

    # Defensive remap: canonicalise any legacy Turkish/ASCII values still present
    # before re-applying the English constraint (0022 already remapped, but a row
    # could have been written under the un-prefixed English constraint only).
    op.execute(
        """
        UPDATE seferler SET durum = CASE durum
            WHEN 'Bekliyor' THEN 'Planned'
            WHEN 'Planlandı' THEN 'Planned'
            WHEN 'Planlandi' THEN 'Planned'
            WHEN 'Yolda' THEN 'Planned'
            WHEN 'Devam Ediyor' THEN 'Planned'
            WHEN 'Tamamlandı' THEN 'Completed'
            WHEN 'Tamamlandi' THEN 'Completed'
            WHEN 'Tamam' THEN 'Completed'
            WHEN 'İptal' THEN 'Cancelled'
            WHEN 'Iptal' THEN 'Cancelled'
            ELSE durum
        END
        WHERE durum NOT IN ('Planned', 'Completed', 'Cancelled');
        """
    )

    # Recreate the single constraint under the ORM naming-convention name.
    op.execute(
        "ALTER TABLE seferler ADD CONSTRAINT ck_seferler_check_sefer_durum_enum "
        "CHECK (durum IN ('Planned', 'Completed', 'Cancelled'));"
    )


def downgrade() -> None:
    # The pre-0029 state was functionally broken (two disjoint CHECKs => no insertable
    # value). We deliberately restore only the working English constraint (0022's
    # intended end-state) rather than re-introducing the impossible pair.
    op.execute(
        "ALTER TABLE seferler DROP CONSTRAINT IF EXISTS ck_seferler_check_sefer_durum_enum;"
    )
    op.execute(
        "ALTER TABLE seferler ADD CONSTRAINT check_sefer_durum_enum "
        "CHECK (durum IN ('Planned', 'Completed', 'Cancelled'));"
    )
