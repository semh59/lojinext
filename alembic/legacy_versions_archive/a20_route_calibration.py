"""020_route_calibration

Revision ID: a20_route_calib
Revises: 0fd51bbb32e2
Create Date: 2026-02-28 13:10:52.427042

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "a20_route_calib"
down_revision: Union[str, Sequence[str], None] = "0fd51bbb32e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass
    # 0. Enable PostGIS
    # op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))

    # 1. Add spatial columns to lokasyonlar
    # op.add_column("lokasyonlar", sa.Column("cikis_geom", Geometry(geometry_type="POINT", srid=4326), nullable=True))
    # op.add_column("lokasyonlar", sa.Column("varis_geom", Geometry(geometry_type="POINT", srid=4326), nullable=True))
    # op.add_column("lokasyonlar", sa.Column("rota_geom", Geometry(geometry_type="LINESTRING", srid=4326), nullable=True))

    # 2. Add spatial columns to seferler
    # op.add_column("seferler", sa.Column("cikis_geom", Geometry(geometry_type="POINT", srid=4326), nullable=True))
    # op.add_column("seferler", sa.Column("varis_geom", Geometry(geometry_type="POINT", srid=4326), nullable=True))

    # 3. Create guzergah_kalibrasyonlari table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "guzergah_kalibrasyonlari" not in inspector.get_table_names():
        op.create_table(
            "guzergah_kalibrasyonlari",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lokasyon_id", sa.Integer(), nullable=False),
            # sa.Column("hedef_path", Geometry(geometry_type="LINESTRING", srid=4326), nullable=True),
            sa.Column(
                "buffer_meters", sa.Float(), server_default="250.0", nullable=False
            ),
            sa.Column("match_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column(
                "avg_deviation_dist", sa.Float(), server_default="0.0", nullable=False
            ),
            sa.Column(
                "olusturma_tarihi",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["lokasyon_id"], ["lokasyonlar.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_guzergah_kalibrasyonlari_lokasyon_id"),
            "guzergah_kalibrasyonlari",
            ["lokasyon_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_guzergah_kalibrasyonlari_lokasyon_id"),
        table_name="guzergah_kalibrasyonlari",
    )
    op.drop_table("guzergah_kalibrasyonlari")

    # op.drop_column("seferler", "varis_geom")
    # op.drop_column("seferler", "cikis_geom")

    # op.drop_column("lokasyonlar", "rota_geom")
    # op.drop_column("lokasyonlar", "varis_geom")
    # op.drop_column("lokasyonlar", "cikis_geom")

    # We do not drop postgis extension as it might be used by other things,
    # but technically we could if we were sure.
