# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LojiNext — AI-powered fuel tracking, route optimisation, and anomaly detection for Turkish TIR fleets. FastAPI backend + React/TypeScript frontend, backed by PostgreSQL, Redis, and a Celery worker pool.

---

## Commands

### Backend

```bash
# Install dependencies
pip install -r app/requirements.txt
pip install -r app/requirements-dev.txt   # includes pytest, ruff, mypy

# Run dev server (from repo root)
uvicorn app.main:app --reload

# Database migrations
alembic upgrade head          # apply all pending
alembic check                 # verify no drift (must pass in CI)
alembic revision --autogenerate -m "description"

# Run all tests (unit + integration)
pytest

# Run only unit tests with coverage gate
pytest -m "unit or not integration" --cov=app --cov-report=term-missing --cov-fail-under=70

# Run a single test file or function
pytest app/tests/integration/test_api_seferler.py -x -q
pytest app/tests/unit/test_ai_deep_remediation.py::test_specific_fn -s

# Celery worker
celery -A v2.modules.platform_infra.background.celery_app worker -l info

# Lint and type-check
ruff check app --select E,F,W,I
mypy app --ignore-missing-imports --no-strict-optional

# End-to-end pilot smoke (Excel pipeline doğrulaması: TRUNCATE → 5
# entity yükle → dashboard endpoint'lerini probe et). Status code yetmez,
# response body parse edilir; saved >= expected AND errors == [] olmalı.
PYTHONIOENCODING=utf-8 python scripts/e2e_pilot_smoke.py

# Sadece iş verisini TRUNCATE et (auth + alembic_version korunur)
docker compose exec backend python scripts/reset_business_data.py --confirm
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server (hot-reload)
npm run build      # Production build → dist/
npm run lint       # ESLint
npx vitest --run   # Run all unit tests

# Run a single test file
npx vitest --run src/components/trips/__tests__/TripTable.test.tsx

# Run tests matching a name pattern
npx vitest --run -t "BulkActionBar"
```

### Docker (full stack)

```bash
docker-compose up -d                  # Start all 15 services (backend, frontend, worker, celery-beat, db, redis, ocr-service, telegram-driver-bot, telegram-ops-bot, prometheus, grafana, alertmanager, 3x exporter)
docker-compose logs -f backend        # Stream backend logs
docker-compose down
docker-compose -f docker-compose.prod.yml up -d   # Production config

# Backend source code is baked into the image — there is no volume mount
# in docker-compose.yml. Live-applying a single edit without rebuild:
docker cp app/<path>/<file>.py lojinext-backend-1:/app/app/<path>/<file>.py
docker compose restart backend
# Tip: full rebuild (`docker compose up -d --build backend`) is slower but
# the only path when adding new modules / changing requirements.
```

### 0-mock epiği — dış-API stub (Kategori B)

`api_stub/` — küçük, gerçek bir FastAPI sunucusu; Mapbox/OpenRoute/
Open-Meteo/Telegram/Groq'un gerçek path yapısını birebir taklit eden
deterministik canned response'lar döner (in-process mock DEĞİL, gerçek
HTTP). Sadece `docker compose --profile test up -d api-stub` ile başlar
(`profiles: ["test"]`, default `up -d` bunu görmez, prod/dev davranışı
değişmez). `app/config.py`'deki `MAPBOX_API_BASE_URL`/
`OPENROUTE_API_BASE_URL`/`OPEN_METEO_API_BASE_URL`/
`TELEGRAM_API_BASE_URL`/`GROQ_API_BASE_URL` test/CI'da bu servise
işaret eder. Hata-enjeksiyonu: her endpoint `?simulate=timeout|error|
notfound` destekler (gerçek HTTP davranışı, mock değil).

Deployment is single-Docker-host `docker-compose` with replica scaling
(`docker compose up -d --scale backend=N`, fronted by Traefik) — not a
multi-node cluster. `app_data`/`model_data` named volumes are already shared
across every backend/worker replica on that host, so the FAISS index
(`app/data/ai_kb/`), ML `.pkl` models, and `storage/backups/` are already
consistent without object storage. Migrating them to S3/MinIO was
consciously deferred (2026-07-03) — it would only become necessary if the
deployment moves to multiple physical hosts (Swarm/K8s).

---

## Architecture

### Layer order

```
HTTP → api/v1/endpoints → core/services (or services/) → database/repositories → PostgreSQL
                            ↓
                    infrastructure/ (cache, events, audit, resilience)
                            ↓
                    core/ml / core/ai  (ML prediction, RAG, Groq LLM)
```

### Dependency injection

