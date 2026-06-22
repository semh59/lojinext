"""add_tahmin_meta_to_seferler

Revision ID: b3c2d1e7f890
Revises: 0727e4e88432
Create Date: 2026-03-07 15:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c2d1e7f890"
down_revision: Union[str, Sequence[str], None] = "0727e4e88432"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "seferler",
        sa.Column(
            "tahmin_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.create_index(
        "idx_seferler_tahmin_meta_gin",
        "seferler",
        ["tahmin_meta"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_seferler_tahmin_meta_gin", table_name="seferler")
    op.drop_column("seferler", "tahmin_meta")
