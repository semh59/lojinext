"""route_paths: drop 4 redundant single-column indexes (Tier B madde 14)

2026-07-02 prod-grade denetimi Tier B madde 14 "composite/mekânsal
index'siz" iddiası ampirik olarak (EXPLAIN ANALYZE, gerçek Postgres,
100k satır) DOĞRULANAMADI: `uq_route_coords` UniqueConstraint zaten
(origin_lat, origin_lon, dest_lat, dest_lon) üzerinde composite bir btree
index oluşturuyor ve `RouteRepository.get_by_coords`'un tek gerçek sorgu
deseni (4 kolonlu AND-range tolerans filtresi) bu index'i kullanıyor
(Index Scan, <1ms) — composite index zaten vardı.

Gerçek bulgu: 4 kolonun her biri AYRICA `index=True` ile tekil index'e
sahipti (ix_route_paths_origin_lat/origin_lon/dest_lat/dest_lon).
`route_paths` tablosunu tek kolon üzerinden sorgulayan hiçbir kod yolu yok
(grep ile doğrulandı) — bu 4 index sorgu performansına hiçbir katkı
sağlamadan sadece INSERT/UPDATE maliyeti ve disk alanı tüketiyordu.
EXPLAIN ANALYZE, bu 4 index kaldırıldıktan sonra AYNI planı (composite
unique index üzerinden Index Scan) ve aynı hızı üretti.

Revision ID: 0039_route_idx_cleanup
Revises: 0038_page_views_user_id_fk
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0039_route_idx_cleanup"
down_revision: Union[str, Sequence[str], None] = "0038_page_views_user_id_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    "ix_route_paths_origin_lat",
    "ix_route_paths_origin_lon",
    "ix_route_paths_dest_lat",
    "ix_route_paths_dest_lon",
]


def upgrade() -> None:
    for name in _INDEXES:
        op.drop_index(name, table_name="route_paths")


def downgrade() -> None:
    op.create_index("ix_route_paths_origin_lat", "route_paths", ["origin_lat"])
    op.create_index("ix_route_paths_origin_lon", "route_paths", ["origin_lon"])
    op.create_index("ix_route_paths_dest_lat", "route_paths", ["dest_lat"])
    op.create_index("ix_route_paths_dest_lon", "route_paths", ["dest_lon"])
