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
    "m_anomaly": [
        "trip",
        "driver",
        "fleet",
        "admin_platform",
        "location",
        "fuel",
        "notification",
    ],
    # notification: found live in the SAME pilot's manual HTTP test --
    # attribute_loss.override_attribution() publishes SEFER_UPDATED via
    # get_event_bus().publish_async(...) SYNCHRONOUSLY (in-process, not
    # via the outbox relay) -- notification's subscriber handler for that
    # event runs INLINE in the same async task/request, so it inherits
    # m_anomaly's SET LOCAL ROLE and needs to read
    # notification.bildirim_kurallari to decide whether to alert. A new
    # class of transitive dependency: in-process (non-outbox) event
    # publishing propagates the publisher's role into every synchronous
    # subscriber's queries, on top of the direct public.py-call and
    # buried-repository-method classes already found in this pilot.
    # trip/driver/fleet already correct in Wave 1 (get_anomaly_alarm_
    # context's unqualified anomalies/seferler/soforler/araclar JOIN +
    # get_fleet_insights.py's uow.sefer_repo/arac_repo). admin_platform
    # found live (FAZ2 Wave 2 anomaly pilot, 2026-07-29, comprehensive
    # public.py audit before wiring) — detect_anomaly.py's
    # detect_consumption_anomalies() calls admin_platform.public.
    # get_runtime_float("ANOMALY_Z_THRESHOLD", ...) (sistem_konfig table,
    # same schema-wide grant that already fixed entegrasyon_ayarlari for
    # m_location/m_route_simulation). location + fuel: found live in the
    # SAME pilot's manual HTTP test — `GET /anomalies/fleet/insights` ->
    # get_fleet_insights.py's uow.sefer_repo.get_cost_leakage_stats()
    # runs 3 raw SQL queries INSIDE TRIP'S OWN REPOSITORY that
    # unqualified-touch seferler (trip, already granted), location's
    # lokasyonlar (JOIN), and fuel's yakit_alimlari (separate query) —
    # invisible from a public.py import grep since they're buried inside
    # another module's repository method, not anomaly's own code — a new
    # class of transitive dependency beyond the direct public.py audit
    "m_ai_assistant": [
        "fleet",
        "trip",
        "driver",
        "location",
        "fuel",
        "anomaly",
        "admin_platform",
    ],
    # fuel + anomaly found live (FAZ2 Wave 2 ai_assistant pilot, 2026-07-30,
    # public.py + source-code audit before wiring): `AIService._build_
    # context` (orchestrate_ai_response.py) calls `uow.analiz_repo.
    # get_dashboard_stats()` -- reads fuel.yakit_alimlari (SUM(litre)) on
    # top of the already-granted trip/fleet/driver tables -- and `uow.
    # analiz_repo.get_recent_unread_alerts()` -- reads anomaly.anomalies
    # directly. `ai_routes.py`'s `_fuel_trend_chart` also calls fuel.
    # public.get_monthly_cost_trend() (fuel.yakit_alimlari, monthly
    # aggregate). admin_platform: `groq_client.py`/`raw_client.py` both
    # call admin_platform.public.get_integration_secret() (reads
    # admin_platform.entegrasyon_ayarlari for a DB-stored Groq API key
    # override) -- same sistem_konfig/entegrasyon_ayarlari-read pattern
    # already granted for m_location/m_route_simulation/m_anomaly/
    # m_prediction_ml. Unlike those, get_integration_secret never raises
    # (falls back to the env var on any DB error) so a missing grant here
    # would NOT crash /ai/chat -- but it would silently make the DB-based
    # key override permanently inert for this module, so the grant is
    # added anyway for consistency with every other module hitting this
    # exact table.
    "m_fleet": ["trip"],  # already documented in fleet/CLAUDE.md
    "m_fuel": ["fleet", "trip"],  # was undocumented anywhere before
    "m_driver": ["trip", "fleet", "anomaly"],  # trip already documented in
    # driver/CLAUDE.md; fleet+anomaly found live (FAZ2 Wave 2 driver pilot,
    # 2026-07-29) — anomaly_repository.py's get_anomalies() query (used by
    # DriverCoachingEngine via get_anomaly_detector().get_recent_anomalies)
    # joins unqualified anomalies/araclar/seferler/soforler in one raw SQL
    # statement
    "m_prediction_ml": [
        "fleet",
        "trip",
        "driver",
        "admin_platform",
        "location",
        "fuel",
        "anomaly",
    ],
    # fleet: scheduler_task.py. trip/driver/admin_platform found live
    # (FAZ2 Wave 2 prediction_ml pilot, 2026-07-29, public.py audit before
    # wiring) -- predictions.py's GET endpoints directly ORM-query
    # trip.public.SeferORM (Sefer) and db.get(driver.public.Sofor, ...);
    # ensemble_service.py's train_for_vehicle/predict_consumption use
    # trip.public.get_sefer_repo and driver.public.get_driver_stats;
    # prediction_service.py calls admin_platform.public.get_runtime_float
    # ("VEHICLE_AGE_DEGRADATION_RATE") -- same sistem_konfig-read pattern
    # already fixed for m_location/m_route_simulation/m_anomaly. location:
    # found live via real HTTP testing -- trip's own sefer_repo.
    # get_for_training() (a buried-repository-method case, same class as
    # the m_anomaly pilot's get_cost_leakage_stats finding) unqualified-
    # LEFT JOINs seferler with location's lokasyonlar (route difficulty
    # enrichment for training data). fuel + anomaly: admin_pilot.py's
    # GET /admin/pilot-status runs raw COUNT(*) queries against
    # yakit_alimlari (fuel) and anomalies (anomaly), unqualified, directly
    # in the route handler.
    "m_route_simulation": ["location", "fleet", "trip", "admin_platform"],
    # openroute_client.py SELECT path (location, original). Found live
    # (FAZ2 Wave 2 route_simulation pilot, 2026-07-29) via comprehensive
    # public.py cross-module audit (a lesson from the location pilot's
    # 3-round trip — audited up front this time instead of discovering
    # one CI failure at a time): fleet — create_route_simulation.py's
    # `POST /simulate` handler does `db.get(Arac, arac_id)` directly;
    # trip — weather_routes.py's `GET /weather/dashboard-summary` calls
    # `SeferService.get_all_paged(...)` (trip.public, request-scoped
    # factory) to list planned trips; admin_platform — openroute_client.py
    # AND mapbox_client.py both call `admin_platform.public.
    # get_integration_secret` for DB-configured API keys (same
    # entegrasyon_ayarlari table location's pilot found)
    "m_location": ["route_simulation", "admin_platform"],  # found live
    # (FAZ2 Wave 2 location pilot, 2026-07-29) — GET /locations/route-info
    # reads route_simulation.route_paths (bbox cache lookup) via
    # route_simulation.public.get_route_details(); the ContextVar-scoped
    # role from the location request context propagates into this nested
    # call's session because module_role is task-local (not session-local),
    # so m_location itself needs SELECT on route_simulation's tables.
    # admin_platform: openroute_geocode_client.py's _resolve_api_key()
    # reads admin_platform.entegrasyon_ayarlari (DB-configured ORS key,
    # takes priority over .env) via admin_platform.public.
    # get_integration_secret — without this grant the read silently fails
    # (caught + logged as a warning, falls through to .env) instead of
    # actually finding the configured key, a real prod functional
    # regression masked by the graceful fallback
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
    # FAZ2 Wave 2 admin_platform pilot (2026-07-29): found live via public.py
    # cross-module audit before wiring -- telegram_bridge.py (Telegram bot
    # bridge, api/internal_routes.py) calls driver.public.get_sofor_repo/
    # get_by_telegram_id (driver), driver.public.get_by_sofor_id (a driver
    # function that itself queries trip.seferler directly --
    # infrastructure/driver_trip_queries.py), driver.public.
    # SoforSeferPDFService (reads driver.soforler + trip.seferler for PDF
    # generation), driver.public.get_driver_coaching_engine (reads
    # anomaly.anomalies via get_anomaly_detector().get_recent_anomalies),
    # and _arac_plaka()'s uow.arac_repo.get_by_id (fleet). "platform" is for
    # application/error_events.py's admin-facing read surface over
    # error_events/error_hourly_stats (owned by platform_infra.monitoring,
    # moved to the "platform" schema in 0060_platform_schema_move) --
    # admin_audit_log itself is admin_platform's OWN table, no grant needed.
    "m_admin_platform": ["driver", "trip", "fleet", "anomaly", "platform"],
    # FAZ2 combined-coverage-gate CI failure (2026-07-30): m_import_excel
    # had zero blanket SELECT anywhere (only narrow WriteExceptions for its
    # bulk-write columns) -- but every importer validates/looks up existing
    # rows BEFORE writing. sefer_upload_importer.py/execute_import.py/
    # sefer_importer.py all call uow.arac_repo.get_all() (fleet.araclar +
    # fleet.arac_bakimlari + trip.seferler, joined in one raw query --
    # AracRepository.get_all() always delegates to get_all_with_stats_paged),
    # uow.sofor_repo.get_all() (driver.soforler), uow.dorse_repo.get_all()
    # (fleet.dorseler), uow.lokasyon_repo.get_all()/get_all_route_keys()
    # (location.lokasyonlar); yakit_importer.py's fuel.public.
    # recalculate_vehicle_periods() reads fuel.yakit_alimlari via
    # yakit_repo.get_all() before rewriting yakit_periyotlari. Caught by an
    # "Integration — remaining" test hitting sefer_upload_importer's
    # permission-denied on arac_bakimlari, which silently degraded (caught
    # exception, partial result) rather than raising -- no test failed, but
    # combined coverage dropped 92%->91% from the unreached success-path
    # branches.
    "m_import_excel": ["fleet", "driver", "trip", "location", "fuel"],
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
    # anomaly.attribute_loss.override_attribution() -- called from attribution_routes.py.
    # FAZ2 Wave 2 anomaly pilot (2026-07-29): added "updated_at" -- this was
    # a pre-existing Wave 1 gap (not a newly introduced regression). The
    # Sefer ORM model's updated_at column carries a Python-side
    # onupdate=get_utc_now, so SQLAlchemy auto-appends it to EVERY UPDATE --
    # the original column list missed this, surfacing as "permission denied
    # for table seferler" (confirmed via a real HTTP request). Also added
    # "tahmini_tuketim" -- override_attribution publishes SEFER_UPDATED
    # synchronously (in-process publish_async, not the outbox relay), and
    # prediction_ml's PhysicsRecalculationHandler subscribes to that event
    # and writes tahmini_tuketim back to the same row -- this handler runs
    # INLINE in the same async task, inheriting m_anomaly's SET LOCAL ROLE
    # the same way notification's subscriber does (see the m_anomaly
    # READER_SELECT_GRANTS comment above for the general pattern).
    WriteException(
        "m_anomaly",
        "trip",
        "seferler",
        ("UPDATE",),
        columns=(
            "arac_id",
            "sofor_id",
            "is_corrected",
            "correction_reason",
            "updated_at",
            "tahmini_tuketim",
        ),
    ),
    # prediction_ml's ensemble_service.py calls analytics_executive.public.
    # get_analiz_repo().save_model_params()/get_model_params() (found live,
    # FAZ2 Wave 2 prediction_ml pilot, 2026-07-29) -- analytics_executive
    # is schema-less (NO_SCHEMA_ROLES) but its AnalizRepository queries
    # OTHER modules' schemas directly; save_model_params does an upsert
    # (DELETE + INSERT) on fuel.yakit_formul, get_model_params SELECTs it.
    # Same table m_analytics_executive itself already has INSERT/DELETE on
    # (see the entry above) -- this is m_prediction_ml's own grant for the
    # same table, needed because SET LOCAL ROLE m_prediction_ml is active
    # when prediction_ml's own endpoints trigger this call chain.
    WriteException(
        "m_prediction_ml", "fuel", "yakit_formul", ("SELECT", "INSERT", "DELETE")
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
    # FAZ2 Wave 2 import_excel pilot (2026-07-29): found live via public.py
    # cross-module audit -- route_importer.py's import_routes() calls
    # location.public.create_location(uow.lokasyon_repo, ...), which INSERTs
    # a new lokasyonlar row or, on the "passive route re-added" path,
    # UPDATEs an existing one at arbitrary caller-supplied fields
    # (`**data.model_dump(exclude_unset=True)`) -- full-table UPDATE, not
    # column-scoped like the narrower WriteExceptions above.
    WriteException("m_import_excel", "location", "lokasyonlar", ("INSERT", "UPDATE")),
    # yakit_importer.py -> fuel.public.recalculate_vehicle_periods() ->
    # uow.yakit_repo.save_fuel_periods(periods, clear_existing=True) does a
    # DELETE + bulk INSERT into fuel.yakit_periyotlari (a table distinct
    # from yakit_alimlari, needs its own grant).
    WriteException("m_import_excel", "fuel", "yakit_periyotlari", ("INSERT", "DELETE")),
    # Same recalculate_vehicle_periods() call also does
    # uow.sefer_repo.update_trips_fuel_data(...) -- a bulk ORM UPDATE on
    # trip.seferler limited to 3 columns (distribution results), separate
    # from the existing INSERT/DELETE WriteException on the same table
    # above (which covers execute_import's raw-SQL bulk sefer import, not
    # this UPDATE path).
    WriteException(
        "m_import_excel",
        "trip",
        "seferler",
        ("UPDATE",),
        columns=("dagitilan_yakit", "tuketim", "periyot_id"),
    ),
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
    # FAZ2 Wave 2 pilot (2026-07-29): found live, location pilot — same
    # ContextVar-task-local mechanism as the READER_SELECT_GRANTS
    # "m_location": ["route_simulation"] entry above, one layer deeper.
    # `GET /locations/route-info` -> `route_simulation.public.
    # get_route_details()` doesn't just SELECT a cached route
    # (`route_simulation.route_paths`) — on a cache miss it computes a
    # fresh route and INSERTs the result back into that same table
    # (`BaseRepository.create` via route_simulation's own repository,
    # still running under m_location's SET LOCAL ROLE because the nested
    # session inherits the same task-local module_role ContextVar).
    # READER_SELECT_GRANTS alone covers cache HITS; this WriteException
    # covers cache MISSES.
    WriteException("m_location", "route_simulation", "route_paths", ("INSERT",)),
    # FAZ2 Wave 2 admin_platform pilot (2026-07-29): found live --
    # telegram_bridge.py::kaydet_belge() INSERTs a SeferBelge row (photo
    # upload + OCR-pending marker) into trip.sefer_belgeler.
    WriteException("m_admin_platform", "trip", "sefer_belgeler", ("INSERT",)),
    # telegram_bridge.py::report_driver_breakdown() -> fleet.public.
    # create_breakdown() INSERTs an AracBakim row into fleet.arac_bakimlari.
    WriteException("m_admin_platform", "fleet", "arac_bakimlari", ("INSERT",)),
    # application/error_events.py::resolve_error_event() UPDATEs
    # platform.error_events (READER_SELECT_GRANTS above only covers SELECT).
    WriteException(
        "m_admin_platform",
        "platform",
        "error_events",
        ("UPDATE",),
        columns=("resolved_at", "resolved_by"),
    ),
    # FAZ2 Wave 2 admin_platform pilot fix #2 (2026-07-29, caught live by a
    # real frontend CI test hitting the real backend): sistem_konfig/
    # konfig_gecmis are admin_platform's own primary feature (system
    # config CRUD, konfig_service.py) but -- like error_events above --
    # physically live in the "platform" schema. Migration
    # 0059_admin_platform_schema_move moves entegrasyon_ayarlari/
    # admin_audit_log into the admin_platform schema, but that same
    # migration's own docstring routes sistem_konfig/konfig_gecmis/
    # idempotency_keys to the platform schema instead -- a nuance this
    # pilot's initial audit missed by trusting the module's CLAUDE.md
    # table-ownership summary at face value instead of the migration.
    # AdminConfigRepository.update_value() runs SELECT ... FOR UPDATE on
    # sistem_konfig -- Postgres requires UPDATE privilege (not just
    # SELECT) to take a FOR UPDATE row lock, which is where this was
    # actually caught: PUT /admin/config/{key} 500'd with "permission
    # denied for table sistem_konfig" in CI's real-backend frontend test
    # (KonfigurasyonPage.test.tsx) -- the READER_SELECT_GRANTS "platform"
    # entry above only covers plain SELECT.
    WriteException(
        "m_admin_platform",
        "platform",
        "sistem_konfig",
        ("UPDATE",),
        columns=("deger", "guncelleyen_id", "son_guncelleme"),
    ),
    # Same update_value() call also INSERTs a KonfigGecmis audit-history row.
    WriteException("m_admin_platform", "platform", "konfig_gecmis", ("INSERT",)),
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
