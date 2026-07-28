"""FAZ2 pilot: iceri_aktarim_gecmisi tablosunu import_excel şemasına taşı.

Şema-per-module planının ilk dalgası (`TASKS/faz2-schema-per-module-postgres.md`).
`import_excel` en küçük şema (tek tablo) olduğu için pilot seçildi.

Geri alınabilir: `SET SCHEMA` metadata-only, kısa ACCESS EXCLUSIVE kilit.

`ALTER ROLE CURRENT_USER SET search_path`: repodaki ~200 raw-SQL/
`execute_query()` çağrı sitesi (`analiz_repo`/`AnalizRepository` vb.) bare
tablo adı kullanıyor (`FROM seferler`, `FROM araclar`, ...) — bu siteleri
tek tek şema-nitelemek yerine, taşınan her şema bu rolün `search_path`'ine
eklenir; Postgres unqualified adları search_path sırasıyla çözer. Bu, ileriki
`faz2-db-rol-izolasyonu` görevini zayıflatmaz: search_path yalnız ad-çözümleme
sırasıdır, `USAGE` grant'ı olmayan bir şema search_path'te listeli olsa bile
o role görünmez (bkz. görev dosyasının "Uygulama notları" bölümü).
`CURRENT_USER` kullanılıyor ki dev/test/CI/prod farklı DB kullanıcı adlarında
da hardcode gerekmesin.

İndeks yeniden adlandırması (gerçek `alembic check` koşumunda bulundu):
`alembic/env.py`'nin naming_convention'ı (`"ix": "ix_%(column_0_label)s"`)
`__table_args__`'a `schema=` eklenince `column_0_label`'ı şema-önekli üretmeye
başlıyor (`ix_iceri_aktarim_gecmisi_durum` → `ix_import_excel_iceri_aktarim_
gecmisi_durum`) — PK/FK isimleri (`%(table_name)s` tabanlı) ETKİLENMİYOR,
yalnız 3 index. DB'deki eski-isimli index'ler yeniden adlandırılmazsa
`alembic check` "removed/added index" drift'i rapor ediyor (doğrulandı).
`ALTER INDEX RENAME` metadata-only, yeniden inşa gerektirmez.

Revision ID: 0047_import_excel_schema_move
Revises: 0046_telegram_bot_tokens
Create Date: 2026-07-23

(Revision id kept <= 32 chars to fit alembic_version.version_num varchar(32).)
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0047_import_excel_schema_move"
down_revision: Union[str, Sequence[str], None] = "0046_telegram_bot_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "import_excel"
_TABLE = "iceri_aktarim_gecmisi"

# (old name, new schema-prefixed name) — see docstring.
_INDEX_RENAMES = [
    (
        "ix_iceri_aktarim_gecmisi_aktarim_tipi",
        "ix_import_excel_iceri_aktarim_gecmisi_aktarim_tipi",
    ),
    (
        "ix_iceri_aktarim_gecmisi_durum",
        "ix_import_excel_iceri_aktarim_gecmisi_durum",
    ),
    (
        "ix_iceri_aktarim_gecmisi_yukleyen_id",
        "ix_import_excel_iceri_aktarim_gecmisi_yukleyen_id",
    ),
]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
    op.execute(f"ALTER TABLE {_TABLE} SET SCHEMA {_SCHEMA}")
    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = public, {_SCHEMA}")
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{new} RENAME TO {old}")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} SET SCHEMA public")
    op.execute("ALTER ROLE CURRENT_USER SET search_path = public")
