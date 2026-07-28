"""FAZ2 şema-per-modül: auth_rbac'ın 4 tablosunu auth_rbac şemasına taşı.

`roller`, `kullanicilar`, `kullanici_oturumlari`, `kullanici_ayarlari` —
`v2/modules/auth_rbac/infrastructure/models.py`'nin sahip olduğu 4 tablo.
`kullanicilar` sistemin en büyük FK mıknatısı (~28 çapraz-şema kenar) —
bu taşıma FK'leri BOZMAZ: Postgres FK kısıtları OID üzerinden takip edilir,
hangi şemada yaşadıkları önemli değil (bkz. 0047'nin pilot notu).

search_path deseni 0047'de kurulan tasarım kararını takip eder (rewrite
yerine): `ALTER ROLE CURRENT_USER SET search_path` HER taşıma dalgasında
o ana kadar taşınan TÜM şemaları kümülatif olarak taşır (çünkü bu komut
listeyi DEĞİŞTİRMEZ, TAMAMEN DEĞİŞTİRİR/replace eder) — bu yüzden
downgrade bir önceki dalganın tam listesine geri döner.

İndeks yeniden adlandırması: yalnız `index=True` (naming-convention'dan
otomatik türeyen, `ix_%(column_0_label)s`) sütunlar etkilenir — açık
`Index("literal_name", ...)` çağrıları schema-agnostic oldukları için
YOK. auth_rbac'ta hiç açık Index() kullanımı yok, ama `roller` tablosunun
hiçbir `index=True` sütunu da yok (yalnız `unique=True` — UniqueConstraint,
`uq_%(table_name)s_...` şeması kullanır, schema eklenmesinden etkilenmez).

Revision ID: 0048_auth_rbac_schema_move
Revises: 0047_import_excel_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0048_auth_rbac_schema_move"
down_revision: Union[str, Sequence[str], None] = "0047_import_excel_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "auth_rbac"
_TABLES = ["roller", "kullanicilar", "kullanici_oturumlari", "kullanici_ayarlari"]

_SEARCH_PATH_AFTER = "public, import_excel, auth_rbac"
_SEARCH_PATH_BEFORE = "public, import_excel"

_INDEX_RENAMES = [
    ("ix_kullanicilar_email_bidx", "ix_auth_rbac_kullanicilar_email_bidx"),
    ("ix_kullanicilar_sofor_id", "ix_auth_rbac_kullanicilar_sofor_id"),
    (
        "ix_kullanici_oturumlari_kullanici_id",
        "ix_auth_rbac_kullanici_oturumlari_kullanici_id",
    ),
    (
        "ix_kullanici_ayarlari_kullanici_id",
        "ix_auth_rbac_kullanici_ayarlari_kullanici_id",
    ),
    ("ix_kullanici_ayarlari_modul", "ix_auth_rbac_kullanici_ayarlari_modul"),
    ("ix_kullanici_ayarlari_ayar_tipi", "ix_auth_rbac_kullanici_ayarlari_ayar_tipi"),
]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} SET SCHEMA {_SCHEMA}")
    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_AFTER}")
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{new} RENAME TO {old}")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} SET SCHEMA public")
    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_BEFORE}")
