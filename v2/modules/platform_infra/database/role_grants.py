"""FAZ2 Wave 1 — PostgreSQL rol/grant bootstrap (tek doğruluk kaynağı).

Bu modül yalnız DDL üretir/uygular — hiçbir yerde `SET ROLE`/`SET LOCAL
ROLE` çağırmaz (bu, Wave 2'nin işi; bkz. TASKS/faz2-db-rol-izolasyonu-ve-
read-model-grantlari.md). Wave 1'in amacı: her modülün kendi şemasında
ALL, birkaç "okuyucu" modülün başka şemalarda yalnız SELECT (+ birkaç dar
yazma istisnası) yetkisine sahip PostgreSQL rollerini var etmek — ama
uygulamanın hâlâ tek bir login role ile çalışmaya devam etmesini
sağlamak (sıfır davranış değişikliği).

İki çağıran:
  - `alembic/versions/0061_faz2_role_grants.py` (gerçek deploy/CI yolu,
    `apply_role_grants_sync`).
  - `app/tests/conftest.py` / `tests/conftest.py` (her test oturumunun
    şema drop/recreate döngüsünden HEMEN SONRA, `apply_role_grants_async`)
    — Alembic hiç çalışmamış bir yerel test DB'sinde bile rollerin/
    grantların sıfırdan doğru kurulmasını sağlar, ve migration'ın
    GRANT'ladığı ama conftest'in yeniden yarattığı tabloların grant'sız
    kalmasını önler (ALTER DEFAULT PRIVILEGES ile).

Tüm SQL idempotent/yeniden-çalıştırılabilir: `CREATE ROLE` bir DO-block
existence-check'i içinde, `GRANT`'lar zaten doğal olarak tekrar
çalıştırılabilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection

# ── Modül → şema → rol haritası ────────────────────────────────────────────
# 14 iş modülü şeması + platform (shared_kernel'in outbox/error-monitoring
# tabloları). analytics_executive ve ai_assistant'ın kendi şeması/tablosu
# yok (yalnız read-model) — READER_SELECT_GRANTS'te ayrıca ele alınıyor.
MODULE_SCHEMA_ROLES: dict[str, str] = {
    "trip": "m_trip",
    "fleet": "m_fleet",
    "driver": "m_driver",
    "fuel": "m_fuel",
    "location": "m_location",
    "route_simulation": "m_route_simulation",
    "anomaly": "m_anomaly",
    "prediction_ml": "m_prediction_ml",
    "reports": "m_reports",
    "notification": "m_notification",
    "auth_rbac": "m_auth_rbac",
    "admin_platform": "m_admin_platform",
    "import_excel": "m_import_excel",
    "platform": "m_platform",
}

# Kendi şeması olmayan read-model rolleri (analytics_executive, ai_assistant)
NO_SCHEMA_ROLES: list[str] = ["m_analytics_executive", "m_ai_assistant"]

OPS_ROLE = "m_ops"

ALL_ROLES: list[str] = [*MODULE_SCHEMA_ROLES.values(), *NO_SCHEMA_ROLES, OPS_ROLE]

# ── Okuyucu SELECT grant matrisi ────────────────────────────────────────────
# Doğrudan kaynak okumasıyla doğrulanmış (bkz. plan dosyasının "Araştırmanın
# düzelttiği noktalar" bölümü) — görev dosyasının orijinal taslağı yanlıştı/
# eksikti, burada düzeltilmiş hali var.
READER_SELECT_GRANTS: dict[str, list[str]] = {
    "m_analytics_executive": ["trip", "fleet", "driver", "fuel", "anomaly", "location"],
    "m_reports": ["trip", "fleet", "driver", "fuel", "anomaly"],
    "m_anomaly": ["trip", "driver", "fleet"],
    "m_ai_assistant": ["fleet", "trip", "driver", "location"],
    "m_fleet": ["trip"],  # fleet/CLAUDE.md'de zaten dokümante
    "m_fuel": ["fleet", "trip"],  # önceden hiçbir yerde dokümante değildi
    "m_driver": ["trip"],  # driver/CLAUDE.md'de zaten dokümante
    "m_prediction_ml": ["fleet"],  # scheduler_task.py
    "m_route_simulation": ["location"],  # openroute_client.py SELECT yolu
}


@dataclass(frozen=True)
class WriteException:
    """Bir okuyucu/yazıcı rolüne, kendi şeması dışında dar bir yazma izni.

    `columns=None` → tüm tabloya (INSERT/DELETE gibi kolon-scope
    desteklemeyen izinler için). `columns` verilmişse yalnız o kolonlara
    (yalnız UPDATE/SELECT/REFERENCES kolon-scope destekler — Postgres
    kısıtı).
    """

    role: str
    schema: str
    table: str
    privileges: tuple[str, ...]
    columns: tuple[str, ...] | None = None


# Kaynak koduna doğrudan bakılarak doğrulanmış 5 yazma istisnası — her biri
# ilgili modülün "okuyucu" olarak SELECT-only olma varsayımını kıran, canlı/
# çağrılan bir yazma yolu (bkz. plan dosyası).
WRITE_EXCEPTIONS: list[WriteException] = [
    # analytics_executive.AnalizRepository.save_model_params() — prediction_ml'den çağrılır.
    WriteException("m_analytics_executive", "fuel", "yakit_formul", ("INSERT", "DELETE")),
    # anomaly.attribute_loss.override_attribution() — attribution_routes.py'den çağrılır.
    WriteException(
        "m_anomaly",
        "trip",
        "seferler",
        ("UPDATE",),
        columns=("arac_id", "sofor_id", "is_corrected", "correction_reason"),
    ),
    # route_simulation.openroute_client.OpenRouteClient._save_to_cache()
    WriteException(
        "m_route_simulation",
        "location",
        "lokasyonlar",
        ("UPDATE",),
        columns=("api_mesafe_km", "api_sure_saat", "ascent_m", "descent_m", "last_api_call"),
    ),
    # import_excel — toplu Excel import, repository'leri bilerek bypass eder
    # (driver/CLAUDE.md'de zaten kabul edilmiş bir istisna olarak dokümante).
    WriteException("m_import_excel", "fleet", "araclar", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "driver", "soforler", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "driver", "sofor_ad_soyad_trigram", ("INSERT",)),
    WriteException("m_import_excel", "trip", "seferler", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "fuel", "yakit_alimlari", ("INSERT", "DELETE")),
]

# m_ops'un ALL+CREATE grant aldığı 14 iş-modülü şeması (platform dahil, ama
# analytics_executive/ai_assistant hariç — onların hiç şeması yok).
_ALL_MODULE_SCHEMAS: list[str] = list(MODULE_SCHEMA_ROLES.keys())


def _create_role_stmt(role: str) -> str:
    return (
        "DO $$ BEGIN\n"
        f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN\n"
        f"    CREATE ROLE {role} NOLOGIN;\n"
        "  END IF;\n"
        "END $$;"
    )


def _self_grant_membership_stmt(role: str) -> str:
    # Dev/CI: login role süperkullanıcı olduğu için sorunsuz geçer. Prod'da
    # (login role süperkullanıcı değilse) `insufficient_privilege` fırlar —
    # migration'ı FAIL ETTİRMEDEN bir NOTICE ile DBA'ya elle-adım bırakılır.
    return (
        "DO $$ BEGIN\n"
        "  BEGIN\n"
        f"    EXECUTE format('GRANT {role} TO %I', current_user);\n"
        "  EXCEPTION WHEN insufficient_privilege THEN\n"
        f"    RAISE NOTICE '{role}: could not self-grant to %; ops must run "
        f"\"GRANT {role} TO <app_login_role>;\" manually', current_user;\n"
        "  END;\n"
        "END $$;"
    )


def _owning_schema_grant_stmts(schema: str, role: str) -> list[str]:
    return [
        f"GRANT USAGE ON SCHEMA {schema} TO {role}",
        f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}",
        f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {role}",
    ]


def _reader_select_grant_stmts(role: str, schema: str) -> list[str]:
    return [
        f"GRANT USAGE ON SCHEMA {schema} TO {role}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO {role}",
    ]


def _write_exception_stmt(exc: WriteException) -> str:
    privileges = ", ".join(exc.privileges)
    if exc.columns is not None:
        columns = ", ".join(exc.columns)
        return f"GRANT {privileges} ({columns}) ON {exc.schema}.{exc.table} TO {exc.role}"
    return f"GRANT {privileges} ON {exc.schema}.{exc.table} TO {exc.role}"


def _ops_role_stmts() -> list[str]:
    schema_list = ", ".join(_ALL_MODULE_SCHEMAS)
    stmts = [f"GRANT USAGE, CREATE ON SCHEMA {schema_list} TO {OPS_ROLE}"]
    for schema in _ALL_MODULE_SCHEMAS:
        stmts.append(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {OPS_ROLE}")
        stmts.append(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {OPS_ROLE}")
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {OPS_ROLE}"
        )
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {OPS_ROLE}"
        )
    # NOT: reset_business_data.py'nin `SET session_replication_role=replica`
    # ihtiyacı hâlâ gerçek superuser gerektirir — m_ops bunu ÇÖZMEZ, ayrı/
    # elle-onaylı bir operasyon olarak kalmaya devam eder (bkz.
    # TASKS/faz2-schema-per-module-postgres.md'nin m_ops notu). Postgres bu
    # yetkiyi rol üyeliğiyle devretmeyi desteklemez.
    return stmts


def generate_role_grant_ddl() -> list[str]:
    """Saf fonksiyon — idempotent SQL string'lerinin sıralı listesini döner.

    Hiçbir I/O yapmaz; `apply_role_grants_sync`/`apply_role_grants_async`
    bu listeyi sırayla çalıştırır.
    """
    stmts: list[str] = []

    # 1) Tüm roller (idempotent CREATE + self-grant membership)
    for role in ALL_ROLES:
        stmts.append(_create_role_stmt(role))
        stmts.append(_self_grant_membership_stmt(role))

    # 2) Her modülün kendi şemasında ALL
    for schema, role in MODULE_SCHEMA_ROLES.items():
        stmts.extend(_owning_schema_grant_stmts(schema, role))

    # 3) Okuyucuların SELECT grant'ları
    for role, schemas in READER_SELECT_GRANTS.items():
        for schema in schemas:
            stmts.extend(_reader_select_grant_stmts(role, schema))

    # 4) Dar yazma istisnaları (tablo/kolon-scope)
    for exc in WRITE_EXCEPTIONS:
        stmts.append(_write_exception_stmt(exc))

    # 5) m_ops — geniş bakım rolü
    stmts.extend(_ops_role_stmts())

    return stmts


def apply_role_grants_sync(conn: "Connection") -> None:
    """Alembic migration'ından çağrılır (`op.get_bind()`)."""
    for stmt in generate_role_grant_ddl():
        conn.execute(text(stmt))


