"""fix yakit_alimlari durum CHECK constraint

CHECK constraint 'Onaylandi' (ASCII) yerine 'Onaylandı' (Türkçe ı) ve
'Reddedildi' değerlerini de kapsamalı. Mevcut 'Onaylandi' verileri de
'Onaylandı'ya güncellenir.

Revision ID: 0025_fix_yakit_durum_check
Revises: 0024_page_views
Create Date: 2026-06-16
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0025_fix_yakit_durum_check"
down_revision: Union[str, Sequence[str], None] = "0024_page_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_CHECK = "durum IN ('Bekliyor', 'Onaylandi')"
_NEW_CHECK = "durum IN ('Bekliyor', 'Onaylandı', 'Reddedildi')"
_CONSTRAINT_NAME = "check_yakit_durum_enum"
_TABLE = "yakit_alimlari"


def upgrade() -> None:
    # 1. Normalize legacy ASCII data before tightening the constraint
    op.execute(
        sa.text(
            "UPDATE yakit_alimlari SET durum = 'Onaylandı' WHERE durum = 'Onaylandi'"
        )
    )

    # 2. Drop old constraint if it exists (PostgreSQL requires drop + recreate to change CHECK)
    op.execute(
        sa.text(
            f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS ck_{_TABLE}_{_CONSTRAINT_NAME}"
        )
    )

    # 3. Create corrected constraint with Turkish diacritics + Reddedildi
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        _NEW_CHECK,
    )


def downgrade() -> None:
    # Revert Reddedildi rows to Bekliyor (safest fallback — avoids data loss)
    op.execute(
        sa.text(
            "UPDATE yakit_alimlari SET durum = 'Bekliyor' WHERE durum = 'Reddedildi'"
        )
    )
    # Revert Turkish ı back to ASCII i
    op.execute(
        sa.text(
            "UPDATE yakit_alimlari SET durum = 'Onaylandi' WHERE durum = 'Onaylandı'"
        )
    )

    op.execute(
        sa.text(
            f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS ck_{_TABLE}_{_CONSTRAINT_NAME}"
        )
    )
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        _TABLE,
        _OLD_CHECK,
    )
