"""fix_error_occurrences_partition

Revision ID: 0021_fix_partition
Revises: 9cefef01eaec
Create Date: 2026-05-31 09:50:00.000000

Fixes LOJINEXT-180: error_occurrences partition for 2026-05-31 was not created
by the initial migration (0011_add_error_monitoring.py). This migration ensures
the partition exists.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_fix_partition"
down_revision: Union[str, Sequence[str], None] = ["0020_sefer_rsim_fk", "9cefef01eaec"]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create partition for May 2026 if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_05
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
    """)

    # Create partitions for June-October 2026 for future-proofing
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_06
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_07
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_08
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_09
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS error_occurrences_2026_10
        PARTITION OF error_occurrences
        FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_10;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_09;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_08;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_07;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_06;")
    op.execute("DROP TABLE IF EXISTS error_occurrences_2026_05;")
