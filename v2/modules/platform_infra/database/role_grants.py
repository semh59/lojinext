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
    "m_fleet": ["trip"],  # already documented in fleet/CLAUDE.md
    "m_fuel": ["fleet", "trip"],  # was undocumented anywhere before
    "m_driver": ["trip"],  # already documented in driver/CLAUDE.md
    "m_prediction_ml": ["fleet"],  # scheduler_task.py
    "m_route_simulation": ["location"],  # openroute_client.py SELECT path
    # FAZ2 Wave 2 pilot (2026-07-28): m_trip was missing entirely from this
    # matrix, found live — creating a trip failed with
    # "permission denied for schema fleet" the moment role enforcement was
    # actually turned on for trip's routes (add_trip.py's own arac_repo/
    # sofor_repo FK-validation reads). fleet/driver/location/fuel confirmed
    # via direct `uow.<repo>` grep in trip/application/*.py
    # (add_trip.py -> arac_repo/sofor_repo, bulk_add_trips.py ->
    # lokasyon_repo/arac_repo/sofor_repo, reconcile_costs.py -> yakit_repo,
    # sla.py/trip_prediction_enrichment.py -> lokasyon_repo). NOTE: this
    # does NOT yet cover the SeferFuelEstimator path (prediction_ml /
    # route_simulation tables) — that only runs when
    # USE_SEFER_FUEL_ESTIMATOR=true (prod default) and needs its own,
    # separate verification pass before Wave 2 rolls out to production.
    "m_trip": ["fleet", "driver", "location", "fuel"],
}

# FAZ2 Wave 2 pilot (2026-07-28): found live, AFTER fixing the m_trip entry
# above — every protected endpoint's `get_current_user` dependency reads
# `auth_rbac.kullanicilar` (to resolve the JWT's user id) on whatever role
# is active for that request. This isn't module-specific at all: EVERY
# module role needs it, the exact same "universal, not per-module" pattern
# as the `outbox_events` WriteException below. Masked in initial pilot
# testing because the super-admin auth path has its own break-glass
# fallback (virtual id=0) that doesn't hard-fail on `permission denied` —
# only surfaced once testing hit a real, normal (non-super-admin) user via
# the RBAC/idempotency/API-contract test suites. `m_auth_rbac` already owns
# its own schema; `m_ops` already gets ALL via `_ops_role_stmts`.
for _role in ALL_ROLES:
    if _role in ("m_auth_rbac", OPS_ROLE):
        continue
    READER_SELECT_GRANTS.setdefault(_role, [])
    if "auth_rbac" not in READER_SELECT_GRANTS[_role]:
        READER_SELECT_GRANTS[_role].append("auth_rbac")


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
    WriteException(
        "m_analytics_executive", "fuel", "yakit_formul", ("INSERT", "DELETE")
    ),
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
        columns=(
            "api_mesafe_km",
            "api_sure_saat",
            "ascent_m",
            "descent_m",
            "last_api_call",
        ),
    ),
    # import_excel — toplu Excel import, repository'leri bilerek bypass eder
    # (driver/CLAUDE.md'de zaten kabul edilmiş bir istisna olarak dokümante).
    WriteException("m_import_excel", "fleet", "araclar", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "driver", "soforler", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "driver", "sofor_ad_soyad_trigram", ("INSERT",)),
    WriteException("m_import_excel", "trip", "seferler", ("INSERT", "DELETE")),
    WriteException("m_import_excel", "fuel", "yakit_alimlari", ("INSERT", "DELETE")),
    # FAZ2 Wave 2 pilot (2026-07-28): found live — trip's add_trip.py calls
    # shared_kernel's save_outbox_event() (INSERT INTO platform.outbox_events)
    # to publish SEFER_ADDED, and every one of the 14 module-schema roles
    # does the exact same thing — outbox_events is shared infrastructure
    # every business module writes its own domain events to (see
    # shared_kernel/CLAUDE.md's outbox.py entry). Granting this to only
    # m_trip would just move the same discovery to each of the other 14
    # modules' own pilot — granted to all of them up front instead.
    *[
        WriteException(role, "platform", "outbox_events", ("INSERT",))
        for role in MODULE_SCHEMA_ROLES.values()
        if role != "m_platform"  # m_platform already owns this table (ALL)
    ],
    # FAZ2 Wave 2 pilot (2026-07-28): found live, same "universal, not
    # per-module" story as outbox_events above — `admin_platform`'s
    # idempotency_service.py (reserve_or_get_cached/finalize_response,
    # SELECT+INSERT+UPDATE on platform.idempotency_keys) backs the
    # `Idempotency-Key` header support that trip_write_routes.py AND
    # fuel_routes.py both call into, so this needs to be pre-granted to
    # every module role rather than rediscovered per module.
    *[
        WriteException(
            role, "platform", "idempotency_keys", ("SELECT", "INSERT", "UPDATE")
        )
        for role in ALL_ROLES
        if role not in ("m_platform", OPS_ROLE)
    ],
    # FAZ2 Wave 2 pilot (2026-07-28): found live, fleet pilot — same
    # "universal, not per-module" story again. `admin_platform.
    # admin_audit_log` is written by `platform_infra.audit.audit_logger`'s
    # `@audit_log`/`log_audit_event` on EVERY module's write endpoints, not
    # just admin_platform's own. Without a schema-USAGE grant, a role
    # scoped to some other module can't even resolve the unqualified
    # `admin_audit_log` name via search_path — Postgres reports this as
    # "relation does not exist" (not "permission denied": a role with no
    # USAGE on a schema can't see it exists at all), which the audit
    # persist's own shared/test-session `begin_nested()` SAVEPOINT
    # guard only covers when the session's own `in_transaction()` check
    # takes that branch — the OTHER branch (no active transaction yet,
    # e.g. after an inline `uow.commit()` already ran earlier in the
    # SAME request, as in fleet's smart-delete flow) has no such guard and
    # genuinely poisons the shared session for the rest of the test.
    *[
        WriteException(role, "admin_platform", "admin_audit_log", ("INSERT",))
        for role in ALL_ROLES
        if role not in ("m_admin_platform", OPS_ROLE)
    ],
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
        f'"GRANT {role} TO <app_login_role>;" manually\', current_user;\n'
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


