"""entegrasyon_ayarlari

Multi-tenant API key yönetimi (2026-07-10 kullanıcı talebi): admin panelden
harici entegrasyon (Mapbox/OpenRoute/Groq) API key'lerini girebilmeli, ama
girilen değer ASLA geri okunamaz/görüntülenemez — sadece "configured"
durumu ve son güncelleme bilgisi görünür, değer sadece güncellenebilir.

`deger_sifreli` KASITLI OLARAK models.py'deki EncryptedPII TypeDecorator'ı
KULLANMIYOR (o decorator ORM okumasında şeffaf şekilde decrypt eder — burada
istenen tam tersi: hiçbir zaman otomatik decrypt edilmemesi). Düz Text
(ciphertext) olarak saklanır; decrypt SADECE
app.core.services.integration_secrets.get_integration_secret() içinde,
gerçek API çağrısı yapılırken bellek içinde olur, hiçbir response/log/audit
satırına yazılmaz.

Revision ID: 0045_entegrasyon_ayarlari
Revises: 0044_dorse_model
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0045_entegrasyon_ayarlari"
down_revision: Union[str, Sequence[str], None] = "0044_dorse_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KNOWN_SERVICES = ("mapbox", "openroute", "groq")


def upgrade() -> None:
    op.create_table(
        "entegrasyon_ayarlari",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("servis_adi", sa.String(length=50), nullable=False),
        sa.Column("deger_sifreli", sa.Text(), nullable=True),
        sa.Column(
            "guncelleyen_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("guncellenme_tarihi", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("servis_adi", name="uq_entegrasyon_ayarlari_servis_adi"),
    )
    # Seed known services with NULL deger_sifreli — get_integration_secret()
    # falls back to the .env-sourced settings value until an admin sets one.
    conn = op.get_bind()
    for servis in _KNOWN_SERVICES:
        conn.execute(
            sa.text(
                "INSERT INTO entegrasyon_ayarlari (servis_adi) VALUES (:s) "
                "ON CONFLICT (servis_adi) DO NOTHING"
            ),
            {"s": servis},
        )


def downgrade() -> None:
    op.drop_table("entegrasyon_ayarlari")
