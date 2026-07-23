"""FAZ2 şema-per-modül: reports'un 1 tablosunu reports şemasına taşı.

`page_views` — `v2/modules/reports/infrastructure/models.py`.

Desen 0048 ile aynı. `user_id`'nin `index=True` OLMADIĞI gerçek Postgres'te
koşularak doğrulandı (yalnız `fk_page_views_user` FK kısıtı var, bkz.
`0038_page_views_user_id_fk.py` — ham SQL, naming-convention index değil)
— rename listesinde YOK, yalnız `route`/`created_at` var.

Revision ID: 0057_reports_schema_move
Revises: 0056_trip_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0057_reports_schema_move"
down_revision: Union[str, Sequence[str], None] = "0056_trip_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reports"
_TABLES = ["page_views"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip"
)

_INDEX_RENAMES = [
    ("ix_page_views_route", "ix_reports_page_views_route"),
    ("ix_page_views_created_at", "ix_reports_page_views_created_at"),
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
