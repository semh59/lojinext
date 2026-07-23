"""FAZ2 şema-per-modül: prediction_ml'in 3 tablosunu prediction_ml şemasına
taşı.

`egitim_kuyrugu`, `model_versiyonlar`, `prediction_results` —
`v2/modules/prediction_ml/infrastructure/models.py`.

Desen 0048 ile aynı. `model_versiyonlar`'ın açık `Index("idx_model_arac_versiyon", ...)`
ve `UniqueConstraint("arac_id", "versiyon", name="uq_arac_versiyon")` kısıtları
schema-agnostic, rename yok.

Revision ID: 0055_prediction_ml_schema_move
Revises: 0054_anomaly_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0055_prediction_ml_schema_move"
down_revision: Union[str, Sequence[str], None] = "0054_anomaly_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prediction_ml"
_TABLES = ["egitim_kuyrugu", "model_versiyonlar", "prediction_results"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly"
)

_INDEX_RENAMES = [
    ("ix_egitim_kuyrugu_arac_id", "ix_prediction_ml_egitim_kuyrugu_arac_id"),
    ("ix_egitim_kuyrugu_durum", "ix_prediction_ml_egitim_kuyrugu_durum"),
    ("ix_model_versiyonlar_arac_id", "ix_prediction_ml_model_versiyonlar_arac_id"),
    ("ix_prediction_results_task_id", "ix_prediction_ml_prediction_results_task_id"),
    ("ix_prediction_results_status", "ix_prediction_ml_prediction_results_status"),
    ("ix_prediction_results_user_id", "ix_prediction_ml_prediction_results_user_id"),
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
