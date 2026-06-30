"""route_simulations: add arac_id FK for vehicle-specific physics specs

When a user selects a vehicle for route simulation the endpoint now loads
the Arac row and builds a VehicleSpecs from its real technical parameters
(bos_agirlik_kg, hava_direnc_katsayisi, on_kesit_alani_m2,
lastik_direnc_katsayisi, motor_verimliligi).  This column stores which
vehicle was used so past simulations can be revisited with correct context.

Revision ID: 0034_route_simulations_arac_id
Revises: 0033_sefer_correction_audit
Create Date: 2026-06-30
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0034_route_simulations_arac_id"
down_revision: Union[str, Sequence[str], None] = "0033_sefer_correction_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "route_simulations",
        sa.Column("arac_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_route_simulations_arac_id",
        "route_simulations",
        "araclar",
        ["arac_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_route_simulations_arac_id",
        "route_simulations",
        ["arac_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_route_simulations_arac_id", table_name="route_simulations")
    op.drop_constraint(
        "fk_route_simulations_arac_id", "route_simulations", type_="foreignkey"
    )
    op.drop_column("route_simulations", "arac_id")
