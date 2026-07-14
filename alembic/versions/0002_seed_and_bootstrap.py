"""0002 seed and bootstrap

Revision ID: 0002_seed_and_bootstrap
Revises: 0001_baseline_manual
Create Date: 2026-03-15 14:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.config import settings
from v2.modules.auth_rbac.domain.security import get_password_hash

revision: str = "0002_seed_and_bootstrap"
down_revision: Union[str, None] = "0001_baseline_manual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    admin_email = settings.SUPER_ADMIN_USERNAME
    if not settings.ADMIN_PASSWORD:
        raise RuntimeError(
            "ADMIN_PASSWORD is not set — cannot seed the bootstrap admin user. "
            "Set the ADMIN_PASSWORD environment variable before running "
            "`alembic upgrade head` (required in every environment, not only prod)."
        )
    admin_password = settings.ADMIN_PASSWORD.get_secret_value()

    conn = op.get_bind()

    roller = sa.table(
        "roller",
        sa.column("id", sa.Integer()),
        sa.column("ad", sa.String(length=50)),
        sa.column("yetkiler", postgresql.JSONB(astext_type=sa.Text())),
    )
    kullanicilar = sa.table(
        "kullanicilar",
        sa.column("id", sa.Integer()),
        sa.column("email", sa.String(length=255)),
        sa.column("ad_soyad", sa.String(length=100)),
        sa.column("sifre_hash", sa.Text()),
        sa.column("rol_id", sa.Integer()),
        sa.column("aktif", sa.Boolean()),
        sa.column("basarisiz_giris_sayisi", sa.Integer()),
    )

    role_insert = postgresql.insert(roller).values(
        ad="super_admin",
        yetkiler={"*": True},
    )
    role_upsert = role_insert.on_conflict_do_update(
        index_elements=["ad"],
        set_={"yetkiler": role_insert.excluded.yetkiler},
    )
    conn.execute(role_upsert)

    super_admin_role_id = conn.execute(
        sa.select(roller.c.id).where(roller.c.ad == "super_admin")
    ).scalar_one()

    user_insert = postgresql.insert(kullanicilar).values(
        email=admin_email,
        ad_soyad="Sistem Yonetici",
        sifre_hash=get_password_hash(admin_password),
        rol_id=super_admin_role_id,
        aktif=True,
        basarisiz_giris_sayisi=0,
    )
    user_upsert = user_insert.on_conflict_do_update(
        index_elements=["email"],
        set_={
            "ad_soyad": user_insert.excluded.ad_soyad,
            "sifre_hash": user_insert.excluded.sifre_hash,
            "rol_id": user_insert.excluded.rol_id,
            "aktif": user_insert.excluded.aktif,
            "basarisiz_giris_sayisi": 0,
        },
    )
    conn.execute(user_upsert)


def downgrade() -> None:
    """Reverse the seed bootstrap by removing the super_admin role and user.

    Note: if other rows reference the seeded admin (e.g. ``kullanicilar.olusturan_id``
    or audit logs that point at the admin's id), the DELETE will fail with an
    FK violation. Clean those dependents up before downgrading past this
    migration — blindly cascading from a seed migration is unsafe in prod.
    """
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM kullanicilar WHERE email = :email"),
        {"email": settings.SUPER_ADMIN_USERNAME},
    )
    conn.execute(sa.text("DELETE FROM roller WHERE ad = 'super_admin'"))
