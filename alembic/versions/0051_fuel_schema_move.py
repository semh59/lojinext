"""FAZ2 şema-per-modül: fuel'in 3 tablosunu fuel şemasına taşı.

`yakit_alimlari`, `yakit_periyotlari`, `yakit_formul` —
`v2/modules/fuel/infrastructure/models.py`.

Desen 0048 ile aynı. `yakit_periyotlari`/`yakit_formul`'in hiçbir
`index=True` sütunu yok (yalnız açık `UniqueConstraint`/composite
`Index()` — schema-agnostic) — rename yalnız `yakit_alimlari` için.

Revision ID: 0051_fuel_schema_move
Revises: 0050_driver_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0051_fuel_schema_move"
down_revision: Union[str, Sequence[str], None] = "0050_driver_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "fuel"
_TABLES = ["yakit_alimlari", "yakit_periyotlari", "yakit_formul"]

_SEARCH_PATH_AFTER = "public, import_excel, auth_rbac, fleet, driver, fuel"
_SEARCH_PATH_BEFORE = "public, import_excel, auth_rbac, fleet, driver"

_INDEX_RENAMES = [
    ("ix_yakit_alimlari_tarih", "ix_fuel_yakit_alimlari_tarih"),
    ("ix_yakit_alimlari_arac_id", "ix_fuel_yakit_alimlari_arac_id"),
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
