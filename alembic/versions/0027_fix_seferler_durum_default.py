"""fix seferler.durum server_default to match English CHECK constraint

Migration 0001 set server_default='Tamam'; migration 0022 changed the CHECK
to IN ('Planned','Completed','Cancelled') but did not update the column
default. Any raw INSERT that omits durum would produce 'Tamam' which violates
the constraint. This migration aligns the server_default with the CHECK.

Revision ID: 0027_fix_seferler_durum_default
Revises: 0026_sefer_onaylayan_id
Create Date: 2026-06-16
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0027_fix_seferler_durum_default"
down_revision: Union[str, Sequence[str], None] = "0026_sefer_onaylayan_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "seferler",
        "durum",
        existing_type=sa.String(length=20),
        server_default=sa.text("'Planned'"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "seferler",
        "durum",
        existing_type=sa.String(length=20),
        server_default=sa.text("'Tamam'"),
        existing_nullable=False,
    )
