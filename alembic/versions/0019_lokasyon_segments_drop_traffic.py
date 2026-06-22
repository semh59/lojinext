"""lokasyon_segments traffic_speed_kmh + congestion drop (Phase 3.5)

Revision ID: 0019_lokasyon_segments_drop_traffic
Revises: 0018_route_simulations_lokasyon
Create Date: 2026-05-30 15:00:00.000000

Mimari düzeltme: lokasyon_segments yolun STATİK haritasıdır. Trafik
(traffic_speed_kmh, congestion) zamansal veridir — sefer simülasyonu
sırasında Mapbox cache (Phase 2.3, 24h) ile çekilip route_segments'a
yazılır.

Bu migration iki zamansal kolonu drop eder. Mevcut veriler kaybolur
(hidrate edilmiş lokasyonların traffic snapshot'ı). Kayıp önemsiz çünkü
zaten sefer simülasyonu güncel trafiği alır.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0019_drop_traffic"
down_revision: Union[str, Sequence[str], None] = "0018_route_simulations_lokasyon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("lokasyon_segments", "traffic_speed_kmh")
    op.drop_column("lokasyon_segments", "congestion")


def downgrade() -> None:
    op.add_column(
        "lokasyon_segments",
        sa.Column("traffic_speed_kmh", sa.Float, nullable=True),
    )
    op.add_column(
        "lokasyon_segments",
        sa.Column("congestion", sa.String(20), nullable=True),
    )
