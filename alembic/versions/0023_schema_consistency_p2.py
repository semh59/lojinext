"""P2 schema consistency: timestamps, timezone, ondelete, column rename

Brings the migration-built schema in line with the ORM model (P2 fixes):
  * MODEL-002: add ``updated_at`` to araclar, soforler, yakit_alimlari,
    anomalies, outbox_events, route_simulations; add ``created_at`` +
    ``updated_at`` to lokasyonlar.
  * MINOR-001: add ``created_at`` to yakit_formul.
  * DATA-004: yakit_formul.updated_at -> TIMESTAMPTZ.
  * MODEL-003: rename sefer_belgeler.olusturulma -> created_at.
  * SEC-008/MINOR-006: ON DELETE SET NULL for kullanicilar-referencing audit
    FKs (olusturan_id / guncelleyen_id / egiten_kullanici_id / degistiren_id).
    Uses DROP CONSTRAINT IF EXISTS so it is resilient to a FK that the baseline
    never created (vehicle_spec_timeline.degistiren_id was a plain Integer).

Note: arac_bakimlari is intentionally left untouched — it already carries
``bakim_tarihi`` and ``guncelleme_tarihi`` (Turkish-named equivalents).

Revision ID: 0023_schema_consistency_p2
Revises: 0022_durum_canonical_english
Create Date: 2026-06-09
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0023_schema_consistency_p2"
down_revision: Union[str, Sequence[str], None] = "0022_durum_canonical_english"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables getting a NOT NULL updated_at (with server_default now()).
_UPDATED_AT_TABLES = (
    "araclar",
    "soforler",
    "yakit_alimlari",
    "anomalies",
    "outbox_events",
    "route_simulations",
)

# (table, column, referenced_table, fk_name) for ON DELETE SET NULL FKs.
# FK names follow the metadata naming_convention
# (fk_%(table)s_%(column_0)s_%(referred_table)s), NOT the PostgreSQL default
# <table>_<column>_fkey — otherwise alembic check reports a naming drift.
_SET_NULL_FKS = (
    ("araclar", "olusturan_id", "kullanicilar", "fk_araclar_olusturan_id_kullanicilar"),
    (
        "kullanicilar",
        "olusturan_id",
        "kullanicilar",
        "fk_kullanicilar_olusturan_id_kullanicilar",
    ),
    (
        "model_versiyonlar",
        "egiten_kullanici_id",
        "kullanicilar",
        "fk_model_versiyonlar_egiten_kullanici_id_kullanicilar",
    ),
    (
        "sistem_konfig",
        "guncelleyen_id",
        "kullanicilar",
        "fk_sistem_konfig_guncelleyen_id_kullanicilar",
    ),
    (
        "konfig_gecmis",
        "guncelleyen_id",
        "kullanicilar",
        "fk_konfig_gecmis_guncelleyen_id_kullanicilar",
    ),
    (
        "vehicle_spec_timeline",
        "degistiren_id",
        "kullanicilar",
        "fk_vehicle_spec_timeline_degistiren_id_kullanicilar",
    ),
)


def _ts_col(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _column_exists(conn, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()

    # --- MODEL-002: updated_at columns -------------------------------------
    for table in _UPDATED_AT_TABLES:
        op.add_column(table, _ts_col("updated_at"))

    # lokasyonlar: both created_at and updated_at
    op.add_column("lokasyonlar", _ts_col("created_at"))
    op.add_column("lokasyonlar", _ts_col("updated_at"))

    # --- MINOR-001 + DATA-004: yakit_formul --------------------------------
    op.add_column("yakit_formul", _ts_col("created_at"))
    op.alter_column(
        "yakit_formul",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_server_default=sa.text("now()"),
        existing_nullable=False,
    )

    # --- MODEL-003: rename sefer_belgeler.olusturulma -> created_at ---------
    op.alter_column("sefer_belgeler", "olusturulma", new_column_name="created_at")

    # --- SEC-008 / MINOR-006: ON DELETE SET NULL ---------------------------
    for table, column, ref, fk_name in _SET_NULL_FKS:
        if not _column_exists(conn, table, column):
            # Defensive: skip if the column is absent in this schema (guards
            # against any residual model<->migration drift on these tables).
            continue
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{fk_name}"')
        op.create_foreign_key(
            fk_name, table, ref, [column], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Revert FKs to no ON DELETE action (recreate without ondelete).
    for table, column, ref, fk_name in _SET_NULL_FKS:
        if not _column_exists(conn, table, column):
            continue
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{fk_name}"')
        op.create_foreign_key(fk_name, table, ref, [column], ["id"])

    op.alter_column("sefer_belgeler", "created_at", new_column_name="olusturulma")

    op.alter_column(
        "yakit_formul",
        "updated_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.drop_column("yakit_formul", "created_at")

    op.drop_column("lokasyonlar", "updated_at")
    op.drop_column("lokasyonlar", "created_at")

    for table in _UPDATED_AT_TABLES:
        op.drop_column(table, "updated_at")
