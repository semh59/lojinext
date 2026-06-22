"""Admin Base: Roles, Users, Sessions, Audit Log

Revision ID: 936fb5546679
Revises: 5144dc178795
Create Date: 2026-02-28 11:11:54.037046

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "936fb5546679"
down_revision: Union[str, Sequence[str], None] = "5144dc178795"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ROLLER ────────────────────────────────────────────────────────
    op.create_table(
        "roller",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ad", sa.String(length=50), nullable=False),
        sa.Column(
            "yetkiler",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "olusturma",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("ad"),
    )

    # Başlangıç rolleri
    op.execute(
        """
        INSERT INTO roller (ad, yetkiler) VALUES
        ('super_admin', '{"*": true}'),
        ('admin', '{
            "kullanici_goruntule": true, "kullanici_ekle": true,
            "kullanici_duzenle": true, "kullanici_sil": false,
            "model_goruntule": true, "model_egit": true,
            "model_aktif_et": true, "model_sil": false,
            "konfig_goruntule": true, "konfig_duzenle": true,
            "bakim_goruntule": true, "bakim_ekle": true, "bakim_duzenle": true,
            "import_goruntule": true, "import_rollback": true,
            "attribution_override": true,
            "guzergah_override": true,
            "sistem_saglik_goruntule": true,
            "circuit_breaker_reset": true,
            "backup_goruntule": true, "backup_al": true,
            "bildirim_yonet": true,
            "rag_yonet": true
        }'),
        ('mudur', '{
            "model_goruntule": true,
            "bakim_goruntule": true, "bakim_ekle": true,
            "import_goruntule": true,
            "sistem_saglik_goruntule": true
        }'),
        ('operafor', '{
            "bakim_goruntule": true, "bakim_ekle": true,
            "import_goruntule": true
        }'),
        ('izleyici', '{
            "model_goruntule": true,
            "bakim_goruntule": true,
            "sistem_saglik_goruntule": true
        }');
        """
    )

    # ── KULLANICILAR (TRANSFORMASYON) ──────────────────────────────────
    # Mevcut tablodan verileri koruyarak dönüştür
    # 1. Yeni kolonlar ekle
    op.add_column(
        "kullanicilar", sa.Column("email", sa.String(length=255), nullable=True)
    )
    op.add_column("kullanicilar", sa.Column("rol_id", sa.Integer(), nullable=True))
    op.add_column(
        "kullanicilar",
        sa.Column("son_giris_ip", sa.dialects.postgresql.INET(), nullable=True),
    )
    op.add_column(
        "kullanicilar",
        sa.Column(
            "basarisiz_giris_sayisi", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "kullanicilar",
        sa.Column("kilitli_kadar", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kullanicilar",
        sa.Column(
            "sifre_degisim_tarihi",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "kullanicilar", sa.Column("sifre_sifir_token", sa.Text(), nullable=True)
    )
    op.add_column(
        "kullanicilar",
        sa.Column("sifre_sifir_son", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kullanicilar",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "kullanicilar", sa.Column("olusturan_id", sa.Integer(), nullable=True)
    )

    # 2. Mevcut veriyi migrate et
    op.execute(
        "UPDATE kullanicilar SET email = kullanici_adi || '@lojinext.internal' WHERE email IS NULL"
    )
    op.execute(
        "UPDATE kullanicilar SET rol_id = (SELECT id FROM roller WHERE ad = 'admin') WHERE rol = 'admin'"
    )
    op.execute(
        "UPDATE kullanicilar SET rol_id = (SELECT id FROM roller WHERE ad = 'super_admin') WHERE rol = 'super_admin'"
    )
    op.execute(
        "UPDATE kullanicilar SET rol_id = (SELECT id FROM roller WHERE ad = 'izleyici') WHERE rol_id IS NULL"
    )

    # 3. Kısıtlamaları ekle
    op.alter_column("kullanicilar", "email", nullable=False)
    op.alter_column("kullanicilar", "rol_id", nullable=False)
    op.create_unique_constraint("uq_kullanici_email", "kullanicilar", ["email"])
    op.create_foreign_key(
        "fk_kullanici_rol", "kullanicilar", "roller", ["rol_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_kullanici_olusturan",
        "kullanicilar",
        "kullanicilar",
        ["olusturan_id"],
        ["id"],
    )
    op.create_index("idx_kullanici_email", "kullanicilar", ["email"])

    # 4. Eski kolonları kaldır (rol kolonunu kaldırıyoruz çünkü rol_id geldi)
    op.drop_column("kullanicilar", "rol")
    op.drop_column("kullanicilar", "kullanici_adi")  # email artık ana kimlik

    # ── OTURUMLAR ──────────────────────────────────────────────────────
    op.create_table(
        "kullanici_oturumlari",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kullanici_id", sa.Integer(), nullable=False),
        sa.Column("access_token_hash", sa.Text(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=True),
        sa.Column("ip_adresi", sa.dialects.postgresql.INET(), nullable=False),
        sa.Column("tarayici", sa.Text(), nullable=True),
        sa.Column(
            "olusturma",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "son_aktivite",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("access_bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_bitis", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aktif", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("iptal_sebebi", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["kullanici_id"], ["kullanicilar.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "idx_oturum_kullanici", "kullanici_oturumlari", ["kullanici_id", "aktif"]
    )

    # ── AUDİT LOG ──────────────────────────────────────────────────────
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kullanici_id", sa.Integer(), nullable=True),
        sa.Column("kullanici_email", sa.String(length=255), nullable=True),
        sa.Column("aksiyon_tipi", sa.String(length=100), nullable=False),
        sa.Column("hedef_tablo", sa.String(length=100), nullable=True),
        sa.Column("hedef_id", sa.Text(), nullable=True),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column(
            "eski_deger",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "yeni_deger",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("ip_adresi", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("tarayici", sa.Text(), nullable=True),
        sa.Column("istek_id", sa.String(length=36), nullable=True),
        sa.Column("basarili", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("hata_mesaji", sa.Text(), nullable=True),
        sa.Column("sure_ms", sa.Integer(), nullable=True),
        sa.Column(
            "zaman",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["kullanici_id"], ["kullanicilar.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_audit_zaman", "admin_audit_log", [sa.text("zaman DESC")])

    # ── MODEL VERSİYONLAR (TRANSFORMASYON) ──────────────────────────────
    op.rename_table("model_versions", "model_versiyonlar")
    op.add_column("model_versiyonlar", sa.Column("mape", sa.Float(), nullable=True))
    op.add_column("model_versiyonlar", sa.Column("rmse", sa.Float(), nullable=True))
    op.add_column(
        "model_versiyonlar", sa.Column("model_dosya_yolu", sa.Text(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("model_boyut_kb", sa.Integer(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("egitim_suresi_sn", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar",
        sa.Column(
            "kullanilan_ozellikler",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "model_versiyonlar", sa.Column("xgboost_agirligi", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("lightgbm_agirligi", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("rf_agirligi", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("gb_agirligi", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("fizik_agirligi", sa.Float(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar",
        sa.Column(
            "fizik_only_mod", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "model_versiyonlar", sa.Column("fizik_only_sebebi", sa.Text(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar",
        sa.Column("egiten_kullanici_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "model_versiyonlar",
        sa.Column(
            "tetikleyici",
            sa.String(length=50),
            server_default="otomatik",
            nullable=False,
        ),
    )

    op.alter_column("model_versiyonlar", "version", new_column_name="versiyon")
    op.alter_column("model_versiyonlar", "is_active", new_column_name="aktif")
    op.alter_column("model_versiyonlar", "r2_score", new_column_name="r2_skoru")
    op.alter_column("model_versiyonlar", "created_at", new_column_name="egitim_tarihi")

    op.drop_column("model_versiyonlar", "model_type")
    op.drop_column("model_versiyonlar", "params_json")
    op.drop_column("model_versiyonlar", "sample_count")

    op.create_foreign_key(
        "fk_model_egiten",
        "model_versiyonlar",
        "kullanicilar",
        ["egiten_kullanici_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_arac_versiyon", "model_versiyonlar", ["arac_id", "versiyon"]
    )
    op.create_index(
        "idx_model_arac_versiyon",
        "model_versiyonlar",
        ["arac_id", sa.text("versiyon DESC")],
    )


def downgrade() -> None:
    # Rollback sequence (reverse order of upgrade)
    op.drop_table("admin_audit_log")
    op.drop_table("kullanici_oturumlari")

    # model_versiyonlar rollback
    op.alter_column("model_versiyonlar", "versiyon", new_column_name="version")
    op.alter_column("model_versiyonlar", "aktif", new_column_name="is_active")
    op.alter_column("model_versiyonlar", "r2_skoru", new_column_name="r2_score")
    op.alter_column("model_versiyonlar", "egitim_tarihi", new_column_name="created_at")
    op.add_column(
        "model_versiyonlar", sa.Column("model_type", sa.String(50), nullable=True)
    )
    op.add_column(
        "model_versiyonlar", sa.Column("params_json", sa.Text(), nullable=True)
    )
    op.add_column(
        "model_versiyonlar",
        sa.Column("sample_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.rename_table("model_versiyonlar", "model_versions")

    # kullanicilar rollback
    op.add_column("kullanicilar", sa.Column("rol", sa.String(length=20), nullable=True))
    op.add_column(
        "kullanicilar", sa.Column("kullanici_adi", sa.String(length=50), nullable=True)
    )
    op.execute("UPDATE kullanicilar SET kullanici_adi = split_part(email, '@', 1)")
    op.execute(
        "UPDATE kullanicilar SET rol = (SELECT ad FROM roller WHERE id = rol_id)"
    )
    op.drop_constraint("fk_kullanici_rol", "kullanicilar")
    op.drop_column("kullanicilar", "rol_id")
    op.drop_column("kullanicilar", "email")
    # ... more drops here if perfect rollback is needed, but typically deletions are enough

    op.drop_table("roller")
