"""route_simulations + route_segments (Phase 2.1)

Revision ID: 0016_route_simulations
Revises: 0015_push_subscriptions
Create Date: 2026-05-30 12:00:00.000000

Route Segment Simulation persist katmanı (Plan §5).

route_simulations: POST /api/v1/routes/simulate header (input snapshot +
aggregate result + pipeline meta).

route_segments: 500m bucket sonuçları (FK simulation_id ON DELETE CASCADE).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0016_route_simulations"
down_revision: Union[str, Sequence[str], None] = "0015_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "route_simulations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "kullanici_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cikis_lon", sa.Float, nullable=False),
        sa.Column("cikis_lat", sa.Float, nullable=False),
        sa.Column("varis_lon", sa.Float, nullable=False),
        sa.Column("varis_lat", sa.Float, nullable=False),
        sa.Column("ton", sa.Float, nullable=False, server_default="15.0"),
        sa.Column("arac_yasi", sa.Integer, nullable=False, server_default="5"),
        sa.Column("target_length_km", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("raw_segment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "resampled_segment_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "elevation_coverage_pct",
            sa.Float,
            nullable=False,
            server_default="0.0",
        ),
        sa.Column("total_km", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_l", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("avg_l_per_100km", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_eta_sec", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_ascent_m", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_descent_m", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_route_simulations_kullanici_id",
        "route_simulations",
        ["kullanici_id"],
    )
    op.create_index(
        "ix_route_simulations_kullanici_created",
        "route_simulations",
        ["kullanici_id", "created_at"],
    )

    op.create_table(
        "route_segments",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "simulation_id",
            sa.BigInteger,
            sa.ForeignKey("route_simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("length_km", sa.Float, nullable=False),
        sa.Column("grade_pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("road_class", sa.String(20), nullable=True),
        sa.Column("maxspeed_kmh", sa.Float, nullable=True),
        sa.Column("traffic_speed_kmh", sa.Float, nullable=True),
        sa.Column("congestion", sa.String(20), nullable=True),
        sa.Column("sim_speed_kmh", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("sim_l_per_100km", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("sim_l_total", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("eta_sec", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("mid_lon", sa.Float, nullable=True),
        sa.Column("mid_lat", sa.Float, nullable=True),
        sa.UniqueConstraint(
            "simulation_id", "seq", name="uq_route_segments_simulation_seq"
        ),
    )
    op.create_index(
        "ix_route_segments_simulation_id",
        "route_segments",
        ["simulation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_route_segments_simulation_id", table_name="route_segments")
    op.drop_table("route_segments")
    op.drop_index(
        "ix_route_simulations_kullanici_created",
        table_name="route_simulations",
    )
    op.drop_index("ix_route_simulations_kullanici_id", table_name="route_simulations")
    op.drop_table("route_simulations")
