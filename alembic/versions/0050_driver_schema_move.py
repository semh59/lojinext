"""FAZ2 şema-per-modül: driver'ın 4 tablosunu driver şemasına taşı.

`soforler`, `sofor_ad_soyad_trigram`, `sofor_adaptasyon`,
`coaching_deliveries` — `v2/modules/driver/infrastructure/models.py`.

Desen 0048 ile aynı. `sofor_ad_soyad_trigram`'ın tek indeksi açık
`Index("ix_sofor_trigram_hash", ...)` — schema-agnostic, rename yok.

Revision ID: 0050_driver_schema_move
Revises: 0049_fleet_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0050_driver_schema_move"
down_revision: Union[str, Sequence[str], None] = "0049_fleet_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "driver"
_TABLES = [
    "soforler",
    "sofor_ad_soyad_trigram",
    "sofor_adaptasyon",
    "coaching_deliveries",
]

_SEARCH_PATH_AFTER = "public, import_excel, auth_rbac, fleet, driver"
_SEARCH_PATH_BEFORE = "public, import_excel, auth_rbac, fleet"

_INDEX_RENAMES = [
    ("ix_soforler_ad_soyad_bidx", "ix_driver_soforler_ad_soyad_bidx"),
    ("ix_soforler_telegram_id", "ix_driver_soforler_telegram_id"),
    ("ix_sofor_adaptasyon_surucu_id", "ix_driver_sofor_adaptasyon_surucu_id"),
    ("ix_coaching_deliveries_sofor_id", "ix_driver_coaching_deliveries_sofor_id"),
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
