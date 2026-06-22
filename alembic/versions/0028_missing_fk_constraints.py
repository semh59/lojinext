"""Add missing FK constraints (AUDIT-008)

Five user/reference id columns lacked DB-level FK constraints, allowing orphaned
references to accumulate silently. Added with NOT VALID so existing rows are not
validated at migration time. Run VALIDATE CONSTRAINT after confirming data integrity.

Tables affected:
  - anomalies.acknowledged_by / resolved_by → kullanicilar(id) ON DELETE SET NULL
  - seferler_log.degistiren_id             → kullanicilar(id) ON DELETE SET NULL
  - bildirim_kurallari.alici_rol_id        → roller(id) ON DELETE RESTRICT
  - yakit_periyotlari.alim1_id / alim2_id  → yakit_alimlari(id) ON DELETE CASCADE

Revision ID: 0028_missing_fk_constraints
Revises: 0027_fix_seferler_durum_default
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0028_missing_fk_constraints"
down_revision: Union[str, Sequence[str], None] = "0027_fix_seferler_durum_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT VALID skips validation of existing rows — safe for production migrations
    # where orphaned data may exist from before this constraint was added.
    op.execute("""
        ALTER TABLE anomalies
          ADD CONSTRAINT fk_anomaly_acknowledged_by
          FOREIGN KEY (acknowledged_by) REFERENCES kullanicilar(id)
          ON DELETE SET NULL
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE anomalies
          ADD CONSTRAINT fk_anomaly_resolved_by
          FOREIGN KEY (resolved_by) REFERENCES kullanicilar(id)
          ON DELETE SET NULL
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE seferler_log
          ADD CONSTRAINT fk_seferler_log_degistiren
          FOREIGN KEY (degistiren_id) REFERENCES kullanicilar(id)
          ON DELETE SET NULL
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE bildirim_kurallari
          ADD CONSTRAINT fk_bildirim_kural_rol
          FOREIGN KEY (alici_rol_id) REFERENCES roller(id)
          ON DELETE RESTRICT
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE yakit_periyotlari
          ADD CONSTRAINT fk_yakit_periyot_alim1
          FOREIGN KEY (alim1_id) REFERENCES yakit_alimlari(id)
          ON DELETE CASCADE
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE yakit_periyotlari
          ADD CONSTRAINT fk_yakit_periyot_alim2
          FOREIGN KEY (alim2_id) REFERENCES yakit_alimlari(id)
          ON DELETE CASCADE
          NOT VALID;
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE yakit_periyotlari DROP CONSTRAINT IF EXISTS fk_yakit_periyot_alim2;"
    )
    op.execute(
        "ALTER TABLE yakit_periyotlari DROP CONSTRAINT IF EXISTS fk_yakit_periyot_alim1;"
    )
    op.execute(
        "ALTER TABLE bildirim_kurallari DROP CONSTRAINT IF EXISTS fk_bildirim_kural_rol;"
    )
    op.execute(
        "ALTER TABLE seferler_log DROP CONSTRAINT IF EXISTS fk_seferler_log_degistiren;"
    )
    op.execute(
        "ALTER TABLE anomalies DROP CONSTRAINT IF EXISTS fk_anomaly_resolved_by;"
    )
    op.execute(
        "ALTER TABLE anomalies DROP CONSTRAINT IF EXISTS fk_anomaly_acknowledged_by;"
    )
