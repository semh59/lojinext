"""page_views.user_id: add real FK to kullanicilar(id) (Tier A madde 4)

2026-07-02 prod-grade denetimi Tier A madde 4: `page_views.user_id` bir
plain nullable Integer kolonuydu, DB seviyesinde hiçbir FK kısıtı yoktu —
diğer tüm audit alanlarının (`created_by_id`, `updated_by_id` vb.,
`ForeignKey("kullanicilar.id", ondelete="SET NULL")`) aksine.

`page_view_repo.record()`'un tek yazıcısı (`analytics.py::record_page_view`)
zaten süper-admin synthetic id'lerini (id<=0) `None`'a çeviriyor (`_uid()`
helper) — bu FK'yi eklemek güvenli, mevcut yazma yolunu bozmaz.

Kullanıcı silinirse `page_views.user_id` NULL'a düşürülür (ON DELETE SET
NULL) — sayfa görüntüleme kaydının kendisi (anonim analitik olarak) korunur.

NOT VALID ile eklendi — mevcut satırlar migration zamanında doğrulanmaz.

Revision ID: 0038_page_views_user_id_fk
Revises: 0037_idempotency_keys
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0038_page_views_user_id_fk"
down_revision: Union[str, Sequence[str], None] = "0037_idempotency_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE page_views
        SET user_id = NULL
        WHERE user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM kullanicilar k WHERE k.id = page_views.user_id
          );
    """)
    op.execute("""
        ALTER TABLE page_views
          ADD CONSTRAINT fk_page_views_user
          FOREIGN KEY (user_id) REFERENCES kullanicilar(id)
          ON DELETE SET NULL
          NOT VALID;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE page_views DROP CONSTRAINT IF EXISTS fk_page_views_user;")
