"""seferler.periyot_id: add real FK to yakit_periyotlari(id) (P1 madde 14)

2026-07-01 prod-grade denetimi Dalga 3 madde 14: `seferler.periyot_id` bir
plain Integer kolonuydu ("soft link to periyot"), DB seviyesinde hiçbir FK
kısıtı yoktu — orphan referanslar engellenmiyor, join'den sessizce düşüyordu.

`yakit_periyotlari` silindiğinde ilişkili `seferler.periyot_id` NULL'a
düşürülür (ON DELETE SET NULL) — bu zaten nullable/opsiyonel bir soft-link
alanı olduğu için sefer kaydının kendisi etkilenmez.

NOT VALID ile eklendi — mevcut satırlar migration zamanında doğrulanmaz
(prod'da orphan veri olabilir, migration'ı bloklamasın). Data-doğruluğu
teyit edildikten sonra `VALIDATE CONSTRAINT fk_sefer_periyot` ayrı bir
adımda çalıştırılabilir.

Revision ID: 0035_sefer_periyot_id_fk
Revises: 0034_route_simulations_arac_id
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0035_sefer_periyot_id_fk"
down_revision: Union[str, Sequence[str], None] = "0034_route_simulations_arac_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Orphan referansları önce NULL'a çek — aksi halde NOT VALID bile olsa
    # VALIDATE aşamasında (veya bazı Postgres sürümlerinde ADD CONSTRAINT'in
    # kendisinde) mevcut orphan satırlar sorun çıkarabilir.
    op.execute("""
        UPDATE seferler
        SET periyot_id = NULL
        WHERE periyot_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM yakit_periyotlari yp WHERE yp.id = seferler.periyot_id
          );
    """)
    op.execute("""
        ALTER TABLE seferler
          ADD CONSTRAINT fk_sefer_periyot
          FOREIGN KEY (periyot_id) REFERENCES yakit_periyotlari(id)
          ON DELETE SET NULL
          NOT VALID;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS fk_sefer_periyot;")
