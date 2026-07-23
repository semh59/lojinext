"""FAZ2 şema-per-modül: notification'ın 3 tablosunu notification şemasına
taşı.

`bildirim_kurallari`, `bildirim_gecmisi`, `push_subscriptions` —
`v2/modules/notification/infrastructure/models.py`.

Desen 0048 ile aynı. `push_subscriptions.user_id`'nin tek indeksi açık
`Index("ix_push_subscriptions_user_id", ...)` — schema-agnostic, rename yok.

Revision ID: 0058_notification_schema_move
Revises: 0057_reports_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0058_notification_schema_move"
down_revision: Union[str, Sequence[str], None] = "0057_reports_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "notification"
_TABLES = ["bildirim_kurallari", "bildirim_gecmisi", "push_subscriptions"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports, notification"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports"
)

_INDEX_RENAMES = [
    ("ix_bildirim_kurallari_olay_tipi", "ix_notification_bildirim_kurallari_olay_tipi"),
    (
        "ix_bildirim_kurallari_alici_rol_id",
        "ix_notification_bildirim_kurallari_alici_rol_id",
    ),
    (
        "ix_bildirim_gecmisi_kullanici_id",
        "ix_notification_bildirim_gecmisi_kullanici_id",
    ),
    ("ix_bildirim_gecmisi_olay_tipi", "ix_notification_bildirim_gecmisi_olay_tipi"),
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
