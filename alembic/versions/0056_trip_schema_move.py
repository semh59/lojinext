"""FAZ2 şema-per-modül: trip'in 3 tablosunu trip şemasına taşı.

`seferler`, `seferler_log`, `sefer_belgeler` —
`v2/modules/trip/infrastructure/models.py`.

Desen 0048 ile aynı. `seferler`'in çoğu açık `Index(...)`/GIN indeksi
(`idx_seferler_durum_tarih`, `ix_seferler_arac_id_tarih`,
`ix_seferler_sofor_id_tarih`, `ix_seferler_arac_id_durum`,
`idx_seferler_rota_detay_gin`, `idx_seferler_tahmin_meta_gin`,
`ix_seferler_onay_durumu`) schema-agnostic, rename yok — yalnız
`index=True` (naming-convention) sütunları aşağıda listeli.
`seferler.id`'ye kendi-şema self-reference (`seferler_log.sefer_id`,
`sefer_belgeler.sefer_id`) FK string'leri modelde zaten `trip.seferler.id`
olarak nitelendi (bkz. kritik bulgu: schema eklenince self-reference dahil
TÜM FK string'leri nitelenmeli) — bu migration'ı etkilemez, FK adları
`%(table_name)s` tabanlı olduğu için değişmiyor.

Revision ID: 0056_trip_schema_move
Revises: 0055_prediction_ml_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0056_trip_schema_move"
down_revision: Union[str, Sequence[str], None] = "0055_prediction_ml_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "trip"
_TABLES = ["seferler", "seferler_log", "sefer_belgeler"]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml"
)

_INDEX_RENAMES = [
    ("ix_seferler_sefer_no", "ix_trip_seferler_sefer_no"),
    ("ix_seferler_tarih", "ix_trip_seferler_tarih"),
    ("ix_seferler_is_deleted", "ix_trip_seferler_is_deleted"),
    ("ix_seferler_guzergah_id", "ix_trip_seferler_guzergah_id"),
    ("ix_seferler_route_pair_id", "ix_trip_seferler_route_pair_id"),
    ("ix_seferler_route_simulation_id", "ix_trip_seferler_route_simulation_id"),
    ("ix_seferler_arac_id", "ix_trip_seferler_arac_id"),
    ("ix_seferler_dorse_id", "ix_trip_seferler_dorse_id"),
    ("ix_seferler_sofor_id", "ix_trip_seferler_sofor_id"),
    ("ix_seferler_periyot_id", "ix_trip_seferler_periyot_id"),
    ("ix_seferler_created_by_id", "ix_trip_seferler_created_by_id"),
    ("ix_seferler_updated_by_id", "ix_trip_seferler_updated_by_id"),
    ("ix_seferler_log_sefer_id", "ix_trip_seferler_log_sefer_id"),
    ("ix_seferler_log_created_at", "ix_trip_seferler_log_created_at"),
    ("ix_sefer_belgeler_sofor_id", "ix_trip_sefer_belgeler_sofor_id"),
    ("ix_sefer_belgeler_sefer_id", "ix_trip_sefer_belgeler_sefer_id"),
    ("ix_sefer_belgeler_ocr_durumu", "ix_trip_sefer_belgeler_ocr_durumu"),
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
