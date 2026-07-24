"""FAZ2 — DB rol izolasyonu Wave 1: 17 PostgreSQL rolü + grant matrisi.

Bu migration, `TASKS/faz2-db-rol-izolasyonu-ve-read-model-grantlari.md`'nin
Wave 1'i: her modülün kendi şemasında ALL, birkaç "okuyucu" modülün başka
şemalarda yalnız SELECT (+ birkaç dar yazma istisnası) yetkisine sahip
olduğu PostgreSQL rollerini var eder. **Bu migration hiçbir yerde `SET
ROLE`/`SET LOCAL ROLE` çağırmaz** — uygulama hâlâ tek bir login role ile
çalışmaya devam eder, sıfır davranış değişikliği. Enforcement (rollerin
gerçekten bağlanması) ayrı bir Wave 2 görevi, ayrı bir onay gerektiriyor.

Tüm DDL `v2/modules/platform_infra/database/role_grants.py`'de üretiliyor
(tek doğruluk kaynağı) — bu dosya yalnız `apply_role_grants_sync`'i
çağırıyor. Aynı fonksiyon `app/tests/conftest.py`/`tests/conftest.py`
tarafından her test oturumunun şema drop/recreate döngüsünden SONRA da
çağrılıyor — bu, Alembic hiç çalışmamış bir yerel test DB'sinde bile
rollerin/grantların sıfırdan doğru kurulmasını sağlıyor (bkz. o dosyanın
docstring'i, ve plan dosyasının "test-ortamı riski" bulgusu).

Roller `NOLOGIN` — hiçbir gerçek bağlantı bu rollerle açılmıyor, yalnız
gelecekteki bir Wave 2'nin `SET LOCAL ROLE <rol>` çağrısı için hazır
bekliyorlar. `downgrade()` güvenli: roller hiçbir nesneye sahip değil
(yalnız grant taşıyorlar), `REVOKE ALL` + `DROP ROLE` sorunsuz çalışır.

Revision ID: 0061_faz2_role_grants
Revises: 0060_platform_schema_move
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0061_faz2_role_grants"
down_revision: Union[str, Sequence[str], None] = "0060_platform_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import revoke_role_grants_sync

    revoke_role_grants_sync(op.get_bind())
