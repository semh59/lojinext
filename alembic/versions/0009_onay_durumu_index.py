"""performance: partial index on seferler.onay_durumu for pending-approval queries

Revision ID: 0009_onay_durumu_index
Revises: 0008_telegram_integration
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0009_onay_durumu_index"
down_revision: Union[str, None] = "0008_telegram_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial index: covers only rows where onay_durumu IS NOT NULL.
    # The most frequent query (beklemede approval queue) hits this index directly.
    op.create_index(
        "ix_seferler_onay_durumu",
        "seferler",
        ["onay_durumu"],
        postgresql_where="onay_durumu IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_seferler_onay_durumu", table_name="seferler")
