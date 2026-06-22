# Foundation Inventory - 2026-03-20

This inventory captures the current pre-Phase-12 production-foundation state.
It is intentionally operational, not aspirational: completed slices, active
runtime surfaces, and remaining blockers are listed separately.

## Completed foundation slices

- `reports` route is resource-only Turkish through
  `frontend/src/resources/tr/reports.ts`.
- `fuel` page shell, stats, filters, header, modal, and shared import/export
  surfaces now read Turkish UI copy from resources:
  - `frontend/src/resources/tr/fuel.ts`
  - `frontend/src/resources/tr/shared.ts`
- `fuel` child components `FuelTable.tsx`, `FuelPagination.tsx`, and
  `ComparisonWidget.tsx` now read Turkish UI copy from
  `frontend/src/resources/tr/fuel.ts`.
- `locations` page shell and active child components now read Turkish UI copy
  from `frontend/src/resources/tr/locations.ts`:
  - `LocationList.tsx`
  - `AnalysisModal.tsx`
  - `RouteAnalysisCard.tsx`
  - `LocationFormModal.tsx`
- `fleet` page shell, insight cards, module shells, and active vehicle/driver/trailer
  child components now read Turkish UI copy from dedicated resources:
  - `frontend/src/resources/tr/fleet.ts`
  - `frontend/src/resources/tr/vehicles.ts`
  - `frontend/src/resources/tr/drivers.ts`
  - `frontend/src/resources/tr/trailers.ts`
- Admin overview, ML management, system health, and admin layout now read
  Turkish UI copy from `frontend/src/resources/tr/admin.ts`.
- Remaining active admin pages now also read Turkish UI copy from
  `frontend/src/resources/tr/admin.ts`:
  - `KonfigurasyonPage.tsx`
  - `KullanicilarPage.tsx`
  - `BakimPage.tsx`
  - `VeriYonetimPage.tsx`
  - `BildirimlerPage.tsx`
- Public/frontend trip contracts no longer expose `is_real`.
- Backend/public trip schemas and trip write flows no longer expose or pass
  `is_real`.
- Active truthfulness guards remain in place for time-series, route
  calibration, reports, and deleted legacy runtime adapters.
- Dormant runtime trip widgets were removed from the production tree:
  - `SmartRouteAnalysis.tsx`
  - `NewTripStepper.tsx`
- Dormant fleet runtime widgets were removed from the production tree:
  - `DriverCard.tsx`
  - `VehicleGridView.tsx`

## Active frontend route matrix

- `/trips`
  - status simplification already applied
  - page shell, module shell, header, filters, table, analytics, bulk action flow, timeline, form modal shell, telemetry card, trip list, and primary trip form child components are now resource-only through `frontend/src/resources/tr/trips.ts`
  - dormant auxiliary widgets `SmartRouteAnalysis.tsx` and `NewTripStepper.tsx` were deleted from the production tree
- `/fuel`
  - page shell and active child components are resource-only
- `/fleet`
  - page shell, insights, module shells, headers, filters, tables, detail dialogs,
    delete dialogs, and form dialogs are now resource-only
  - dormant alternative widgets `DriverCard.tsx` and `VehicleGridView.tsx`
    were removed from the production tree
  - still requires broader technical-English conversion and file/module rename wave
- `/locations`
  - page shell and active child components are resource-only
  - dormant runtime alternative modal `LocationAnalyzeModal.tsx` was removed from the app tree
- `/reports`
  - already resource-only in the earlier slice
- `/admin/*`
  - all active admin routes and `AdminLayout.tsx` are now resource-only
  - still requires broader technical-English conversion and file/module rename wave

## Backend runtime/public contract matrix

- Trip public contract
  - `app/schemas/sefer.py`: `is_real` removed from runtime/public schema
  - `app/core/entities/models.py`: `is_real` removed from public entity models
  - `app/core/services/sefer_write_service.py`: `is_real` no longer passed on
    create/return-trip flows
- Repository public surface
  - `app/database/repositories/sefer_repo.py`
    - public `get_all` and `count_all` no longer accept `is_real` filtering
    - public `add` no longer accepts `is_real`
    - public `update_sefer` no longer allows `is_real` updates
- Analytics/training persistence boundary
  - `is_real` has been removed from the touched runtime and persistence slice:
    - `app/database/models.py`
    - `app/database/repositories/analiz_repo.py`
    - `app/database/repositories/arac_repo.py`
    - training/reporting SQL inside `app/database/repositories/sefer_repo.py`
    - `app/tests/conftest.py`
    - `scripts/train_elite_ensemble.py`
  - clean rebuild is still required to enforce the new production database baseline end-to-end

## Test infrastructure status

- `app/tests/conftest.py`
  - PostgreSQL test resets now terminate stale sessions before rebuilding the schema
  - the reset path now recreates the `public` schema directly instead of relying on
    metadata-driven `drop_all`
- `app/tests/unit/test_services/test_sefer_service.py`
  - converted to a true unit suite with an in-memory repository stub
  - no longer depends on full database bootstrap

## Non-route execution surface status

- Startup/lifespan hooks: not fully audited in this slice
- Workers/background jobs: not fully audited in this slice
- WebSocket/SSE/pubsub/listener surfaces: not fully audited in this slice
- Import/export generators:
  - shared import/export UI is now resource-backed
  - remaining backend/import pipeline still needs English-only and truthfulness
    audit

## Packaging and repo hygiene status

- Deleted non-production generators remain covered by
  `app/tests/unit/test_production_foundation_guards.py`
- Build and lint stay green
- Clean rebuild, English schema, and production DB reset are still open

## Remaining blockers before Phase 12

- Full resource-only Turkish rollout for the remaining active route surfaces:
  - residual `/trips` and `/fleet` helper files outside the main routed surfaces
- Technical English-only conversion across touched frontend/backend/docs/scripts
- Clean rebuild implementation
- Full non-route execution-surface audit
