"""Add System Configuration and History

Revision ID: 157d0af5715d
Revises: 936fb5546679
Create Date: 2026-02-28 11:15:47.304809

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "157d0af5715d"
down_revision: Union[str, Sequence[str], None] = "936fb5546679"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── SİSTEM KONFİG ──────────────────────────────────────────────────
    op.create_table(
        "sistem_konfig",
        sa.Column("anahtar", sa.String(length=100), primary_key=True),
        sa.Column(
            "deger", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("tip", sa.String(length=20), nullable=False),
        sa.Column("birim", sa.String(length=20), nullable=True),
        sa.Column("min_deger", sa.Float(), nullable=True),
        sa.Column("max_deger", sa.Float(), nullable=True),
        sa.Column("grup", sa.String(length=50), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column(
            "yeniden_baslat", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "son_guncelleme",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("guncelleyen_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["guncelleyen_id"], ["kullanicilar.id"], ondelete="SET NULL"
        ),
    )

    # ── KONFİG GEÇMİŞ ──────────────────────────────────────────────────
    op.create_table(
        "konfig_gecmis",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("anahtar", sa.String(length=100), nullable=False),
        sa.Column(
            "eski_deger",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "yeni_deger",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("degisiklik_sebebi", sa.Text(), nullable=True),
        sa.Column("guncelleyen_id", sa.Integer(), nullable=True),
        sa.Column(
            "zaman",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["guncelleyen_id"], ["kullanicilar.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_konfig_gecmis_anahtar", "konfig_gecmis", ["anahtar"])

    # ── BAŞLANGIÇ VERİSİ (SEED) ────────────────────────────────────────
    op.execute(
        """
        INSERT INTO sistem_konfig (anahtar, deger, tip, birim, min_deger, max_deger, grup, aciklama, yeniden_baslat) VALUES
        -- Physics
        ('physics.gravity', '9.81', 'number', 'm/s²', 9.7, 9.9, 'physics', 'Yerçekimi ivmesi', false),
        ('physics.air_density', '1.225', 'number', 'kg/m³', 0.8, 1.5, 'physics', 'Hava yoğunluğu (deniz seviyesi)', false),
        ('physics.rolling_resistance_base', '0.007', 'number', '', 0.001, 0.05, 'physics', 'Baz yuvarlanma direnci', false),

        -- Anomaly Detection
        ('anomaly.fuel_loss_threshold', '5.0', 'number', '%', 1.0, 20.0, 'anomaly', 'Yakit kaybi anomali esigi', false),
        ('anomaly.consumption_std_limit', '3.0', 'number', 'sigma', 1.0, 5.0, 'anomaly', 'Tuketim sapma limiti', false),
        ('anomaly.min_trip_km', '10.0', 'number', 'km', 1.0, 100.0, 'anomaly', 'Anomali analizi icin min sefer mesafesi', false),

        -- ML Service
        ('ml.retrain_limit', '100', 'number', 'kayit', 10, 1000, 'ml', 'Yeniden egitim icin gereken min yeni veri sayisi', false),
        ('ml.confidence_threshold_yellow', '0.6', 'number', '', 0.0, 1.0, 'ml', 'Confidence sari uyari esigi', false),
        ('ml.confidence_threshold_red', '0.4', 'number', '', 0.0, 1.0, 'ml', 'Confidence kirmizi uyari esigi (manual override)', false),
        ('ml.ensemble_main_model', '"xgboost"', 'string', '', null, null, 'ml', 'Ana ensemble modeli', true),

        -- System
        ('system.maintenance_mode', 'false', 'boolean', '', null, null, 'system', 'Sistem bakim modu', true),
        ('system.audit_retention_days', '365', 'number', 'gün', 30, 3650, 'system', 'Audit log saklama süresi', false);
        """
    )


def downgrade() -> None:
    op.drop_index("idx_konfig_gecmis_anahtar", table_name="konfig_gecmis")
    op.drop_table("konfig_gecmis")
    op.drop_table("sistem_konfig")
