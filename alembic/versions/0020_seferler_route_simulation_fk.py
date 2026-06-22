"""seferler.route_simulation_id FK (Phase 4.4)

Revision ID: 0020_sefer_rsim_fk
Revises: 0019_drop_traffic
Create Date: 2026-05-30 18:00:00.000000

SeferFuelEstimator (Phase 4.3) tahmin ürettiği route_simulations row'unu
sefer kaydına bağlar. NULL yapılır (geriye uyumlu — eski seferlerde bağ yok).
Lokasyon silinince route_simulations bağlı kalır (SET NULL Phase 3.3'te).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0020_sefer_rsim_fk"
down_revision: Union[str, Sequence[str], None] = "0019_drop_traffic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seferler",
        sa.Column(
            "route_simulation_id",
            sa.BigInteger,
            sa.ForeignKey("route_simulations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_seferler_route_simulation_id",
        "seferler",
        ["route_simulation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_seferler_route_simulation_id", table_name="seferler")
    op.drop_column("seferler", "route_simulation_id")
