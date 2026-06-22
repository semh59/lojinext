"""add missing indexes: prediction_results.status + anomaly status combo

Revision ID: 0030_add_missing_indexes
Revises: 0029_sefer_durum_dual_fix
Create Date: 2026-06-21 18:00:00.000000

- ix_prediction_results_status: polling sorgularında GET /trips/tasks/{id}/status
  tam table scan yapmaması için gerekli.
- idx_anomaly_status_combo: dashboard ?status=open|acknowledged|resolved filtresi
  için (resolved_at, acknowledged_at) compound index.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0030_add_missing_indexes"
down_revision: Union[str, Sequence[str], None] = "0029_sefer_durum_dual_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_prediction_results_status",
        "prediction_results",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_anomaly_status_combo",
        "anomalies",
        ["resolved_at", "acknowledged_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_anomaly_status_combo", table_name="anomalies")
    op.drop_index("ix_prediction_results_status", table_name="prediction_results")
