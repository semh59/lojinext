"""FAZ2 şema-per-modül: admin_platform'un 2 tablosunu admin_platform
şemasına taşı.

`entegrasyon_ayarlari`, `admin_audit_log` —
`v2/modules/admin_platform/infrastructure/models.py`'nin admin_platform
şemasına ait tabloları. Aynı dosyanın `sistem_konfig`/`konfig_gecmis`/
`idempotency_keys` tabloları `platform` şemasına gider — bu, ayrı bir
sonraki migration'ın (platform şeması, MV/trigger/partition/alembic_version
taşımasıyla birlikte) işi (bkz. o dosyanın docstring'i).

Desen 0048 ile aynı. `entegrasyon_ayarlari`'nın hiçbir `index=True` sütunu
yok (yalnız `unique=True` — UniqueConstraint, schema-agnostic) — rename
yalnız `admin_audit_log.kullanici_id` için.

Revision ID: 0059_admin_platform_schema_move
Revises: 0058_notification_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0059_admin_platform_schema_move"
down_revision: Union[str, Sequence[str], None] = "0058_notification_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "admin_platform"
_TABLES = ["entegrasyon_ayarlari", "admin_audit_log"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports, notification, "
    "admin_platform"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports, notification"
)

_INDEX_RENAMES = [
    ("ix_admin_audit_log_kullanici_id", "ix_admin_platform_admin_audit_log_kullanici_id"),
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
