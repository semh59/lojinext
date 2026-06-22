# Production Foundation Frozen Contracts

This document records the production-only foundation that must remain green before and during any Phase 12+ work.

## Frozen contracts from Phase 0-11

- Frontend build must stay green with `npm --prefix frontend run build`.
- Backend unit regressions must stay green with `pytest app/tests/unit -q`.
- Backend integration regressions must stay green with `pytest app/tests/integration -q`.
- Legacy backend regressions must stay green with `pytest tests -q`.
- Trip and prediction flows must keep their current contract semantics:
  - trip write paths keep unified prediction fields
  - time-series endpoints fail closed when prerequisites or models are unavailable
  - route cache and route persistence remain schema-aligned
- Dashboard, report, and import flows must use real service contracts instead of placeholders.
- Admin backend health, backup, and role flows must remain truthful and source-backed.
- Phase 11 hygiene contracts stay frozen:
  - canonical event type source
  - canonical audit logger source
  - no mojibake in touched backend Python files

## Permanent production-only rules

- No fabricated business outputs in runtime code.
- No silent fallback from API failure to plausible business data.
- No simulated or prototype operational panels on active routes.
- No runtime imports from deleted legacy adapters or quarantined fake modules.
- Clean rebuild is the only accepted path for the production database:
  - existing fake operational data is not migrated into the production rebuild
  - analytics, ROI, and reporting stay unavailable until real history exists
- Non-production generators, synthetic seeders, demo trainers, benchmarks, and load-test scripts must stay deleted from the repo runtime surface.
- UI Turkish must be resource-only:
  - active reports route and shared export dialog now read UI copy from `frontend/src/resources/tr/reports.ts`
  - active fuel route shell and child components now read UI copy from `frontend/src/resources/tr/fuel.ts`
  - active locations route shell and active child components now read UI copy from `frontend/src/resources/tr/locations.ts`
  - active trips route shell, core analytics/table/filter surface, bulk actions, timeline, form modal shell, telemetry card, trip list, and primary trip form child sections now read UI copy from `frontend/src/resources/tr/trips.ts`
  - dormant trips widgets `SmartRouteAnalysis.tsx` and `NewTripStepper.tsx` remain deleted from the production tree
  - active fleet route shell, insights, module wrappers, and active vehicle/driver/trailer child components now read UI copy from `frontend/src/resources/tr/fleet.ts`, `frontend/src/resources/tr/vehicles.ts`, `frontend/src/resources/tr/drivers.ts`, and `frontend/src/resources/tr/trailers.ts`
  - dormant fleet widgets `DriverCard.tsx` and `VehicleGridView.tsx` remain deleted from the production tree
  - active admin routes and layout now read UI copy from `frontend/src/resources/tr/admin.ts`
  - no new inline Turkish copy is allowed in touched technical components
- Frontend public trip contracts must not expose `is_real`.
- Backend public trip contracts must not expose `is_real`.
- Runtime, persistence, training scripts, and test bootstrap must not reference `is_real`.
- `app/tests` bootstrap must terminate stale PostgreSQL test-db sessions before reset.
- Pure unit suites must avoid full database reset when an in-memory repository stub is sufficient.
- UI text may remain Turkish.
- Technical surfaces must move toward English-only:
  - code identifiers
  - logs
  - comments
  - tests
  - scripts
  - docs
  - API error contracts

## Required Phase 12+ gates for every touched slice

Run all affected frozen-contract tests plus the cumulative gates below:

```powershell
pytest app/tests/unit -q
pytest app/tests/integration -q
pytest tests -q
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

## Targeted truthfulness guards added with this foundation

- `app/tests/unit/test_time_series_truthfulness.py`
- `app/tests/unit/test_production_foundation_guards.py`
- `app/tests/integration/test_prediction_time_series_api.py`
- `tests/test_route_calibration.py`
- `frontend/src/pages/__tests__/LocationsPage.test.tsx`
- `frontend/src/pages/admin/__tests__/OverviewPage.test.ts`
- `frontend/src/pages/admin/__tests__/AdminResourcePages.test.ts`
- `frontend/src/features/trips/__tests__/TripsModule.test.tsx`
- `frontend/src/features/trips/__tests__/TripsModuleResilience.test.tsx`
- `frontend/src/components/trips/__tests__/TripTable.test.tsx`
- `frontend/src/components/trips/__tests__/BrowserCompatibility.test.tsx`
- `frontend/src/components/trips/__tests__/TripSurface.test.tsx`
- `frontend/src/components/fuel/__tests__/FuelStats.test.tsx`
- `frontend/src/components/fuel/__tests__/FuelTable.test.tsx`
- `frontend/src/components/locations/__tests__/RouteAnalysisCard.test.tsx`
- `frontend/src/components/locations/__tests__/LocationFormModal.test.tsx`
- `frontend/src/components/vehicles/__tests__/VehicleDetailModal.test.tsx`

If any of these fail, Phase 12+ work is blocked until the regression is fixed.
