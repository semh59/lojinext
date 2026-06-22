"""page_views table — Faz 3 kullanım analitiği (route/user/timestamp).

Revision ID: 0024_page_views
Revises: 0023_schema_consistency_p2
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0024_page_views"
down_revision: Union[str, Sequence[str], None] = "0023_schema_consistency_p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route", sa.String(length=255), nullable=False),
        # user_id FK YOK — analitik decoupled/best-effort; süper-admin synthetic
        # id'leri ve silinmiş kullanıcılar FK violation yaratmasın.
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Index adları model'in index=True auto-naming'iyle aynı (ix_<table>_<col>)
    # olmalı; yoksa `alembic check` drift raporlar.
    op.create_index("ix_page_views_created_at", "page_views", ["created_at"])
    op.create_index("ix_page_views_route", "page_views", ["route"])


def downgrade() -> None:
    op.drop_index("ix_page_views_route", table_name="page_views")
    op.drop_index("ix_page_views_created_at", table_name="page_views")
    op.drop_table("page_views")