def _write_exception_stmts(exc: WriteException) -> list[str]:
    # A role with zero other access to `exc.schema` (e.g. m_trip writing to
    # `platform.outbox_events`, which isn't in its own READER_SELECT_GRANTS
    # entry) needs SCHEMA-level USAGE too — a table-level GRANT alone is a
    # no-op without it (Postgres can't even resolve the table without schema
    # USAGE). Idempotent/harmless to re-issue for roles that already have it
    # via READER_SELECT_GRANTS.
    stmts = [f"GRANT USAGE ON SCHEMA {exc.schema} TO {exc.role}"]
    privileges = ", ".join(exc.privileges)
    if exc.columns is not None:
        columns = ", ".join(exc.columns)
        stmts.append(
            f"GRANT {privileges} ({columns}) ON {exc.schema}.{exc.table} TO {exc.role}"
        )
    else:
        stmts.append(f"GRANT {privileges} ON {exc.schema}.{exc.table} TO {exc.role}")
    if "INSERT" in exc.privileges:
        # A serial/identity PK's underlying sequence needs its own USAGE
        # grant for `nextval()` — an INSERT-only table grant isn't enough
        # (found live: m_trip writing to platform.outbox_events, whose `id`
        # is `nextval('outbox_events_id_seq')`). Schema-wide, not per-table,
        # since WriteException doesn't track individual sequence names —
        # harmless (sequences are just ID generators, not data).
        stmts.append(
            f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {exc.schema} TO {exc.role}"
        )
        # `INSERT ... RETURNING <pk>` — which is exactly what SQLAlchemy's
        # ORM does on every flush() to read back an autoincrement PK — needs
        # SELECT on the returned column(s) too. Postgres genuinely enforces
        # this: RETURNING reads the row back, so INSERT privilege alone
        # isn't enough (found live, root cause of a real permission-denied
        # on platform.outbox_events even with current_user confirmed as
        # m_trip and the INSERT grant confirmed present — verified with a
        # raw asyncpg repro isolating RETURNING as the actual trigger).
        # Table-wide, not just the PK column: every one of this file's
        # existing (never-yet-enforced) WriteExceptions inserts into a
        # table with an autoincrement PK, so they'd hit the exact same
        # wall the moment their own module gets wired.
        stmts.append(f"GRANT SELECT ON {exc.schema}.{exc.table} TO {exc.role}")
    return stmts


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

    # 4) Narrow write exceptions (table/column-scoped)
    for exc in WRITE_EXCEPTIONS:
        stmts.extend(_write_exception_stmts(exc))

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
        stmts.append(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {role}"
        )
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
