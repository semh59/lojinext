"""FAZ2 şema-per-modül: anomaly'nin 2 tablosunu anomaly şemasına taşı.

`anomalies`, `fuel_investigations` — `v2/modules/anomaly/infrastructure/models.py`.

Desen 0048 ile aynı. `fuel_investigations`'ın tüm indeksleri açık
`Index("ix_fuel_inv_*", ...)` — schema-agnostic, rename yok; rename yalnız
`anomalies` tablosunun 5 `index=True` sütunu için.

Revision ID: 0054_anomaly_schema_move
Revises: 0053_route_simulation_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0054_anomaly_schema_move"
down_revision: Union[str, Sequence[str], None] = "0053_route_sim_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "anomaly"
_TABLES = ["anomalies", "fuel_investigations"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation"
)

_INDEX_RENAMES = [
    ("ix_anomalies_tarih", "ix_anomaly_anomalies_tarih"),
    ("ix_anomalies_tip", "ix_anomaly_anomalies_tip"),
    ("ix_anomalies_kaynak_id", "ix_anomaly_anomalies_kaynak_id"),
    ("ix_anomalies_acknowledged_at", "ix_anomaly_anomalies_acknowledged_at"),
    ("ix_anomalies_resolved_at", "ix_anomaly_anomalies_resolved_at"),
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