`v2/modules/platform_infra/container.py` is the singleton DI container (moved from `app/core/container.py` in dalga 17). All major services (SeferService, AracService, AIService, RAGEngine, etc.) are lazy-loaded, thread-safe properties. Endpoints receive services via FastAPI `Depends()` wired through `app/api/deps.py`. In tests, patch `container_mod.*` or pass explicit instances.

### v2 modular-monolith rebuild (in progress)

`v2/modules/<name>/` is the target architecture for a from-scratch, vertical-slice rebuild — `api/`, `application/`, `domain/`, `infrastructure/`, plus `public.py` (the module's only external surface), `events.py`, and a per-module `CLAUDE.md`. **Always `Read` a module's own `v2/modules/<name>/CLAUDE.md` before touching its code** — it documents that module's exact public API, cross-module dependencies (including temporary/undone ones), and gotchas; this root file only tracks which modules exist and their end-state intent. New code for a migrated domain goes in `v2/`, never back into the old `app/` location — once a module is migrated, its old `app/` files are deleted (not shimmed), and any remaining `app/` consumers are updated to import from `v2.modules.<name>...` directly.

| Module | Status | CLAUDE.md |
|---|---|---|
| `location` | Done (code) — CRUD, geocoding, route hydration | `v2/modules/location/CLAUDE.md` |
| `route_simulation` | Done (code) — ORS/Mapbox/Open-Meteo clients + segment simulator + `/routes` endpoints + `public.py`/`events.py` (added 2026-07-18); `weather_service.py`/`route_validator.py`/`route_calibration_service.py`/`admin_calibration.py` endpoint migrated to this module 2026-07-22 (only `openroute_service.py`'s live geocode surface stays in `app/core/services/` — it's `location`'s dependency, not this module's) | `v2/modules/route_simulation/CLAUDE.md` |
| `notification` | Done (code) | `v2/modules/notification/CLAUDE.md` |
| `fleet` | Done (code) | `v2/modules/fleet/CLAUDE.md` |
| `fuel` | Done (code) | `v2/modules/fuel/CLAUDE.md` |
| `driver` | Done (code) | `v2/modules/driver/CLAUDE.md` |
| `auth_rbac` | Done (code) | `v2/modules/auth_rbac/CLAUDE.md` |
| `anomaly` | Done (code) — fraud/investigation/attribution merged in (not a separate module) | `v2/modules/anomaly/CLAUDE.md` |
| `import_excel` | Done (code) | `v2/modules/import_excel/CLAUDE.md` |
| `reports` | Done (code) | `v2/modules/reports/CLAUDE.md` |
| `analytics_executive` | Done (code) — Feature-E strategic cockpit | `v2/modules/analytics_executive/CLAUDE.md` |
| `ai_assistant` | Done (code) — LLM chat, RAG, trip-planner wizard | `v2/modules/ai_assistant/CLAUDE.md` |
| `prediction_ml` | Done (code) — 5-model ensemble, physics fallback, Kalman, ARIMA, XAI; consumed by `trip` module's `SeferFuelEstimator` (Phase 4-5 sefer create path) via `adjustment_factors`/`vehicle_health_adjustment` | `v2/modules/prediction_ml/CLAUDE.md` |
| `trip` | Done (code) — sefer CRUD, round-trip automation, bulk ops, SLA/cost reconciliation, Phase 4-5 `SeferFuelEstimator` | `v2/modules/trip/CLAUDE.md` |
| `admin_platform` | Done (code) — sistem konfig, admin audit log, dış entegrasyon secret'ları, idempotency-key altyapısı, health check, error_events admin yüzeyi, Telegram bot köprüsü | `v2/modules/admin_platform/CLAUDE.md` |
| `shared_kernel` | Done (code) — not a business module; genuinely cross-cutting code left over once all 15 business modules were carved out (`UnitOfWork`, `BaseRepository`, ORM `Base`, domain exception hierarchy, security validators, generic response envelopes, `OutboxEvent`/`ErrorEvent`/`ErrorOccurrence`) | `v2/modules/shared_kernel/CLAUDE.md` |
| `platform_infra` | Done (code) — not a business module; genuinely cross-cutting RUNTIME SERVICES (cache/events/monitoring/resilience/middleware/database/DI-container/security/context/logging/audit/background/websocket) called (never inherited) by all 15 business modules; unlike `shared_kernel`, has its own enforced `public-surface-only-platform_infra` import-linter contract | `v2/modules/platform_infra/CLAUDE.md` |

There is no `<X>Service`-as-DI-singleton-only pattern inside migrated modules for CRUD-style use-cases — each use-case is a standalone function (see each module's `public.py`/`CLAUDE.md`). A handful of classes remain as documented exceptions (real mutable state or constructor-injected client dependencies for a single cohesive pipeline) — `RouteSimulator`, `LokasyonHydrator`, `DriverCoachingEngine`, `DriverPerformanceML`, `SoforSeferPDFService`, `PDFReportGenerator`, `LicenseEngine`, `TokenBlacklist`, `PermissionChecker`, `MaintenancePredictor`, `OpetFuelProvider`, `FAISSVectorStore`/`RAGEngine`/`RAGSyncService`/`GroqService`/`LLMClient`/`AIService`/`SmartAIService`+`KnowledgeBase`/`TripPlannerEngine`, `FuelTheftClassifier`, `AnomalyDetector`, `PredictionService`, `EnsemblePredictorService`, `EnsembleFuelPredictor`, `KalmanEstimatorService`, `Trainer`, `SeferService`, `SeferFuelEstimator`, `SeferRepository` — never a multi-use-case service object. Every module's own `CLAUDE.md` documents its exceptions with rationale.

### Route grade/segment analysis

`v2/modules/route_simulation/domain/route_analyzer.py` — module-level `RouteAnalyzer` singleton (`route_analyzer`), `analyze_segments()` classifies elevation-derived grade % into `GradeClass` buckets (downhill_steep/moderate, flat, uphill_moderate/steep) and groups consecutive same-class points into segments. Used by `v2/modules/route_simulation/infrastructure/openroute_client.py` and `application/get_route_details.py`'s route-simulation path.

### Unit of Work

`v2/modules/shared_kernel/infrastructure/unit_of_work.py` — async context manager that groups all repository operations into one transaction. All repositories are properties on the `UnitOfWork` object (`uow.sefer_repo`, `uow.arac_repo`, etc.). Services should accept an optional `uow: UnitOfWork` so callers can share transactions.

### Repository pattern

`v2/modules/shared_kernel/infrastructure/base_repository.py` provides generic CRUD (`BaseRepository`). Specialised repos live in each module's own `infrastructure/repository.py` and add domain queries. Repos operate on each module's own `infrastructure/models.py` (SQLAlchemy 2 async ORM, all deriving from `v2/modules/shared_kernel/infrastructure/base.py`'s `Base`). Pydantic schemas for requests/responses live in each module's own `schemas.py`.

### Service split

There are **two service layers** — do not confuse them:
- `app/core/services/` — domain logic, validation, UoW transaction management. No direct DB access; operates through repositories.
- `app/services/` — orchestration: external API integrations, ML pipeline orchestration, high-level endpoint APIs.

Decision rule for new services:
- DB + business rule → `app/core/services/`
- ML/AI orchestration or external API → `app/services/`

Some services use CQRS internally (e.g. `SeferService` delegates to `SeferReadService` + `SeferWriteService`).

### Pydantic entity models vs schemas

- `app/core/entities/models.py` — internal Pydantic domain entities (Arac, Sefer, Sofor, PredictionResult DTO, etc.)
- `app/schemas/` — request/response schemas used directly by endpoint handlers (AracCreate, SeferResponse, etc.)

These are **separate**. Endpoint handlers import from `app/schemas/`; service internals use `app/core/entities/models.py`.

### Event bus / outbox

`v2/modules/platform_infra/events/event_bus.py` (moved from `app/infrastructure/events/event_bus.py` in dalga 17) — in-process async event bus backed by Redis pub/sub. `@publishes(EventType.X)` decorator on service methods. Reliable delivery uses the transactional outbox pattern (`OutboxEvent` table) relayed by Celery beat task every 60 s (`relay-outbox-events-every-60s`).

### ML subsystem

`v2/modules/prediction_ml/domain/ensemble_core.py` (`EnsembleFuelPredictor`) — 5-model ensemble, orchestrated by `application/ensemble_service.py` (`EnsemblePredictorService`). Cold-start `DEFAULT_WEIGHTS`: physics=0.80, lightgbm/xgboost/gb/rf=0.05 each (physics is the only reliable source before training data accumulates). After training, `DynamicWeightStrategy` recomputes weights via R²-normalisation and saves them to `<model_id>_meta.json`; subsequent startups load those real weights. Physics fallback lives in `domain/physics_fuel_predictor.py`. Time-series forecasting in `domain/time_series_predictor.py` — `ARIMATimeSeriesPredictor` uses ARIMA(1,1,1) via statsmodels (min 10 observations) with a moving-average fallback for shorter series; never requires PyTorch. Kalman smoother in `domain/kalman_estimator.py`. Models stored as `.pkl` files under `app/models/` (git-ignored — note: NOT `app/core/ml/models/`, a stale path this doc previously claimed). All ML calls go through `asyncio.to_thread()` to stay async-safe. Model version registry write path: `application/ml_service.py::MLService.register_model_version()` writes to `model_versiyonlar` (wired into `ensemble_service.py`'s `_register_model_version()` as of 2026-07-18 — the old `app/core/ml/model_manager.py` it superseded targeted a `model_versions` table that never existed in the real schema and was deleted as dead code).

### AI / RAG

`v2/modules/ai_assistant/infrastructure/rag/rag_engine.py` — FAISS vector store with `sentence-transformers/all-MiniLM-L6-v2` (384-dim). LLM inference via Groq (`llama-3.1-70b-versatile`). `v2/modules/ai_assistant/application/knowledge_base.py`'s `SmartAIService` orchestrates RAG + LLM. Index persisted to `app/data/ai_kb/`. (`app/core/ai/rag_engine.py` and `app/services/smart_ai_service.py` are 1-line `FAZ4'te silinir` wildcard shims re-exporting the above — see `v2/modules/ai_assistant/CLAUDE.md`.)

### Frontend page structure

Pages live in `frontend/src/pages/`. Each page is thin — it composes feature modules and passes props. Heavy logic lives in `frontend/src/features/` (e.g. `TripsModule.tsx`, `trips/`). Shared UI primitives are in `frontend/src/components/ui/`.

Domain-scoped components are co-located: `src/components/trips/`, `src/components/vehicles/`, `src/components/fleet/`, etc. Each domain folder may have a `__tests__/` subfolder.

### Frontend state management

Zustand stores in `frontend/src/stores/`. Both stores use the `persist` middleware so state survives page reloads:
- `use-ai-store.ts` — AI chat panel state (messages, open/expanded, status)
- `use-trip-store.ts` — trip list + filter state (uses a custom `storageService` adapter instead of `localStorage` directly)

Global React context (non-persisted) lives in `frontend/src/context/`: `AuthContext.tsx` (current user + token) and `NotificationContext.tsx`.

### Frontend API layer

`frontend/src/services/api/` contains one file per domain (`trip-service.ts`, `fuel-service.ts`, `vehicle-service.ts`, etc.) plus the two shared HTTP utilities documented below. All domain service files import from `axiosInstance` — never call `fetchWithAuth` from them.

### Frontend strings (i18next is the dominant pattern; typed resource objects are legacy)

Most components manage user-visible strings via i18next: `useTranslation()` + `t()` against `frontend/src/locales/tr.json` / `en.json` (wired in `i18n.ts`). This is now the primary pattern — used in ~95 component/page files, not an exception.

The older typed-resource-object pattern (`frontend/src/resources/tr/<domain>.ts`, e.g. `vehicleTableText`, `tripModuleText`) still exists. Among **non-test** files, only the **reports / reports-studio** domain (`ReportsPage.tsx`, `ReportsStudioPage.tsx`, `TemplateConfigPanel.tsx`, `ReportCards.tsx`) still imports it directly (no `t()`). Its footprint in **tests** is wider than that: ~25 other test files across drivers/fuel/trailers/vehicles/admin/trips also import `resources/tr/*` directly for test-assertion text, unrelated to the reports domain — these are pre-existing and out of scope, not a sign of new domains adopting the pattern. Do not add new production domains to this pattern — extend `locales/*.json` + `useTranslation()` instead. `frontend/src/resources/en/<domain>.ts` (English counterpart, same 18 files) exists but is **dead code** — imported nowhere; do not add new keys there.

### Frontend design tokens

`tailwind.config.js` defines semantic tokens used throughout the codebase. Use these — do not hardcode pixel values or raw colours:

| Token | Value | Use |
|-------|-------|-----|
| `rounded-card` | 10px | Cards, dropdowns, inline badges |
| `rounded-modal` | 14px | Modals, page sections, empty states |
| `bg-surface` | CSS var | Component background |
| `bg-elevated` | CSS var | Slightly raised surface (headers, inputs) |
| `text-primary` / `text-secondary` / `text-tertiary` | CSS vars | Text hierarchy |
| `border-border` | CSS var | Standard border colour |

### Frontend data fetching

React Query (`@tanstack/react-query`) is used for all server state. `queryKey` conventions matter — use specific prefixes per domain and avoid prefix collisions (e.g. `['tripStats', 'global']` is distinct from `['tripStats', durum, ...]`). Domain hooks live in `frontend/src/hooks/` (e.g. `useTripsData.ts`).

Heavy list views use `@tanstack/react-virtual` for virtualised rendering (`TripTable.tsx`). Components that use `Link` from `react-router-dom` require a `MemoryRouter` in tests.

### Frontend auth / permissions

`RequirePermission` component (`src/components/auth/RequirePermission.tsx`) wraps UI that requires a specific permission string (e.g. `"sefer:onayla"`). In tests, mock it as a passthrough: `vi.mock('../../../components/auth/RequirePermission', () => ({ RequirePermission: ({ children }) => <>{children}</> }))`.

### Separate microservices

Two standalone services run alongside the main backend, each with its own `Dockerfile` and `requirements.txt`:
- `telegram_bot/` — Telegram bot interface (`driver_bot.py` for drivers, `ops_bot.py` for operations)
- `ocr_service/` — document OCR processor (`ocr_processor.py`)

These are included in `docker-compose.yml` but are not part of the FastAPI app module.

### Auth / RBAC

JWT (HS256 default, RS256 optional). `app/core/security.py` for token logic. `app/api/deps.py` exports `get_current_active_user`, `get_current_active_admin`, `require_permissions("resource:action")`.

Frontend: `axiosInstance` (axios-instance.ts) handles token refresh automatically via interceptor. `fetchWithAuth` (auth-service.ts) also retries with a refreshed token on 401 before redirecting to `/login` — use it only for `/auth/*` endpoints where the axios interceptor would cause circular dependency. For all other calls, prefer `axiosInstance`.

The system runs **single-tenant**: no `tenant_id` column on any table and no row-level multi-tenancy. `SecurityService.apply_isolation()` only refines filters by **role/permission** (e.g. blocking users without READ access) — it is not tenant isolation. Multi-tenant support would require a separate epic to introduce `tenant_id` columns and RLS policies.

### Celery

`v2/modules/platform_infra/background/celery_app.py` — broker Redis, results Redis. Beat schedule includes outbox relay. Most task modules live in each owning module's own `v2/modules/<name>/infrastructure/` (e.g. `dlq_tasks.py`, `theft_tasks.py`); the two genuinely platform-general ones (`backup_tasks.py`, `error_digest.py`) live alongside `celery_app.py` in `v2/modules/platform_infra/background/`. `CELERY_EAGER=True` in test env runs tasks inline (set in `app/config.py`).

### Domain exceptions

`v2/modules/shared_kernel/exceptions.py` — typed exception hierarchy rooted at `DomainError`. Subclasses: `FuelCalculationError`, `ImportValidationError` (carries `errors: list[str]`), `ExcelExportError`, `RouteProcessingError`, `MLPredictionError`, `AnomalyDetectionError`, `AuditLogError`. Services must raise these (never swallow silently) so the FastAPI exception handler can map them to the correct HTTP status.

### Error response envelope

All error responses follow `{"error": {"code": "...", "message": "...", "trace_id": "..."}}`. Raised via FastAPI exception handlers registered in `app/main.py`. Use `HTTPException` in endpoints; service layer raises domain-specific exceptions from `v2/modules/shared_kernel/exceptions.py` or `ValueError` (→ 400).

### Audit logging

`v2/modules/platform_infra/audit/audit_logger.py` exports two things:
- `@audit_log(action="X")` — decorator for service methods
- `await log_audit_event(action, module, entity_id, ...)` — imperative helper for use inside endpoint handlers

### Async job pattern (cost analysis, import)

Long-running endpoints submit work to `BackgroundJobManager` (`v2/modules/platform_infra/background/job_manager.py`) via `await job_manager.submit(coro_or_fn, *args)`. The handler returns 202 with `{status: "PROCESSING", task_id}`. Frontend polls `GET /trips/tasks/{task_id}/status` (returns `PROCESSING|SUCCESS|FAILED`). Used by:
- `GET /trips/{sefer_id}/cost-analysis` — submits `SeferService.reconcile_costs`.
- `POST /trips/upload?async_mode=true` — submits import job; default `async_mode=false` keeps the synchronous response for backward compatibility.

Frontend hook `useTaskStatus(taskId)` (in `frontend/src/hooks/useTaskStatus.ts`) handles polling and auto-stops on terminal status.

### Sefer yakıt tahmini (Phase 4-5 SeferFuelEstimator)

`v2/modules/trip/application/sefer_fuel_estimator.py` — sefer kaydında çalışan tahmin pipeline'ı (bkz. `v2/modules/trip/CLAUDE.md`). Aktivasyon `USE_SEFER_FUEL_ESTIMATOR` env (production `true`, default `false`). 7-adım:
1. arac/sofor yükle → 2. route koordinat çöz → 3. RouteSimulator (Mapbox Directions + segment_resampler + Open-Meteo elevation) → 4. Open-Meteo weather batch midpoints → 5. adjustment factors (temp, wind, precip, seasonal, driver, vehicle_age, maint) → 6. ML correction (Phase 5 cold-start `pw=1.0` → ensemble bypass) → 7. `route_simulations` + `route_segments` persist.

Sefer create yolu (`trip_prediction_enrichment.py::predict_outbound`) **2.5s timeout** uyguluyor; cold cache'de Mapbox+Open-Meteo bunu aşar → sefer **tahminisiz** kaydedilir (`tahmini_tuketim=NULL`). Bu silent fallback `GET /admin/fuel-accuracy` endpoint'inde `coverage_pct`'ye yansır.

`route_simulations` tablosu kolon adları: `total_km`, `total_l`, `total_eta_sec`, `avg_l_per_100km` (`distance_km` / `duration_min` DEĞİL).

Validation: `scripts/p51_real_world_validation.py` — estimator'ı **direkt** çağırır (sefer create timeout bypass), 5 referans Türkiye rotasında tahmini literatür bandlarıyla karşılaştırır. Tahmin doğrulama veya kalibrasyon değişikliği sonrası ilk koşulacak.

Per-segment `predict_granular` çağrıları (segment_simulator 500m bucket) lokal L/100km'de doğal sapma üretir; `silent_outlier_log=True` kwarg ile MAX_REALISTIC clamp log'unu sustur — route-level clamp'ler hâlâ görünür.

### Anomali eylem akışı (T7)

`anomalies` tablosunda `acknowledged_at/by` ve `resolved_at/by` + `resolution_notes` alanları var (migration `0012_anomaly_action`). Endpoint'ler:
- `POST /api/v1/anomalies/{id}/acknowledge` — operatör onaylar
- `POST /api/v1/anomalies/{id}/resolve` — body `{notes?: string}`, ack edilmemişse otomatik ack'ler
- `GET /api/v1/anomalies/?status=open|acknowledged|resolved` — durum filtresi

### XAI / Açıklanabilirlik

- `GET /drivers/{id}/score-breakdown` — hibrit skor formül kırılımı (`{manual, manual_weight, auto, auto_weight, total, trip_count, avg_consumption, target_reference, has_trips}`). Frontend: `DriverScoreBreakdown.tsx`.
- `GET /drivers/{id}/route-profile` — 4 güzergah tipi için ortalama gerçek/tahmini tüketim + sapma %. `best_route_type` >=5 sefer adaylardan en düşük deviation. Frontend: `DriverRouteProfile.tsx`.
- `POST /predictions/explain` — feature importance (top-10). Frontend: `XaiExplainPanel.tsx` (horizontal bar chart).

### Muayene + kalibrasyon

- `GET /vehicles/inspection-alerts?within_days=30` — `{expiring: [...], overdue: [...]}` (aktif + soft-delete edilmemiş).
- `POST /admin/calibration/calibrate/{sefer_id}` — güzergahın "Golden Path"ini verilen seferin GPS verisiyle kalibre eder (admin yetkisi: `kalibrasyon_duzenle`).

---

## Developer gotchas

Subtle traps that have bitten before — read before debugging similar symptoms.

### Repo `get_all` kwargs are NOT uniform

| Repo | Kwarg to include inactive rows |
|------|------|
| `AracRepository`, `SoforRepository` | `sadece_aktif=False` (custom override) |
| `DorseRepository` | `include_inactive=True` (inherits BaseRepository) |
| `LokasyonRepository` | `**kwargs` swallows either |
| `YakitAlimRepository` | `include_inactive=True` |

Passing the wrong kwarg fails with `TypeError: BaseRepository.get_all() got an unexpected keyword argument`.

### Singleton repos need UoW for raw-SQL methods

`get_arac_repo()`, `get_sefer_repo()` etc. return a session-less singleton. Any method that runs raw SQL (`execute_query`, `get_all_with_stats_paged`) crashes with `Database session not initialized in <Repo>`. Always wrap and use `uow.<repo>`:

```python
async with UnitOfWork() as uow:
    vehicles = await uow.arac_repo.get_all(sadece_aktif=False)
```

### Container exports

`from app.core.container import container` does **not** exist. Use `get_container()`. Same applies to `app.infrastructure.events.event_bus` → `get_event_bus()`. There are no module-level singletons named `container` or `event_bus`.

### `admin_audit_log` — Türkçe column names

The audit table is `admin_audit_log` (not `audit_log` / `audit_logs`). Columns: `istek_id` (~trace_id), `aksiyon_tipi` (action), `hedef_tablo` (entity), `hedef_id`, `kullanici_id`, `yeni_deger`, `basarili` (success boolean), `sure_ms` (duration ms), `zaman` (created_at). Project with SQL aliases for frontend.

Audit logger (`v2/modules/platform_infra/audit/audit_logger.py`) **çift yazım** yapar: (1) her zaman JSON dosya log, (2) `_persist_audit_to_db` ile best-effort async `INSERT INTO admin_audit_log`. Async `@audit_log` decorator (success + failure yolları) ve `log_audit_event` her ikisi de tabloya yazar; **sync** wrapper yalnız dosyaya yazar (event loop garanti değil). DB persist asla ana iş akışını bloklamaz (exception yutulur → warning; shared/test session'da `begin_nested()` SAVEPOINT izolasyonu). `istek_id` ← `correlation_id`. Süper admin synthetic id≤0 → `kullanici_id=NULL` (FK violation'dan kaçınır); `kullanicilar`'da olmayan pozitif id'ler best-effort'ta sessizce düşer.

### Sefer `net_kg` check constraint

`seferler.ck_seferler_check_sefer_net_kg_calc`: `net_kg = dolu_agirlik_kg - bos_agirlik_kg`. Excel sefer import only carries `net_kg`; `bulk_add_sefer` must pre-fetch `arac.bos_agirlik_kg` and compute `dolu = bos + net`, else `CheckViolationError` on insert.

### `SafeColumnMapper.map_columns` two-pass strategy

(`app/core/services/excel_column_map.py`)
1. **Exact-match pass** — Excel column locks to its internal_key first.
2. **Fuzzy pass** — only claims columns not yet locked, score uses `min/max` ratio (caps at ≤1).

This precedence is load-bearing: without it, "Plaka" → `dorse_plakasi` drift was happening (substring trick). Adding a new alias that is a substring of another is safe under this scheme.

### Sentry: EU region + numeric ID

Project lives in EU (`de.sentry.io`). API base is `https://de.sentry.io/api/0/`, not `https://sentry.io/api/0/` — the latter returns 404 for issue operations. Resolve action wants the numeric `id`, not the `shortId` (e.g. `LOJINEXT-16R`).

### `_sentry_before_send` already drops these — don't re-capture

(`app/main.py:71`, `_sentry_before_send`) Filters out: monitoring self-test events, `CancelledError`-message events, JWT-anomaly `capture_message`s from `alarm_router`, all `HTTPException`/`StarletteHTTPException` 4xx, `PyJWT`'s `ExpiredSignatureError`/`PyJWTError` (not `jose` — the codebase uses `PyJWT`, `from jwt import ...`), `HTTPException` with "devre dışı/disabled" detail, `asyncio.CancelledError`, and asyncpg's `UntranslatableCharacterError` (test-DB-only). Adding `capture_exception()` for any of these is wasted noise. In practice only two call sites ever reach Sentry: `db_operational_error_handler` (`SAOperationalError`) and the catch-all `unhandled_exception_handler` — everything else is suppressed before send.

### Pre-commit reformats — restage after first commit attempt

`.pre-commit-config.yaml` has ruff + ruff-format + detect-secrets active. If a hook auto-fixes formatting, the commit fails first, the file is rewritten unstaged. Just `git add <file>` again and rerun the same commit command — do not pass `--no-verify`.

### Open-Meteo free tier — minutely rate limit dar

Free tier nominal 600 req/min ama **saturated minute**'da 429 hızla biter. Tek sefer simülasyonu 5-10 elevation chunk + 2-N weather midpoint atıyor → tek istemcide dahi sınıra çarpar.

Pattern (P5.1 sonrası): 429 → `Retry-After` header (varsa) veya 1.5s + tek retry. 5xx/network hataları `with_async_retry` decorator'ında zaten 3 deneme exponential backoff. Yeni Open-Meteo endpoint çağrısı eklerken aynı pattern'i koru — yoksa `v2/modules/route_simulation/infrastructure/open_meteo_client.py:_request_once`'taki gibi 4xx sessizce None'a düşer ve physics underestimate eder (ANK-KON elevation_coverage=0% bulundu, P5.1).

### Container'da script çalıştırma

`scripts/` klasörü image'a dahildir (2026-06-12'den beri; `.dockerignore`'dan çıkarıldı — `Dockerfile` zaten `COPY . .` yapıyor). Çalıştırma:

```bash
docker compose exec backend python -m scripts.<file>
```

Yeni yazılmış/henüz build edilmemiş tek bir script'i rebuild'siz denemek için `docker cp` pattern'i hâlâ geçerli (bkz. Docker bölümü).

---

## Configuration

All settings in `app/config.py` (`pydantic_settings.BaseSettings`). Reference via `from app.config import settings`. Key groups:

| Group | Fields |
|-------|--------|
| Core | `PROJECT_NAME`, `API_V1_STR`, `ENVIRONMENT` |
| Auth | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Database | `DATABASE_URL` (asyncpg) |
| Cache/Queue | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_EAGER` |
| AI/LLM | `GROQ_API_KEY`, `GROQ_MODEL_NAME`, `AI_TEMPERATURE` |
| ML | `VEHICLE_AGE_DEGRADATION_RATE`, `ANOMALY_Z_THRESHOLD` |
| Observability | `SENTRY_DSN`, `OTEL_ENABLED`, `LOG_LEVEL` |
| CORS | `CORS_ORIGINS` (raw string; use `settings.cors_origins` for the parsed list) |

`settings.cors_origins` (lowercase, computed property) returns `List[str]`. Never iterate over `settings.CORS_ORIGINS` directly — it is a raw string.

---

## CI hard gates

`.github/workflows/ci.yml` blocks merges if any of these fail:

1. `app/requirements.txt` must re-export `app/requirements.txt` (dependency contract)
2. Forbidden model strings (`qwen`, `gpt4all`) must not appear in source
3. `alembic check` — no schema drift
4. `pip-audit` / `npm audit --omit dev` — no known CVEs
5. `ruff check` — no lint errors
6. `mypy` — no type errors
7. `pytest` unit + integration with 70 % coverage minimum
8. `vitest --run` + `vite build`
9. `lint-imports` (import-linter) — the 17 v2/-modules contracts (1
   independence + 1 layers + 15 `public-surface-only-<module>`, one per
   migrated business module) must pass; blocking since 2026-07-21. The
   pre-existing legacy `report-only` contract (`app.core.services` vs
   `app.services` circular drift, unrelated to the v2/ modular-monolith
   refactor) stays non-blocking on purpose — see
   `TASKS/faz1-import-linter-baseline-ve-gate.md`. `shared_kernel` landed
   (dalga 16) but deliberately has no `public-surface-only-shared_kernel`
   contract — the whole point of that module is that everyone imports it
   freely (see `v2/modules/shared_kernel/CLAUDE.md`), so the "15" count
   above stays business-modules-only. `platform_infra` (not started) will
   get its own contract added when it lands.

---

## Database migrations

Alembic config: `alembic.ini` + `alembic/env.py`. Migration files go in `alembic/versions/` (tracked in git). Do **not** use `Base.metadata.create_all` in production — always use `alembic upgrade head`. The CI pipeline checks that exactly 1 head exists and the running DB matches it.

---

## Testing notes

### Backend
- Test DB URL: `TEST_DATABASE_URL` env var **zorunlu** (örn. `postgresql+asyncpg://postgres:postgres@localhost:5432/lojinext_test`); yoksa integration testler RuntimeError ile durur. DB adı 'test' içermek zorunda — conftest, bağlandığı DB'de `DROP SCHEMA public CASCADE` çalıştırdığı için dev/prod adlı hedefler reddedilir.
- `app/tests/conftest.py` drops and recreates the public schema before each session, then runs `Base.metadata.create_all`. It gracefully handles missing PostGIS by falling back to `LargeBinary` for geometry columns.
- `asyncio_mode = auto` — all async test functions work without `@pytest.mark.asyncio`.
- Use `@pytest.mark.integration` on DB-touching tests so CI can separate fast unit runs from slow integration runs.

### Frontend
- Test wrapper is `frontend/src/test/test-utils.tsx` — re-exports everything from `@testing-library/react` and replaces `render`/`renderHook` with versions pre-wrapped in `QueryClientProvider + AuthProvider + MemoryRouter`. Always import from `'../../../test/test-utils'`, not directly from `@testing-library/react`, unless the component has no routing or query dependencies.
- Each `render()` call gets a fresh `QueryClient` (retry: false), so React Query cache never bleeds between tests.
- Mock ESM modules with `vi.mock(...)` at the top level; use `await import(...)` inside tests to get the typed mocked reference — never use `require()`, which breaks ESM.
- Turkish uppercase characters (`İ`, `Ş`, `Ü`, `Ğ`) do not case-fold correctly with the regex `/i` flag (no `u` flag). Match them with exact strings (`'MUAYENESİ GEÇMİŞ'`) or uppercase-explicit regexes (`/GÜN KALDI/`). When `getByText` may match multiple elements (e.g. a value that also appears in a section label), use `getAllByText(...)[0]` instead of `getByText`.
