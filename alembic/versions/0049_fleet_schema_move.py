"""FAZ2 şema-per-modül: fleet'in 5 tablosunu fleet şemasına taşı.

`araclar`, `dorseler`, `vehicle_event_log`, `arac_bakimlari`,
`vehicle_spec_timeline` — `v2/modules/fleet/infrastructure/models.py`.

Desen 0048 ile aynı (bkz. o dosyanın docstring'i): search_path kümülatif
büyür, yalnız `index=True` naming-convention sütunları yeniden adlandırılır.
`vehicle_spec_timeline`'ın hiçbir `index=True` sütunu yok (yalnız açık
`Index("idx_spec_arac_tarih", ...)` — schema-agnostic) — bu tablo için
rename yok.

Revision ID: 0049_fleet_schema_move
Revises: 0048_auth_rbac_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0049_fleet_schema_move"
down_revision: Union[str, Sequence[str], None] = "0048_auth_rbac_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "fleet"
_TABLES = [
    "araclar",
    "dorseler",
    "vehicle_event_log",
    "arac_bakimlari",
    "vehicle_spec_timeline",
]

_SEARCH_PATH_AFTER = "public, import_excel, auth_rbac, fleet"
_SEARCH_PATH_BEFORE = "public, import_excel, auth_rbac"

_INDEX_RENAMES = [
    ("ix_araclar_plaka", "ix_fleet_araclar_plaka"),
    ("ix_araclar_is_deleted", "ix_fleet_araclar_is_deleted"),
    ("ix_dorseler_plaka", "ix_fleet_dorseler_plaka"),
    ("ix_dorseler_is_deleted", "ix_fleet_dorseler_is_deleted"),
    ("ix_vehicle_event_log_arac_id", "ix_fleet_vehicle_event_log_arac_id"),
    ("ix_vehicle_event_log_event_type", "ix_fleet_vehicle_event_log_event_type"),
    ("ix_vehicle_event_log_triggered_by", "ix_fleet_vehicle_event_log_triggered_by"),
    ("ix_arac_bakimlari_arac_id", "ix_fleet_arac_bakimlari_arac_id"),
    ("ix_arac_bakimlari_dorse_id", "ix_fleet_arac_bakimlari_dorse_id"),
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
