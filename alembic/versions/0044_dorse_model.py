"""dorse_model

dorseler tablosuna model kolonu (2026-07-09 tasarım denetimi bulgusu).

Frontend'in "Detaylı Filtre" paneli (marka/model/min_yil/max_yil) ve
TrailerDetailModal zaten bu alanı bekliyordu (dorseService.getAll ?model=
gönderiyor, DetailModal trailer.model okuyordu) ama backend'de hiç
karşılığı yoktu — filtre sessizce hiçbir şey yapmıyordu.

Revision ID: 0044_dorse_model
Revises: 0043_arac_sigorta_motor_sasi
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0044_dorse_model"
down_revision: Union[str, Sequence[str], None] = "0043_arac_sigorta_motor_sasi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dorseler", sa.Column("model", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("dorseler", "model")
