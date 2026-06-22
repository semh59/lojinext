"""Canonicalize seferler.durum to English (Planned/Completed/Cancelled)

Fixes the model<->migration drift behind the systemic status-enum bugs:
the ORM model (``app/database/models.py``) declares the CHECK constraint as
``durum IN ('Planned','Completed','Cancelled')`` while the baseline migration
(0001) created a Turkish-only CHECK. Production (migrations) and tests
(``Base.metadata.create_all``) therefore disagreed on the allowed values, and
``alembic check`` does not reliably detect CheckConstraint text drift.

This migration brings the migration-built schema in line with the model:
  1. Drops the materialized view ``sefer_istatistik_mv`` (it has a unique index
     on ``durum`` and filtered the Turkish ``'İptal'`` value).
  2. Drops the Turkish ``check_sefer_durum_enum`` constraint.
  3. Remaps any legacy Turkish/ASCII ``durum`` values to canonical English.
  4. Recreates the constraint as ``IN ('Planned','Completed','Cancelled')``.
  5. Recreates the materialized view with the canonical ``'Cancelled'`` filter.

Revision ID: 0022_durum_canonical_english
Revises: bc35e04ad0fd
Create Date: 2026-06-09
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0022_durum_canonical_english"
down_revision: Union[str, Sequence[str], None] = "bc35e04ad0fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Legacy (Turkish / ASCII / mixed-case) -> canonical English status mapping.
# Mirrors app/core/utils/trip_status.py::_LEGACY_STATUS_ALIASES.
_LEGACY_TO_CANONICAL = {
    "Planlandı": "Planned",
    "Planlandi": "Planned",
    "PLANLANDI": "Planned",
    "planlandi": "Planned",
    "Bekliyor": "Planned",
    "Yolda": "Planned",
    "InTransit": "Planned",
    "InProgress": "Planned",
    "Devam Ediyor": "Planned",
    "Assigned": "Planned",
    "Atandı": "Planned",
    "Tamamlandı": "Completed",
    "Tamamlandi": "Completed",
    "TAMAMLANDI": "Completed",
    "tamamlandi": "Completed",
    "Tamam": "Completed",
    "Done": "Completed",
    "İptal": "Cancelled",
    "İptal Edildi": "Cancelled",
    "Iptal": "Cancelled",
    "IPTAL": "Cancelled",
    "iptal": "Cancelled",
}

_MV_CREATE = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS sefer_istatistik_mv AS
    SELECT
        durum,
        COUNT(id)                              AS toplam_sefer,
        COALESCE(SUM(mesafe_km), 0)            AS toplam_km,
        COALESCE(SUM(otoban_mesafe_km), 0)     AS highway_km,
        COALESCE(SUM(ascent_m), 0)             AS total_ascent,
        COALESCE(SUM(net_kg / 1000.0), 0)      AS total_weight,
        MAX(created_at)                        AS last_updated
    FROM seferler
    WHERE is_deleted = FALSE AND durum != '{cancelled}'
    GROUP BY durum;
"""

_MV_INDEX = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_sefer_istatistik_mv_durum
    ON sefer_istatistik_mv (durum);
"""


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Drop the MV (depends on seferler.durum, unique index on durum).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv;")

    # 2. Drop the (Turkish) CHECK constraint so data can be remapped.
    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_durum_enum;")

    # 3. Remap legacy values to canonical English.
    for legacy, canonical in _LEGACY_TO_CANONICAL.items():
        conn.execute(
            sa.text("UPDATE seferler SET durum = :c WHERE durum = :l"),
            {"c": canonical, "l": legacy},
        )

    # 3b. Safety net: anything still outside the canonical set (corrupt /
    # unexpected) is parked as 'Planned' so the new constraint can be added.
    conn.execute(
        sa.text(
            "UPDATE seferler SET durum = 'Planned' "
            "WHERE durum NOT IN ('Planned', 'Completed', 'Cancelled')"
        )
    )

    # 4. Recreate the constraint in canonical English form (matches the model).
    op.execute(
        "ALTER TABLE seferler ADD CONSTRAINT check_sefer_durum_enum "
        "CHECK (durum IN ('Planned', 'Completed', 'Cancelled'));"
    )

    # 5. Recreate the MV with the canonical 'Cancelled' filter.
    op.execute(_MV_CREATE.format(cancelled="Cancelled"))
    op.execute(_MV_INDEX)


def downgrade() -> None:
    conn = op.get_bind()

    op.execute("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv;")
    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_durum_enum;")

    # Remap English values back to representative Turkish values before
    # re-adding the Turkish CHECK — without this, existing rows violate the new
    # constraint and the downgrade fails (the old comment claiming this was
    # unnecessary was wrong: the data was remapped in upgrade and must be
    # remapped back here).
    conn.execute(
        sa.text("UPDATE seferler SET durum = 'Bekliyor'   WHERE durum = 'Planned'")
    )
    conn.execute(
        sa.text("UPDATE seferler SET durum = 'Tamamlandı' WHERE durum = 'Completed'")
    )
    conn.execute(
        sa.text("UPDATE seferler SET durum = 'İptal'      WHERE durum = 'Cancelled'")
    )

    op.execute(
        "ALTER TABLE seferler ADD CONSTRAINT check_sefer_durum_enum "
        "CHECK (durum IN ('Bekliyor', 'Planlandı', 'Yolda', 'Devam Ediyor', "
        "'Tamamlandı', 'Tamam', 'İptal'));"
    )
    op.execute(_MV_CREATE.format(cancelled="İptal"))
    op.execute(_MV_INDEX)
