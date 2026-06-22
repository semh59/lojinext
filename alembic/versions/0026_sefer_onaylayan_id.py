"""sefer onaylayan_id column

Revision ID: 0026_sefer_onaylayan_id
Revises: 0025_fix_yakit_durum_check
Create Date: 2026-06-16

"""

import sqlalchemy as sa

from alembic import op

revision = "0026_sefer_onaylayan_id"
down_revision = "0025_fix_yakit_durum_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seferler",
        sa.Column(
            "onaylayan_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("seferler", "onaylayan_id")
