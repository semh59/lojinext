"""idempotency_keys table (P1 madde 19)

2026-07-01 prod-grade denetimi Dalga 4 madde 19: `fuel.py`/`trips.py` POST
uçlarında idempotency key yoktu — client timeout+retry çift yakıt/sefer
kaydı oluşturabiliyordu.

Revision ID: 0037_idempotency_keys
Revises: 0036_severity_onay_durumu_check
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0037_idempotency_keys"
down_revision: Union[str, Sequence[str], None] = "0036_severity_onay_durumu_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("key", "endpoint", name="uq_idempotency_key_endpoint"),
    )
    op.create_index(
        "ix_idempotency_keys_key", "idempotency_keys", ["key"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
