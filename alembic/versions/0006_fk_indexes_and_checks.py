"""FK indexes + enum-like CHECK constraints (PR-2: P1.3 + P1.4)

Revision ID: 0006_fk_indexes_and_checks
Revises: 0005_fix_schema_drift
Create Date: 2026-05-06 00:00:00.000000

Closes the FK-without-index gaps and adds CHECK constraints on text columns
that the ORM treats as enums.

Indexes (idempotent — CREATE INDEX IF NOT EXISTS):
  ix_kullanici_oturumlari_kullanici_id
  ix_admin_audit_log_kullanici_id
  ix_konfig_gecmis_guncelleyen_id
  ix_iceri_aktarim_gecmisi_yukleyen_id
  ix_bildirim_kurallari_alici_rol_id

CHECK constraints (DROP IF EXISTS + ADD, also idempotent):
  yakit_alimlari.durum   IN ('Bekliyor', 'Onaylandi')
  egitim_kuyrugu.durum   IN ('WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED')
  model_versiyonlar      NOT (aktif AND fizik_only_mod)   — a model cannot be
                         both physics-only and the active production model.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0006_fk_indexes_and_checks"
down_revision: Union[str, None] = "0005_fix_schema_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES: list[tuple[str, str, str]] = [
    ("ix_kullanici_oturumlari_kullanici_id", "kullanici_oturumlari", "kullanici_id"),
    ("ix_admin_audit_log_kullanici_id", "admin_audit_log", "kullanici_id"),
    ("ix_konfig_gecmis_guncelleyen_id", "konfig_gecmis", "guncelleyen_id"),
    ("ix_iceri_aktarim_gecmisi_yukleyen_id", "iceri_aktarim_gecmisi", "yukleyen_id"),
    ("ix_bildirim_kurallari_alici_rol_id", "bildirim_kurallari", "alici_rol_id"),
]

_CHECKS: list[tuple[str, str, str]] = [
    (
        "yakit_alimlari",
        "check_yakit_durum_enum",
        "durum IN ('Bekliyor', 'Onaylandi')",
    ),
    (
        "egitim_kuyrugu",
        "check_egitim_kuyrugu_durum_enum",
        "durum IN ('WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED')",
    ),
    (
        "model_versiyonlar",
        "check_model_versiyon_aktif_fizik_xor",
        "NOT (aktif = TRUE AND fizik_only_mod = TRUE)",
    ),
]


def _table_exists(bind, table_name: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :name"
        ),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :table AND column_name = :col"
        ),
        {"table": table_name, "col": column_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()

    # ── FK indexes ───────────────────────────────────────────────────────────
    for index_name, table_name, column_name in _INDEXES:
        if not _table_exists(bind, table_name):
            continue
        if not _column_exists(bind, table_name, column_name):
            continue
        bind.execute(
            sa.text(
                f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{table_name}" ("{column_name}")'
            )
        )

    # ── CHECK constraints ────────────────────────────────────────────────────
    for table_name, constraint_name, expression in _CHECKS:
        if not _table_exists(bind, table_name):
            continue
        bind.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" '
                f'DROP CONSTRAINT IF EXISTS "{constraint_name}"'
            )
        )
        bind.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" '
                f'ADD CONSTRAINT "{constraint_name}" CHECK ({expression})'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    # CHECK constraints — drop in reverse order.
    for table_name, constraint_name, _ in _CHECKS:
        if _table_exists(bind, table_name):
            bind.execute(
                sa.text(
                    f'ALTER TABLE "{table_name}" '
                    f'DROP CONSTRAINT IF EXISTS "{constraint_name}"'
                )
            )

    # FK indexes
    for index_name, _, _ in _INDEXES:
        bind.execute(sa.text(f'DROP INDEX IF EXISTS "{index_name}"'))
