"""telegram integration: soforler.telegram_id, seferler.onay_durumu, sefer_belgeler table

Revision ID: 0008_telegram_integration
Revises: 0007_lokasyon_distributions
Create Date: 2026-05-14

Adds:
  soforler.telegram_id          String(50) UNIQUE NULL
  seferler.onay_durumu          String(20) NULL CHECK (beklemede|onaylandi|reddedildi)
  sefer_belgeler                new table (photo + OCR results from driver bot)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_telegram_integration"
down_revision: Union[str, Sequence[str], None] = "0007_lokasyon_distributions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # soforler.telegram_id
    op.add_column(
        "soforler",
        sa.Column("telegram_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_soforler_telegram_id", "soforler", ["telegram_id"], unique=True)

    # seferler.onay_durumu
    op.add_column(
        "seferler",
        sa.Column("onay_durumu", sa.String(20), nullable=True),
    )
    op.create_check_constraint(
        "ck_seferler_onay_durumu",
        "seferler",
        "onay_durumu IS NULL OR onay_durumu IN ('beklemede','onaylandi','reddedildi')",
    )

    # sefer_belgeler
    op.create_table(
        "sefer_belgeler",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sofor_id",
            sa.Integer(),
            sa.ForeignKey("soforler.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sefer_id",
            sa.Integer(),
            sa.ForeignKey("seferler.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("telegram_mesaj_id", sa.BigInteger(), nullable=True),
        sa.Column("belge_tipi", sa.String(30), nullable=False),
        sa.Column("dosya_yolu", sa.String(500), nullable=False),
        sa.Column("ocr_ham", sa.Text(), nullable=True),
        sa.Column(
            "ocr_veri",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "ocr_durumu", sa.String(20), nullable=False, server_default="bekliyor"
        ),
        sa.Column(
            "olusturulma",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sefer_belgeler_sofor_id", "sefer_belgeler", ["sofor_id"])
    op.create_index("ix_sefer_belgeler_sefer_id", "sefer_belgeler", ["sefer_id"])
    op.create_index("ix_sefer_belgeler_ocr_durumu", "sefer_belgeler", ["ocr_durumu"])

    # bas_sofor rolü: sadece seferleri okuyabilir ve onaylayabilir
    op.execute(
        """
        INSERT INTO roller (ad, yetkiler, olusturma)
        VALUES (
            'bas_sofor',
            '{"sefer:read": true, "sefer:onayla": true}'::jsonb,
            NOW()
        )
        ON CONFLICT (ad) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("sefer_belgeler")
    op.drop_constraint("ck_seferler_onay_durumu", "seferler", type_="check")
    op.drop_column("seferler", "onay_durumu")
    op.drop_index("ix_soforler_telegram_id", table_name="soforler")
    op.drop_column("soforler", "telegram_id")
