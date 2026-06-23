"""seferler: add is_corrected + correction_reason (manual attribution override audit)

AttributionService.override_attribution writes is_corrected=True and
correction_reason when an operator manually re-assigns a trip's arac/sofor — but
the seferler table never had these columns, so base_repository.update silently
dropped them (it filters kwargs to physical columns). The override was applied but
never flagged. Add the columns so the correction audit actually persists.

Revision ID: 0033_sefer_correction_audit
Revises: 0032_iceri_aktarim_fk_ondelete
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0033_sefer_correction_audit"
down_revision: Union[str, Sequence[str], None] = "0032_iceri_aktarim_fk_ondelete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seferler",
        sa.Column(
            "is_corrected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "seferler",
        sa.Column("correction_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("seferler", "correction_reason")
    op.drop_column("seferler", "is_corrected")
