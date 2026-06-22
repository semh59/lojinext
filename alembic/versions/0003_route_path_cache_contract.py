"""0003 route path cache contract

Revision ID: 0003_route_path_cache_contract
Revises: 0002_seed_and_bootstrap
Create Date: 2026-03-19 13:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_route_path_cache_contract"
down_revision: Union[str, None] = "0002_seed_and_bootstrap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _route_path_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("route_paths")}


def upgrade() -> None:
    columns = _route_path_columns()
    with op.batch_alter_table("route_paths") as batch_op:
        if "otoban_mesafe_km" not in columns:
            batch_op.add_column(
                sa.Column("otoban_mesafe_km", sa.Float(), nullable=True)
            )
        if "sehir_ici_mesafe_km" not in columns:
            batch_op.add_column(
                sa.Column("sehir_ici_mesafe_km", sa.Float(), nullable=True)
            )
        if "difficulty" not in columns:
            batch_op.add_column(
                sa.Column("difficulty", sa.String(length=20), nullable=True)
            )
        if "route_analysis" not in columns:
            batch_op.add_column(sa.Column("route_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    columns = _route_path_columns()
    with op.batch_alter_table("route_paths") as batch_op:
        if "route_analysis" in columns:
            batch_op.drop_column("route_analysis")
        if "difficulty" in columns:
            batch_op.drop_column("difficulty")
        if "sehir_ici_mesafe_km" in columns:
            batch_op.drop_column("sehir_ici_mesafe_km")
        if "otoban_mesafe_km" in columns:
            batch_op.drop_column("otoban_mesafe_km")
