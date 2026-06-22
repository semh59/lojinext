"""Add sefer_istatistik_mv materialized view

Revision ID: 0010_sefer_istatistik_mv
Revises: 0009_onay_durumu_index
Create Date: 2026-05-15

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0010_sefer_istatistik_mv"
down_revision: Union[str, Sequence[str], None] = "0009_onay_durumu_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
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
        WHERE is_deleted = FALSE AND durum != 'İptal'
        GROUP BY durum;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sefer_istatistik_mv_durum
        ON sefer_istatistik_mv (durum);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv;")