async def apply_role_grants_async(conn: "AsyncConnection") -> None:
    """Test conftest'lerinden çağrılır — şema drop/recreate döngüsünden HEMEN
    SONRA, aynı `engine.begin()` transaction'ı içinde."""
    for stmt in generate_role_grant_ddl():
        await conn.execute(text(stmt))


def generate_role_revoke_ddl() -> list[str]:
    """`generate_role_grant_ddl()`'in tersi — migration downgrade'i için.

    `REVOKE ALL ON ALL TABLES/SEQUENCES IN SCHEMA` yalnız VAR OLAN
    nesnelere uygulanan grant'ları temizler; `ALTER DEFAULT PRIVILEGES ...
    GRANT` ile kaydedilen GELECEK-nesne varsayılanları AYRI bir katalog
    girdisi (`pg_default_acl`) — bunlar `ALTER DEFAULT PRIVILEGES ...
    REVOKE` ile açıkça temizlenmezse, o rol hâlâ bir default-ACL'de
    grantee olarak göründüğü için `DROP ROLE` "role cannot be dropped
    because some objects depend on it" hatasıyla başarısız olur.
    """
    stmts: list[str] = []

    for schema, role in MODULE_SCHEMA_ROLES.items():
        stmts.append(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {role}")
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {role}"
        )
        stmts.append(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {role}")
        stmts.append(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {role}")
        stmts.append(f"REVOKE ALL ON SCHEMA {schema} FROM {role}")

    for role, schemas in READER_SELECT_GRANTS.items():
        for schema in schemas:
            stmts.append(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE SELECT ON TABLES FROM {role}"
            )
            stmts.append(f"REVOKE SELECT ON ALL TABLES IN SCHEMA {schema} FROM {role}")
            stmts.append(f"REVOKE USAGE ON SCHEMA {schema} FROM {role}")

    for exc in WRITE_EXCEPTIONS:
        privileges = ", ".join(exc.privileges)
        stmts.append(f"REVOKE {privileges} ON {exc.schema}.{exc.table} FROM {exc.role}")

    for schema in _ALL_MODULE_SCHEMAS:
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {OPS_ROLE}"
        )
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {OPS_ROLE}"
        )
        stmts.append(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {OPS_ROLE}")
        stmts.append(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {OPS_ROLE}")
        stmts.append(f"REVOKE ALL ON SCHEMA {schema} FROM {OPS_ROLE}")

    for role in ALL_ROLES:
        stmts.append(f"DROP ROLE IF EXISTS {role}")

    return stmts


def revoke_role_grants_sync(conn: "Connection") -> None:
    """Alembic migration downgrade'inden çağrılır."""
    for stmt in generate_role_revoke_ddl():
        conn.execute(text(stmt))
