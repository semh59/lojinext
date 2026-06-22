"""add durum check constraint and server defaults

Revision ID: d465eee4f53b
Revises: c5b2e5e92a68
Create Date: 2026-03-05 13:05:10.767398

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d465eee4f53b"
down_revision: Union[str, Sequence[str], None] = "c5b2e5e92a68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. durum Enum CHECK constraint
    op.create_check_constraint(
        "check_sefer_durum_enum",
        "seferler",
        "durum IN ('Bekliyor', 'Planlandı', 'Yolda', 'Devam Ediyor', 'Tamamlandı', 'Tamam', 'İptal')",
    )
    # 2. bos_sefer server_default
    op.alter_column("seferler", "bos_sefer", server_default=sa.text("false"))
    # 3. durum server_default
    op.alter_column("seferler", "durum", server_default=sa.text("'Tamam'"))
    # 4. Recreate MV with is_real + is_deleted filters
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sefer_istatistik_mv;")
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
    op.alter_column("seferler", "durum", server_default=None)
    op.alter_column("seferler", "bos_sefer", server_default=None)
    op.drop_constraint("check_sefer_durum_enum", "seferler", type_="check")
