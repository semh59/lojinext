"""add_error_monitoring

Revision ID: 2f052e500be8
Revises: 0010_sefer_istatistik_mv
Create Date: 2026-05-18 21:37:43.728992

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f052e500be8"
down_revision: Union[str, Sequence[str], None] = "0010_sefer_istatistik_mv"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE error_layer AS ENUM
                ('db','celery','api','service','frontend','external','security','ml');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE error_severity AS ENUM ('critical','error','warning','info');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Aggregated table: one active row per unique fingerprint
    op.create_table(
        "error_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("fingerprint", sa.CHAR(16), nullable=False),
        sa.Column(
            "layer",
            postgresql.ENUM(name="error_layer", create_type=False),
            nullable=False,
        ),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(name="error_severity", create_type=False),
            nullable=False,
        ),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "first_seen",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("path", sa.String(500), nullable=True),
        sa.Column("stack_trace", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Partial unique index: only one active (unresolved) row per fingerprint
    op.create_index(
        "idx_error_events_fingerprint_active",
        "error_events",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_index(
        "idx_error_events_layer_sev", "error_events", ["layer", "severity", "last_seen"]
    )
    op.create_index(
        "idx_error_events_trace_id",
        "error_events",
        ["trace_id"],
        postgresql_where=sa.text("trace_id IS NOT NULL"),
    )

    # Raw time-series log (partitioned by month)
    op.create_table(
        "error_occurrences",
        sa.Column("id", sa.BigInteger, sa.Identity(), nullable=False),
        sa.Column("fingerprint", sa.CHAR(16), nullable=False),
        sa.Column(
            "layer",
            postgresql.ENUM(name="error_layer", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM(name="error_severity", create_type=False),
            nullable=False,
        ),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        postgresql_partition_by="RANGE (occurred_at)",
    )
    op.create_index(
        "idx_error_occurrences_time", "error_occurrences", ["occurred_at", "layer"]
    )

    # Create initial monthly partition (current month)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_05
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
    """)

    # Materialized view for dashboard (refreshed by Celery beat every 5 min)
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS error_hourly_stats AS
        SELECT
            date_trunc('hour', occurred_at) AS hour,
            layer,
            severity,
            COUNT(*) AS event_count
        FROM error_occurrences
        WHERE occurred_at > now() - INTERVAL '24 hours'
        GROUP BY 1, 2, 3;
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_error_hourly_stats "
        "ON error_hourly_stats(hour, layer, severity);"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS error_hourly_stats;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_05;")
    op.execute("DROP TABLE IF EXISTS error_occurrences CASCADE;")
    op.drop_table("error_events")
    op.execute("DROP TYPE IF EXISTS error_severity;")
    op.execute("DROP TYPE IF EXISTS error_layer;")
