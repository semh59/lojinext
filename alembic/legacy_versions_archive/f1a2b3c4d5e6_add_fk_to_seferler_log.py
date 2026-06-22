"""add_fk_to_seferler_log

Revision ID: f1a2b3c4d5e6
Revises: e4b6a9c7d201
Create Date: 2026-03-07 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4b6a9c7d201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM seferler_log
        WHERE sefer_id IS NULL
           OR sefer_id NOT IN (SELECT id FROM seferler)
        """
    )

    op.create_foreign_key(
        "fk_seferler_log_sefer_id",
        "seferler_log",
        "seferler",
        ["sefer_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_seferler_log_sefer_id",
        "seferler_log",
        type_="foreignkey",
    )
