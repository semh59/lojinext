"""fix admin role yetkiler — add granular permission keys

Revision ID: 0031_fix_admin_role_yetkiler
Revises: 0030_add_missing_indexes
Create Date: 2026-06-21
"""

from alembic import op

revision = "0031_fix_admin_role_yetkiler"
down_revision = "0030_add_missing_indexes"
branch_labels = None
depends_on = None

_GRANULAR_KEYS = {
    "attribution_duzenle": True,
    "backup_al": True,
    "bakim_duzenle": True,
    "bakim_ekle": True,
    "bakim_oku": True,
    "circuit_breaker_reset": True,
    "kalibrasyon_duzenle": True,
    "kalibrasyon_goruntule": True,
    "konfig_duzenle": True,
    "konfig_goruntule": True,
    "kullanici_duzenle": True,
    "kullanici_ekle": True,
    "kullanici_goruntule": True,
    "kullanici_sil": True,
    "model_egit": True,
    "model_goruntule": True,
    "notification_rule_ekle": True,
    "notification_rule_goruntule": True,
    "rol_oku": True,
    "rol_yaz": True,
    "sistem_saglik_goruntule": True,
    "yonetim_rapor": True,
}


def upgrade() -> None:
    import json

    keys_json = json.dumps(_GRANULAR_KEYS)
    op.execute(
        f"""
        UPDATE roller
        SET yetkiler = yetkiler || '{keys_json}'::jsonb
        WHERE ad = 'admin'
        """
    )


def downgrade() -> None:
    keys_to_remove = list(_GRANULAR_KEYS.keys())
    remove_clause = " - ".join(f"'{k}'" for k in keys_to_remove)
    op.execute(
        f"""
        UPDATE roller
        SET yetkiler = yetkiler - {remove_clause}
        WHERE ad = 'admin'
        """
    )
