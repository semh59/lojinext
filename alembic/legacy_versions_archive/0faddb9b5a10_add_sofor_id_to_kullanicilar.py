"""Add sofor_id column to kullanicilar (aligns ORM with schema)

Revision ID: 0faddb9b5a10
Revises: f9a1b2c3d4e7
Create Date: 2026-03-08 18:25:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0faddb9b5a10"
down_revision: Union[str, Sequence[str], None] = "f9a1b2c3d4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE IF EXISTS kullanicilar
        ADD COLUMN IF NOT EXISTS sofor_id INTEGER NULL
            REFERENCES soforler(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kullanicilar_sofor_id ON kullanicilar(sofor_id)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_kullanicilar_sofor_id")
    op.execute("ALTER TABLE IF EXISTS kullanicilar DROP COLUMN IF EXISTS sofor_id")
