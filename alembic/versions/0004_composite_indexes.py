"""add composite performance indexes

Revision ID: 0004_composite_indexes
Revises: 9728f5747de4
Create Date: 2026-05-05 00:00:00.000000

Adds the missing composite indexes identified in the production-readiness
audit (Bölüm 3 P1).  All CREATE INDEX IF NOT EXISTS so the migration is
idempotent and safe on existing databases.

Indexes:
  seferler:         (arac_id, tarih), (sofor_id, tarih), (arac_id, durum)
  yakit_alimlari:   (arac_id, tarih)
  prediction_results: (arac_id, tarih)  — if table exists
  outbox_events:    (dispatched, created_at) — if table exists
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_composite_indexes"
down_revision: Union[str, None] = "9728f5747de4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _col_exists(bind, table: str, column: str) -> bool:
    """Return True only if the given column exists in the given table."""
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # ── seferler ─────────────────────────────────────────────────────────────
    if _table_exists(bind, "seferler"):
        if _col_exists(bind, "seferler", "arac_id") and _col_exists(
            bind, "seferler", "tarih"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_seferler_arac_id_tarih "
                "ON seferler (arac_id, tarih DESC)"
            )
        if _col_exists(bind, "seferler", "sofor_id") and _col_exists(
            bind, "seferler", "tarih"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_seferler_sofor_id_tarih "
                "ON seferler (sofor_id, tarih DESC)"
            )
        if _col_exists(bind, "seferler", "arac_id") and _col_exists(
            bind, "seferler", "durum"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_seferler_arac_id_durum "
                "ON seferler (arac_id, durum)"
            )

    # ── yakit_alimlari ────────────────────────────────────────────────────────
    if _table_exists(bind, "yakit_alimlari"):
        if _col_exists(bind, "yakit_alimlari", "arac_id") and _col_exists(
            bind, "yakit_alimlari", "tarih"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_yakit_alimlari_arac_id_tarih "
                "ON yakit_alimlari (arac_id, tarih DESC)"
            )

    # ── prediction_results ────────────────────────────────────────────────────
    if _table_exists(bind, "prediction_results"):
        if _col_exists(bind, "prediction_results", "arac_id") and _col_exists(
            bind, "prediction_results", "tarih"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_prediction_results_arac_id_tarih "
                "ON prediction_results (arac_id, tarih DESC)"
            )

    # ── outbox_events ─────────────────────────────────────────────────────────
    if _table_exists(bind, "outbox_events"):
        if _col_exists(bind, "outbox_events", "dispatched") and _col_exists(
            bind, "outbox_events", "created_at"
        ):
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_outbox_events_dispatched_created "
                "ON outbox_events (dispatched, created_at ASC)"
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "outbox_events"):
        op.execute("DROP INDEX IF EXISTS ix_outbox_events_dispatched_created")
    if _table_exists(bind, "prediction_results"):
        op.execute("DROP INDEX IF EXISTS ix_prediction_results_arac_id_tarih")
    if _table_exists(bind, "yakit_alimlari"):
        op.execute("DROP INDEX IF EXISTS ix_yakit_alimlari_arac_id_tarih")
    if _table_exists(bind, "seferler"):
        op.execute("DROP INDEX IF EXISTS ix_seferler_arac_id_durum")
        op.execute("DROP INDEX IF EXISTS ix_seferler_sofor_id_tarih")
        op.execute("DROP INDEX IF EXISTS ix_seferler_arac_id_tarih")
