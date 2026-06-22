"""fix_is_real_data_and_status_constraints

Revision ID: 0727e4e88432
Revises: dd39e9ba28d7
Create Date: 2026-03-05 13:24:11.546635

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0727e4e88432"
down_revision: Union[str, Sequence[str], None] = "dd39e9ba28d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Update existing data to is_real=True (Restore summary data)
    op.execute("UPDATE seferler SET is_real = TRUE WHERE is_real = FALSE;")

    # 2. Broaden durum Enum CHECK constraint
    # Drop existing
    op.drop_constraint("check_sefer_durum_enum", "seferler", type_="check")
    # Create new with all DurumEnum values
    op.create_check_constraint(
        "check_sefer_durum_enum",
        "seferler",
        "durum IN ('Bekliyor', 'Onaylandi', 'Reddedildi', 'Tamam', 'Hata', 'İptal', 'Planlandı', 'Yolda', 'Devam Ediyor', 'Tamamlandı')",
    )

    # 3. Refresh the Materialized View
    op.execute("REFRESH MATERIALIZED VIEW sefer_istatistik_mv;")


def downgrade() -> None:
    """Downgrade schema."""
    pass
