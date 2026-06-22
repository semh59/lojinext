"""add distributions JSONB column to lokasyonlar

Revision ID: 0007_lokasyon_distributions
Revises: 0006_fk_indexes_and_checks
Create Date: 2026-05-12

Adds:
  lokasyonlar.distributions  JSONB NULL
    — stores road-class + grade-class distribution as % of total route distance,
      plus weighted average grade. Populated by LokasyonService.analyze_route().

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_lokasyon_distributions"
down_revision: Union[str, Sequence[str], None] = "0006_fk_indexes_and_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lokasyonlar",
        sa.Column(
            "distributions", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("lokasyonlar", "distributions")
