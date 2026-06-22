"""Add sefer_istatistik_mv materialized view

Revision ID: 9d34165ea0de
Revises: d4dfd8f6eeea
Create Date: 2026-03-04 09:40:47.218459

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d34165ea0de"
down_revision: Union[str, Sequence[str], None] = "d4dfd8f6eeea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure soft-delete column exists before creating materialized view
    op.execute(
        "ALTER TABLE IF EXISTS seferler "
        "ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"
    )

    op.execute("""
        CREATE MATERIALIZED VIEW sefer_istatistik_mv AS
        SELECT
            durum,
            COUNT(id) as toplam_sefer,
            COALESCE(SUM(mesafe_km), 0) as toplam_km,
            COALESCE(SUM(otoban_mesafe_km), 0) as highway_km,
            COALESCE(SUM(ascent_m), 0) as total_ascent,
            COALESCE(SUM(net_kg / 1000.0), 0) as total_weight,
            MAX(created_at) as last_updated
        FROM seferler
        WHERE is_real = TRUE AND is_deleted = FALSE AND durum != 'İptal'
        GROUP BY durum;
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_sefer_istatistik_mv_durum
        ON sefer_istatistik_mv (durum);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv;")
