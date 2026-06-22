"""coaching delivery (Feature A.5 — koçluk etki ölçümü)

Revision ID: 0013_coaching_delivery
Revises: 0012_anomaly_action
Create Date: 2026-05-23 00:00:00.000000

Telegram üzerinden gönderilen koçluk mesajlarını ve 14 gün sonraki
skor delta'sını saklayan tablo. Bias kaynakları (mevsim, güzergah,
self-selection) yorumda not edilmiştir — UI caveat alanında gösterilir.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_coaching_delivery"
down_revision: Union[str, Sequence[str], None] = "0012_anomaly_action"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "sofor_id",
            sa.Integer,
            sa.ForeignKey("soforler.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("score_before", sa.Float, nullable=False),
        sa.Column("score_after_2w", sa.Float, nullable=True),
        sa.Column("score_delta_pct", sa.Float, nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "channel",
            sa.String(20),
            nullable=False,
            server_default="telegram",
        ),
        sa.Column("insight_category", sa.String(40), nullable=True),
        sa.Column("message_excerpt", sa.String(500), nullable=True),
        sa.Column(
            "sent_by_user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_coaching_deliveries_sofor_id_sent_at",
        "coaching_deliveries",
        ["sofor_id", "sent_at"],
    )
    op.create_index(
        "ix_coaching_deliveries_evaluated_at",
        "coaching_deliveries",
        ["evaluated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coaching_deliveries_evaluated_at", table_name="coaching_deliveries"
    )
    op.drop_index(
        "ix_coaching_deliveries_sofor_id_sent_at", table_name="coaching_deliveries"
    )
    op.drop_table("coaching_deliveries")
