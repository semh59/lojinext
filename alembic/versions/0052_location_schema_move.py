"""FAZ2 şema-per-modül: location'ın 2 tablosunu location şemasına taşı.

`lokasyonlar`, `lokasyon_segments` — `v2/modules/location/infrastructure/models.py`.

Desen 0048 ile aynı. `lokasyon_segments`'in tek indeksi açık
`Index("ix_lokasyon_segments_lokasyon_id", ...)` — schema-agnostic, rename
yok; rename yalnız `lokasyonlar.is_deleted` için.

Revision ID: 0052_location_schema_move
Revises: 0051_fuel_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0052_location_schema_move"
down_revision: Union[str, Sequence[str], None] = "0051_fuel_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "location"
_TABLES = ["lokasyonlar", "lokasyon_segments"]

_SEARCH_PATH_AFTER = "public, import_excel, auth_rbac, fleet, driver, fuel, location"
_SEARCH_PATH_BEFORE = "public, import_excel, auth_rbac, fleet, driver, fuel"

_INDEX_RENAMES = [
    ("ix_lokasyonlar_is_deleted", "ix_location_lokasyonlar_is_deleted"),
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
