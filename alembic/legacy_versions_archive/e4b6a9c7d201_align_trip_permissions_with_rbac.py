"""align_trip_permissions_with_rbac

Revision ID: e4b6a9c7d201
Revises: b3c2d1e7f890
Create Date: 2026-03-07 18:25:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b6a9c7d201"
down_revision: Union[str, Sequence[str], None] = "b3c2d1e7f890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE roller
        SET yetkiler = COALESCE(yetkiler, '{}'::jsonb)
                       || '{"sefer:read": true, "sefer:write": true}'::jsonb
        WHERE ad = 'admin';
        """
    )

    op.execute(
        """
        UPDATE roller
        SET yetkiler = COALESCE(yetkiler, '{}'::jsonb)
                       || '{"sefer:read": true}'::jsonb
        WHERE ad IN ('mudur', 'operafor', 'izleyici');
        """
    )

    op.execute(
        """
        UPDATE roller
        SET yetkiler = (COALESCE(yetkiler, '{}'::jsonb) - 'all')
                       || '{"*": true}'::jsonb
        WHERE ad = 'superadmin';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE roller
        SET yetkiler = COALESCE(yetkiler, '{}'::jsonb) - 'sefer:read' - 'sefer:write'
        WHERE ad = 'admin';
        """
    )

    op.execute(
        """
        UPDATE roller
        SET yetkiler = COALESCE(yetkiler, '{}'::jsonb) - 'sefer:read'
        WHERE ad IN ('mudur', 'operafor', 'izleyici');
        """
    )

    op.execute(
        """
        UPDATE roller
        SET yetkiler = (COALESCE(yetkiler, '{}'::jsonb) - '*')
                       || '{"all": true}'::jsonb
        WHERE ad = 'superadmin';
        """
    )
