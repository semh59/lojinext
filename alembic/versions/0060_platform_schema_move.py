"""FAZ2 şema-per-modül: platform şemasının son dalgası.

`platform` şeması iki kaynaktan tablo devralır:
- `v2/modules/admin_platform/infrastructure/models.py`'nin admin_platform
  DIŞINDA kalan 3 tablosu: `sistem_konfig`, `konfig_gecmis`,
  `idempotency_keys` (bkz. o dosyanın docstring'i — admin_platform'un
  KENDİ 2 tablosu `entegrasyon_ayarlari`/`admin_audit_log` zaten
  0059'da admin_platform şemasına taşındı).
- `v2/modules/shared_kernel/infrastructure/{outbox.py,
  error_monitoring_models.py}`'nin 3 tablosu: `outbox_events`,
  `error_events`, `error_occurrences` — bunlar hiçbir tek iş modülüne ait
  değil (event_bus.py/audit_logger.py ile aynı "gerçekten paylaşılan
  altyapı" kategorisi), FAZ2 planının orijinal tasarımı bunları `platform`
  şemasına atadı (bkz. pilot planının "Pilot ötesi" notu).

Bu migration 3 ÖZEL durumu ele alır (task #20, önceki 12 "düz" şema
taşımasından farklı):

1. **RANGE partition'lı `error_occurrences`**: gerçek bir Postgres 16
   instance'ında EMPİRİK olarak doğrulandı — `ALTER TABLE <parent> SET
   SCHEMA` parent'ı taşır ama partition ÇOCUKLARINI taşımaz (Postgres'in
   kendi davranışı, SQLAlchemy/Alembic'e özgü değil). Bu yüzden
   `error_occurrences_*` çocuk tablolarını (kaç tane olursa olsun — aylık
   partition'lar `v2/modules/platform_infra/background/error_digest.py`'nin
   `create_monthly_partition` Celery task'ıyla her ayın 28'inde otomatik
   üretiliyor, bu migration'ın yazıldığı an itibarıyla kaç tane var
   bilinmiyor) DİNAMİK olarak `pg_inherits`'ten bulup tek tek taşıyoruz.
2. **Materialized view `error_hourly_stats`**: `ALTER MATERIALIZED VIEW ...
   SET SCHEMA` ile taşınır (parent tablo gibi, kendi partition'ı yok).
   Üzerindeki `idx_error_hourly_stats` ham-SQL indeksi (SQLAlchemy naming
   convention'ından DEĞİL, doğrudan `CREATE UNIQUE INDEX` ile 0011'de
   yaratıldı) MV ile birlikte otomatik taşınır, ayrı bir RENAME
   gerekmiyor (isim şema-önekli üretilmedi, literal isim).
3. **Trigger `error_events_notify`**: ayrıca gerçek Postgres'te doğrulandı
   — trigger'lar tabloya OID üzerinden bağlı, `error_events`'in şeması
   değişince trigger OTOMATİK olarak yeni şemaya "taşınır" (ayrı bir
   ALTER gerekmiyor). Trigger fonksiyonu `notify_error_event()` schema-
   agnostic bırakıldı (fonksiyonlar tablolardan bağımsız nesneler, trigger
   onu OID ile çağırır — hangi şemada olduğu önemli değil).

**alembic_version'ın kendisinin platform şemasına taşınması BU
MİGRASYONDA YAPILMIYOR** — kasıtlı olarak: Alembic kendi versiyon takibini
`context.configure()`'da (env.py, süreç başında SABİTLENİR) `version_table_
schema=None` (varsayılan, şema-siz/`search_path`'e güvenerek) ile açar; bu
migration'ın KENDİSİ aynı alembic çalıştırması (`alembic upgrade head`)
içinde yürüdüğü için, eğer `alembic_version`'ı bu migration'ın içinde
`platform`'a taşırsak, alembic bu migration'ın revision numarasını YAZMAYA
çalıştığında (upgrade() dönüşünden HEMEN sonra, hâlâ AYNI alembic
çalıştırması/transaction'ı içinde) hâlâ ESKİ (şema-siz, `public`'e sabit-
lenmiş `search_path` üzerinden çözülen) tablo referansını kullanır —
tablo artık orada olmadığı için "relation does not exist" ile patlar
(gerçek Postgres'te doğrulandı, bkz. TASKS dosyası). Bu, Alembic'in kendi
mimarisinin doğal bir "tavuk-yumurta" sınırı — tek güvenli çözüm, taşımayı
alembic'in KENDİ migration zincirinin DIŞINDA, ayrı bir tek-seferlik adım
olarak yapmak (bkz. `scripts/faz2_move_alembic_version_to_platform.py` +
`alembic/env.py`'nin `version_table_schema="platform"` eklentisi — ikisi
birlikte, bu migration'dan SONRA, belgelenmiş bir cutover adımı olarak
uygulanır).

Revision ID: 0060_platform_schema_move
Revises: 0059_admin_platform_schema_move
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from sqlalchemy import text

from alembic import op

revision: str = "0060_platform_schema_move"
down_revision: Union[str, Sequence[str], None] = "0059_admin_platform_schema_move"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "platform"
_TABLES = [
    "sistem_konfig",
    "konfig_gecmis",
    "idempotency_keys",
    "outbox_events",
    "error_events",
    "error_occurrences",
]

_SEARCH_PATH_AFTER = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports, notification, "
    "admin_platform, platform"
)
_SEARCH_PATH_BEFORE = (
    "public, import_excel, auth_rbac, fleet, driver, fuel, location, "
    "route_simulation, anomaly, prediction_ml, trip, reports, notification, "
    "admin_platform"
)

_INDEX_RENAMES = [
    ("ix_konfig_gecmis_anahtar", "ix_platform_konfig_gecmis_anahtar"),
    ("ix_konfig_gecmis_guncelleyen_id", "ix_platform_konfig_gecmis_guncelleyen_id"),
    ("ix_idempotency_keys_key", "ix_platform_idempotency_keys_key"),
]

# error_occurrences_YYYY_MM child partitions — enumerated dynamically at
# migration-run time (see docstring point 1), never hardcoded. :schema is
# bound (not string-interpolated) since it's a value, not an identifier.
_FIND_PARTITION_CHILDREN_SQL = text(
    """
    SELECT child.relname
    FROM pg_inherits
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    JOIN pg_namespace parent_ns ON parent.relnamespace = parent_ns.oid
    WHERE parent.relname = 'error_occurrences'
      AND parent_ns.nspname = :schema
    """
)


def _partition_children(connection, schema: str) -> list:
    result = connection.execute(_FIND_PARTITION_CHILDREN_SQL, {"schema": schema})
    return [row[0] for row in result]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    connection = op.get_bind()
    partition_children = _partition_children(connection, "public")

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} SET SCHEMA {_SCHEMA}")

    # Partition children do NOT move with the parent (empirically verified
    # against a real Postgres 16 instance — see docstring point 1).
    for child in partition_children:
        op.execute(f"ALTER TABLE {child} SET SCHEMA {_SCHEMA}")

    op.execute(f"ALTER MATERIALIZED VIEW error_hourly_stats SET SCHEMA {_SCHEMA}")

    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_AFTER}")

    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX {_SCHEMA}.{new} RENAME TO {old}")

    op.execute(f"ALTER ROLE CURRENT_USER SET search_path = {_SEARCH_PATH_BEFORE}")

    op.execute(f"ALTER MATERIALIZED VIEW {_SCHEMA}.error_hourly_stats SET SCHEMA public")

    connection = op.get_bind()
    partition_children = _partition_children(connection, _SCHEMA)
    for child in partition_children:
        op.execute(f"ALTER TABLE {_SCHEMA}.{child} SET SCHEMA public")

    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} SET SCHEMA public")
