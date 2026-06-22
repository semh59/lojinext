"""add prediction results table

Revision ID: f9a1b2c3d4e7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-08
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "f9a1b2c3d4e7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "prediction_results" not in inspector.get_table_names():
        op.create_table(
            "prediction_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "task_id",
                sa.String(length=128),
                nullable=False,
                unique=True,
                index=True,
            ),
            sa.Column(
                "status", sa.String(length=32), nullable=False, server_default="queued"
            ),
            sa.Column("answer", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    existing_indexes = {
        ix["name"] for ix in inspector.get_indexes("prediction_results")
    }
    if "ix_prediction_results_task_id" not in existing_indexes:
        op.create_index(
            "ix_prediction_results_task_id",
            "prediction_results",
            ["task_id"],
            unique=True,
        )
    if "ix_prediction_results_user_id" not in existing_indexes:
        op.create_index(
            "ix_prediction_results_user_id", "prediction_results", ["user_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "prediction_results" in inspector.get_table_names():
        existing_indexes = {
            ix["name"] for ix in inspector.get_indexes("prediction_results")
        }
        if "ix_prediction_results_user_id" in existing_indexes:
            op.drop_index(
                "ix_prediction_results_user_id", table_name="prediction_results"
            )
        if "ix_prediction_results_task_id" in existing_indexes:
            op.drop_index(
                "ix_prediction_results_task_id", table_name="prediction_results"
            )
        op.drop_table("prediction_results")
