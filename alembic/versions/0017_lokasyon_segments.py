"""lokasyon zenginleştirme + lokasyon_segments (Phase 3.1)

Revision ID: 0017_lokasyon_segments
Revises: 0016_route_simulations
Create Date: 2026-05-30 13:00:00.000000

Lokasyon kaydı artık güzergahın HAM HARİTASI'nı taşır:
  - ad: kullanıcı verdiği takma isim ("Sabah Kargosu — İST-BUR")
  - hydrated_at: son LokasyonHydrator çalışma zamanı
  - raw/resampled segment sayıları + elevation_coverage_pct

Yeni tablo: lokasyon_segments — 500m bucket ham verisi (length/grade/
road_class/maxspeed sabit; traffic snapshot).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0017_lokasyon_segments"
down_revision: Union[str, Sequence[str], None] = "0016_route_simulations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. lokasyonlar tablosuna yeni alanlar
    op.add_column(
        "lokasyonlar",
        sa.Column("ad", sa.String(150), nullable=True),
    )
    op.add_column(
        "lokasyonlar",
        sa.Column("hydrated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lokasyonlar",
        sa.Column(
            "raw_segment_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "lokasyonlar",
        sa.Column(
            "resampled_segment_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "lokasyonlar",
        sa.Column(
            "elevation_coverage_pct",
            sa.Float,
            nullable=False,
            server_default="0.0",
        ),
    )

    # 2. Yeni lokasyon_segments tablosu
    op.create_table(
        "lokasyon_segments",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "lokasyon_id",
            sa.Integer,
            sa.ForeignKey("lokasyonlar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("length_km", sa.Float, nullable=False),
        sa.Column("grade_pct", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("road_class", sa.String(20), nullable=True),
        sa.Column("maxspeed_kmh", sa.Float, nullable=True),
        sa.Column("traffic_speed_kmh", sa.Float, nullable=True),
        sa.Column("congestion", sa.String(20), nullable=True),
        sa.Column("mid_lon", sa.Float, nullable=True),
        sa.Column("mid_lat", sa.Float, nullable=True),
        sa.UniqueConstraint(
            "lokasyon_id", "seq", name="uq_lokasyon_segments_lokasyon_seq"
        ),
    )
    op.create_index(
        "ix_lokasyon_segments_lokasyon_id",
        "lokasyon_segments",
        ["lokasyon_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lokasyon_segments_lokasyon_id", table_name="lokasyon_segments")
    op.drop_table("lokasyon_segments")
    op.drop_column("lokasyonlar", "elevation_coverage_pct")
    op.drop_column("lokasyonlar", "resampled_segment_count")
    op.drop_column("lokasyonlar", "raw_segment_count")
    op.drop_column("lokasyonlar", "hydrated_at")
    op.drop_column("lokasyonlar", "ad")
