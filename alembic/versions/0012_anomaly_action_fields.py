"""anomaly action fields (acknowledge / resolve)

Revision ID: 0012_anomaly_action
Revises: 9cefef01eaec
Create Date: 2026-05-22 10:30:00.000000

Adds operator workflow fields to ``anomalies``: acknowledged_at/by,
resolved_at/by, resolution_notes. Existing rows keep NULLs → status='open'.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_anomaly_action"
down_revision: Union[str, Sequence[str], None] = "9cefef01eaec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("anomalies") as batch_op:
        batch_op.add_column(
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("acknowledged_by", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("resolved_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("resolution_notes", sa.Text(), nullable=True))

    op.create_index(
        "ix_anomalies_acknowledged_at",
        "anomalies",
        ["acknowledged_at"],
    )
    op.create_index(
        "ix_anomalies_resolved_at",
        "anomalies",
        ["resolved_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_anomalies_resolved_at", table_name="anomalies")
    op.drop_index("ix_anomalies_acknowledged_at", table_name="anomalies")
    with op.batch_alter_table("anomalies") as batch_op:
        batch_op.drop_column("resolution_notes")
        batch_op.drop_column("resolved_by")
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("acknowledged_by")
        batch_op.drop_column("acknowledged_at")
