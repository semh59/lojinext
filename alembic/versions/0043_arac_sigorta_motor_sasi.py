"""arac_sigorta_motor_sasi

araclar tablosuna sigorta_tarihi/motor_no/sasi_no kolonları (2026-07-09
canlı-hazırlık denetimi bulgusu).

Frontend "Araç Ekle" formu (VehicleModal.tsx) bu 3 alanı belirgin
etiketlerle topluyordu ve `Vehicle` tipinde tanımlıydı, ama backend'in
HİÇBİR katmanında (DB şeması, Pydantic şeması, servis) karşılığı yoktu —
canlı test kanıtı: POST /vehicles/ 201 dönüyor, gönderilen sigorta_tarihi/
motor_no/sasi_no yanıtta hiç yok (Pydantic'in extra="ignore" varsayılanı
sessizce atıyordu). Operatör bu alanları doldurup "kaydedildi" sanıyor,
hiçbir zaman saklanmıyordu.

Revision ID: 0043_arac_sigorta_motor_sasi
Revises: 0042_seed_fuel_cov_threshold
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043_arac_sigorta_motor_sasi"
down_revision: Union[str, Sequence[str], None] = "0042_seed_fuel_cov_threshold"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("araclar", sa.Column("sigorta_tarihi", sa.Date(), nullable=True))
    op.add_column("araclar", sa.Column("motor_no", sa.String(length=50), nullable=True))
    op.add_column("araclar", sa.Column("sasi_no", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("araclar", "sasi_no")
    op.drop_column("araclar", "motor_no")
    op.drop_column("araclar", "sigorta_tarihi")
