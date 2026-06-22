# Sentry Critical Fixes — Design Spec

**Date:** 2026-05-18
**Branch:** `fix/sentry-critical-fixes`
**Scope:** 7 production/test bugs identified via Sentry + deep test run

---

## Context

After merging `feat/frontend-zod-validation`, a full Sentry audit and deep test run revealed 7 bugs — all treated as critical per project policy. None of these are regressions from the Zod PR; they are pre-existing issues now surfaced.

---

## Fix 1: Excel Export — HTTPException(400) Swallowed as 500

**File:** `app/api/v1/endpoints/advanced_reports.py` → `export_analytical_report_excel`

**Problem:** The `except Exception` catch-all intercepts `HTTPException(400)` raised for invalid `report_type` and re-wraps it as HTTP 500. Only `DomainError` has a `re-raise` guard.

**Fix:** Add `except HTTPException: raise` immediately after `except DomainError: raise`, before the generic `except Exception` block.

**Test:** `test_excel_export_invalid_report_type_returns_error` — change assertion from `in (400, 500)` to `== 400`. Remove the "KNOWN BACKEND BUG" comment.

---

## Fix 2: FK Violation on kullanicilar → 500

**File:** `app/api/v1/endpoints/admin_users.py` → `create_user`

**Problem:** Inserting a user with a non-existent `rol_id` reaches the DB and raises `sqlalchemy.exc.IntegrityError` (FK constraint `kullanicilar_rol_id_fkey`). No handler → 500.

**Fix:** In `create_user` endpoint, wrap the service call with `except IntegrityError` → raise `HTTPException(400, "Geçersiz rol_id: belirtilen rol mevcut değil")`. Import `sqlalchemy.exc.IntegrityError`.

**Test:** `test_create_admin_user_invalid_rol_id` in `test_admin_users.py` — change expected status from `in (400, 500)` to `== 400`.

---

## Fix 3: RouteProcessingError Maps to Wrong HTTP Status

**File:** `app/main.py` — exception handler status map

**Problem:** `RouteProcessingError` is mapped to 422 (Unprocessable Entity). All real-world uses — "araç bulunamadı", "şoför bulunamadı", "duplicate sefer no" — are client input errors = 400 (Bad Request).

**Fix:** Change `RouteProcessingError: 422` → `RouteProcessingError: 400` in the `DOMAIN_ERROR_STATUS_MAP` dict in `main.py`.

**Test:** `test_create_sefer_invalid_arac` — change assertion from `== 400` comment (it already expects 400, was returning 422). Verify it now passes.

---

## Fix 4: Vehicle Create — IntegrityError → 500

**File:** `app/api/v1/endpoints/vehicles.py` → `create_arac`

**Problem:** `except Exception` catch-all handles all non-`ValueError` and non-`DomainError` exceptions as 500. SQLAlchemy `IntegrityError` (unique constraint, FK) falls through.

**Fix:** Add `except IntegrityError as e: raise HTTPException(400, ...)` after `except ValueError` in `create_arac`. Import `sqlalchemy.exc.IntegrityError`.

---

## Fix 5: Telegram Notifications Silent Failure

**File:** `app/infrastructure/notifications/telegram_notifier.py`

**Problem:** `notify_error` posts to `http://telegram-ops-bot:8080/webhook/error` (Docker hostname). In dev/non-Docker environments this never resolves. Failure is logged only at `DEBUG` level — invisible in production log levels.

**Fix:**
(a) Elevate failure logging from `logger.debug` to `logger.warning` with full URL in message.
(b) Add `TELEGRAM_OPS_BOT_URL` to `.env.example` with comment explaining Docker vs local values.

---

## Fix 6: ORS Routing 403 — No Specific Log

**File:** `app/services/route_service.py`

**Problem:** `route_service.py` has an explicit log for 401 ("ORS API key rejected") but not for 403 (quota exceeded / key suspended). 403 gets logged generically.

**Fix:** In the HTTP response status check, add an explicit branch for 403: `logger.error("ORS API key forbidden (403). Quota exceeded or key suspended. Check OPENROUTESERVICE_API_KEY in .env.")`. No behavior change — error still propagates.

---

## Fix 7: Test DB Connection Pool — asyncpg Closed Connection

**File:** `app/tests/conftest.py`

**Problem:** `InterfaceError: connection is closed` errors appear after test teardown. The asyncpg connection pool is not explicitly disposed between test sessions, causing subsequent test requests to reuse closed connections.

**Fix:** In `conftest.py`, add `await engine.dispose()` in the `async_engine` fixture teardown (after `yield`). Ensure the session fixture closes the session before the engine is disposed.

---

## Architecture Notes

- All fixes are in separate files with no cross-dependencies — can be implemented and committed independently.
- `main.py` RouteProcessingError status change is a one-line change with broad impact; verify no test expects 422 for RouteProcessingError before committing.
- The `IntegrityError` import (`from sqlalchemy.exc import IntegrityError`) is needed in 2 endpoints.

---

## Test Plan

After all fixes:

```bash
# Backend unit
pytest app/tests/ -x -q --tb=short

# Specific regression tests
pytest app/tests/integration/test_api_seferler.py::TestSeferAPI::test_create_sefer_invalid_arac -v
pytest app/tests/api/test_advanced_reports.py::test_excel_export_invalid_report_type_returns_error -v
pytest app/tests/api/test_admin_users.py -v

# Full suite
pytest app/tests/ -q --tb=no
```

Expected: 0 failures.
