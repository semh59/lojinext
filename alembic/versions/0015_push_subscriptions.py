"""push subscriptions (Reports v2 RV2.PWA)

Revision ID: 0015_push_subscriptions
Revises: 0014_fuel_investigation
Create Date: 2026-05-27 19:00:00.000000

Web Push (VAPID) abonelik kayıtları. Bir kullanıcının birden çok cihazı
(tarayıcı/PWA install) olabilir → unique constraint endpoint üzerinde.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0015_push_subscriptions"
down_revision: Union[str, Sequence[str], None] = "0014_fuel_investigation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text, nullable=False, unique=True),
        sa.Column("p256dh", sa.Text, nullable=False),
        sa.Column("auth", sa.Text, nullable=False),
        sa.Column("user_agent", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_push_subscriptions_user_id",
        "push_subscriptions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_id", "push_subscriptions")
    op.drop_table("push_subscriptions")
