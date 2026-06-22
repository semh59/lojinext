"""route_simulations.lokasyon_id FK (Phase 3.3)

Revision ID: 0018_route_simulations_lokasyon
Revises: 0017_lokasyon_segments
Create Date: 2026-05-30 14:00:00.000000

Sefer simülasyonunu kayıtlı güzergaha bağlamak için route_simulations'a
nullable lokasyon_id FK + index ekler. Lokasyon silinirse simülasyon
kaydı korunur ama bağ kaybedilir (ON DELETE SET NULL).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0018_route_simulations_lokasyon"
down_revision: Union[str, Sequence[str], None] = "0017_lokasyon_segments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "route_simulations",
        sa.Column(
            "lokasyon_id",
            sa.Integer,
            sa.ForeignKey("lokasyonlar.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_route_simulations_lokasyon_id",
        "route_simulations",
        ["lokasyon_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_route_simulations_lokasyon_id", table_name="route_simulations")
    op.drop_column("route_simulations", "lokasyon_id")
