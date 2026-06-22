"""fuel investigation (Feature B.2)

Revision ID: 0014_fuel_investigation
Revises: 0013_coaching_delivery
Create Date: 2026-05-23 10:00:00.000000

Yakıt hırsızlığı soruşturma akış kaydı. Anomaly başına bir soruşturma
(unique anomaly_id). Status enum CheckConstraint ile kısıtlı.
JSONB evidence_files PostgreSQL özelinde.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0014_fuel_investigation"
down_revision: Union[str, Sequence[str], None] = "0013_coaching_delivery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fuel_investigations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "anomaly_id",
            sa.Integer,
            sa.ForeignKey("anomalies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("suspicion_score", sa.Float, nullable=True),
        sa.Column("suspicion_level", sa.String(20), nullable=True),
        sa.Column(
            "assigned_to_user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolution_type", sa.String(40), nullable=True),
        sa.Column(
            "evidence_files",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('open','assigned','investigating','resolved','closed')",
            name="chk_fuel_inv_status",
        ),
    )
    op.create_index("ix_fuel_inv_status", "fuel_investigations", ["status"])
    op.create_index(
        "ix_fuel_inv_assigned_to_user_id",
        "fuel_investigations",
        ["assigned_to_user_id"],
    )
    op.create_index(
        "ix_fuel_inv_created_at",
        "fuel_investigations",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_fuel_inv_created_at", table_name="fuel_investigations")
    op.drop_index(
        "ix_fuel_inv_assigned_to_user_id",
        table_name="fuel_investigations",
    )
    op.drop_index("ix_fuel_inv_status", table_name="fuel_investigations")
    op.drop_table("fuel_investigations")
