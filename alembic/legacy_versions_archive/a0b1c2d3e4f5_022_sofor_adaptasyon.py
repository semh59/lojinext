"""022_sofor_adaptasyon

Revision ID: a0b1c2d3e4f5
Revises: 021_notification_engine
Create Date: 2026-03-01 18:25:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a0b1c2d3e4f5"
down_revision = "021_notification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create table `sofor_adaptasyon`
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "sofor_adaptasyon" not in inspector.get_table_names():
        op.create_table(
            "sofor_adaptasyon",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("surucu_id", sa.Integer(), nullable=False),
            sa.Column(
                "guvenlik_skoru", sa.Float(), nullable=False, server_default="100.0"
            ),
            sa.Column(
                "verimlilik_skoru", sa.Float(), nullable=False, server_default="100.0"
            ),
            sa.Column(
                "eco_driving_basarisi", sa.Float(), nullable=False, server_default="0.0"
            ),
            sa.Column(
                "rutin_disi_davranis_orani",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            ),
            sa.Column(
                "son_degerlendirme_tarihi", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("onerilen_modul", sa.String(length=100), nullable=True),
            sa.Column(
                "risk_kategorisi",
                sa.String(length=50),
                nullable=True,
                server_default="Düşük",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["surucu_id"], ["soforler.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sofor_adaptasyon_surucu_id",
            "sofor_adaptasyon",
            ["surucu_id"],
            unique=True,
        )

    # 2. Add Trigger Function to Auto-Update updated_at
    trigger_func_sql = """
    CREATE OR REPLACE FUNCTION update_sofor_adaptasyon_modtime()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    op.execute(trigger_func_sql)

    # 3. Create Trigger manually
    trigger_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_sofor_adaptasyon_modtime_trigger') THEN
            CREATE TRIGGER update_sofor_adaptasyon_modtime_trigger
            BEFORE UPDATE ON sofor_adaptasyon
            FOR EACH ROW
            EXECUTE FUNCTION update_sofor_adaptasyon_modtime();
        END IF;
    END $$;
    """
    op.execute(trigger_sql)


def downgrade() -> None:
    # 1. Drop trigger and function
    op.execute(
        "DROP TRIGGER IF EXISTS update_sofor_adaptasyon_modtime_trigger ON sofor_adaptasyon"
    )
    op.execute("DROP FUNCTION IF EXISTS update_sofor_adaptasyon_modtime()")

    # 2. Drop table
    op.drop_index("ix_sofor_adaptasyon_surucu_id", table_name="sofor_adaptasyon")
    op.drop_table("sofor_adaptasyon")
