"""fix schema drift: JSON->JSONB, hedef_path column, seferler.guzergah_id nullable

Revision ID: 0005_fix_schema_drift
Revises: 0004_composite_indexes
Create Date: 2026-05-05 00:00:00.000000

Resolves all diffs detected by `alembic check` after the full migration chain
runs on a fresh database:

1. JSON -> JSONB type conversions for all JSON columns that the ORM model
   defines as JSONB.  Uses IF EXISTS guards so the migration is idempotent.
2. Add guzergah_kalibrasyonlari.hedef_path (BYTEA; compatible with plain
   PostgreSQL and with PostGIS environments where it becomes a geometry column).
3. Drop NOT NULL on seferler.guzergah_id (model declares it nullable=True).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0005_fix_schema_drift"
down_revision: Union[str, None] = "0004_composite_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(bind, table: str, column: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _col_is_json(bind, table: str, column: str) -> bool:
    """Return True if the column exists and its data_type is 'json' (not jsonb)."""
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c AND data_type = 'json'"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _to_jsonb(bind, table: str, column: str) -> None:
    """Convert a JSON column to JSONB if it exists and is currently JSON."""
    if _col_is_json(bind, table, column):
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {column} TYPE JSONB "
                f"USING {column}::jsonb"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. JSON → JSONB conversions ──────────────────────────────────────────
    _to_jsonb(bind, "admin_audit_log", "eski_deger")
    _to_jsonb(bind, "admin_audit_log", "yeni_deger")
    _to_jsonb(bind, "bildirim_kurallari", "kanallar")
    _to_jsonb(bind, "iceri_aktarim_gecmisi", "islem_haritasi")
    _to_jsonb(bind, "iceri_aktarim_gecmisi", "hatalar")
    _to_jsonb(bind, "iceri_aktarim_gecmisi", "rollback_baglantilari")
    _to_jsonb(bind, "konfig_gecmis", "eski_deger")
    _to_jsonb(bind, "konfig_gecmis", "yeni_deger")
    _to_jsonb(bind, "kullanici_ayarlari", "deger")
    _to_jsonb(bind, "lokasyonlar", "route_analysis")
    _to_jsonb(bind, "model_versiyonlar", "kullanilan_ozellikler")
    _to_jsonb(bind, "roller", "yetkiler")
    _to_jsonb(bind, "route_paths", "geometry")
    _to_jsonb(bind, "route_paths", "fuel_estimate_cache")
    _to_jsonb(bind, "route_paths", "route_analysis")
    _to_jsonb(bind, "sistem_konfig", "deger")
    _to_jsonb(bind, "yakit_alimlari", "route_analysis")
    _to_jsonb(bind, "yakit_formul", "katsayilar")

    # ── 2. Add guzergah_kalibrasyonlari.hedef_path ───────────────────────────
    # Stored as BYTEA (WKB) — compatible with plain PostgreSQL and PostGIS
    # environments.  Alembic env.py skips geometry type comparisons so no
    # further drift is detected even when geoalchemy2 is installed.
    if not _col_exists(bind, "guzergah_kalibrasyonlari", "hedef_path"):
        op.execute("ALTER TABLE guzergah_kalibrasyonlari ADD COLUMN hedef_path BYTEA")

    # ── 3. Make seferler.guzergah_id nullable ────────────────────────────────
    # The ORM model declares it as Optional[int] / nullable=True.
    # Drop any NOT NULL constraint that was set by earlier migrations.
    result = bind.execute(
        sa.text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'seferler' AND column_name = 'guzergah_id'"
        )
    )
    row = result.fetchone()
    if row and row[0] == "NO":
        op.execute("ALTER TABLE seferler ALTER COLUMN guzergah_id DROP NOT NULL")


def downgrade() -> None:
    bind = op.get_bind()

    # Re-apply NOT NULL on guzergah_id (best-effort — may fail if NULLs exist)
    op.execute("ALTER TABLE seferler ALTER COLUMN guzergah_id SET NOT NULL")

    # Drop hedef_path column
    if _col_exists(bind, "guzergah_kalibrasyonlari", "hedef_path"):
        op.execute("ALTER TABLE guzergah_kalibrasyonlari DROP COLUMN hedef_path")

    # JSONB → JSON downgrades are intentionally omitted:
    # JSONB is a strict superset of JSON; reverting would be lossy and is
    # never needed in practice.
