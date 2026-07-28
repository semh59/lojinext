"""FAZ2 şema-per-modül: route_simulation'ın 4 tablosunu route_simulation
şemasına taşı.

`route_paths`, `guzergah_kalibrasyonlari`, `route_simulations`,
`route_segments` — `v2/modules/route_simulation/infrastructure/models.py`.

Desen 0048 ile aynı. `route_paths`'in tek kısıtı `UniqueConstraint` (4
kolon composite) — schema-agnostic, rename yok. `route_segments`'in tek
indeksi açık `Index("ix_route_segments_simulation_id", ...)` — rename yok.
`route_simulations`'ın açık `Index("ix_route_simulations_kullanici_created", ...)`
kompozit indeksi de schema-agnostic, dokunulmuyor.

Revision ID: 0053_route_sim_schema_move
Revises: 0052_location_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0053_route_sim_schema_move"
down_revision: Union[str, Sequence[str], None] = "0052_location_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "route_simulation"
_TABLES = [
    "route_paths",
    "guzergah_kalibrasyonlari",
    "route_simulations",
    "route_segments",
]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation"
)
_SEARCH_PATH_BEFORE = "public, import_excel, auth_rbac, fleet, driver, fuel, location"

_INDEX_RENAMES = [
    (
        "ix_guzergah_kalibrasyonlari_lokasyon_id",
        "ix_route_simulation_guzergah_kalibrasyonlari_lokasyon_id",
    ),
    (
        "ix_route_simulations_kullanici_id",
        "ix_route_simulation_route_simulations_kullanici_id",
    ),
    (
        "ix_route_simulations_lokasyon_id",
        "ix_route_simulation_route_simulations_lokasyon_id",
    ),
    (
        "ix_route_simulations_arac_id",
        "ix_route_simulation_route_simulations_arac_id",
    ),
]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} SET SCHEMA {_SCHEMA}")
    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_AFTER}")
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{new} RENAME TO {old}")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} SET SCHEMA public")
    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_BEFORE}")
