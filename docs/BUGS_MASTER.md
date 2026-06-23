# LojiNext — Master Bug Tracker

**Last updated:** 2026-06-23
**Sources:** BUG_REPORT.md (2026-06-08), v7_Hata_Raporu (2026-05-19), contract-mismatch audit (2026-06-22/23)

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ FIXED | Verified in current code; commit noted where known |
| ⚠️ OPEN | Still present, needs fix |
| 📋 BACKLOG | Known, accepted/deferred; low-risk or out-of-scope |
| 🔍 VERIFY | Status uncertain |

---

## 1. Critical / Production Blockers

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| BUG-001 | `datetime.now()` crash in `request_password_reset` — `import datetime` (module) instead of `from datetime import datetime` | `auth_service.py:231` | ✅ FIXED | Uses `from datetime import datetime, timedelta, timezone` |
| BUG-002 | Systemic Turkish status strings in SQL — 12 locations using `'Planlandı'`/`'Tamamlandı'`/`'İptal'`/`'Yolda'` instead of `'Planned'`/`'Completed'`/`'Cancelled'` | Multiple | ✅ FIXED | All files use English canonical values; `sefer_repo._VALID_DURUM` uses `CANONICAL_SEFER_STATUS_SET`; `sefer_read_service` limit aligned (API-003) |
| BUG-003 | `analiz_repo.get_recent_unread_alerts` queried table `anomalier` (does not exist) → always returned `[]` | `analiz_repo.py:392` | ✅ FIXED | Now queries `anomalies` |
| API-001 | Admin bulk sefer import always crashed — raw SQL INSERT used `'Planlandı'` against CHECK constraint | `import_service.py:323` | ✅ FIXED | Part of BUG-002 fix |

---

## 2. Security

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| SEC-001 | IDOR — `notification_service.mark_as_read` accepted `user_id` kwarg but never used it for ownership check | `notification_service.py:135` | ✅ FIXED | `mark_as_read(notification_id, user_id)` now delegates to `notification_repo.mark_as_read_for_user` which scopes UPDATE to owner |
| SEC-002 | `INTERNAL_API_SECRET` not validated in prod startup — empty string allowed | `config.py` | ✅ FIXED | `_validate()` raises `ValueError` when `ENVIRONMENT=prod` and secret empty (line 325) |
| SEC-003 | WebSocket JWT auth used HS256 key even when `ALGORITHM=RS256` → all WS connections failed silently | `admin_ws.py:67` | ✅ FIXED | Uses `get_decode_key()` from `jwt_handler` which selects correct key per algorithm |
| SEC-004 | Token blacklist fail-open — Redis down → logout'd tokens remain valid for `ACCESS_TOKEN_EXPIRE_MINUTES` | `token_blacklist.py:43` | 📋 BACKLOG | Documented trade-off; partial protection via `revoke_session`; fail-secure requires Redis HA |
| SEC-005 | `ADMIN_PASSWORD` optional in config — migration runs before startup validator → `AttributeError` if not set | `config.py:47`, `0002_seed_and_bootstrap.py:42` | 📋 BACKLOG | Prod validator exists; migration risk only in fresh env without env var |
| SEC-006 | JWT access token stored in `localStorage` — XSS risk | `storage-service.ts:18` | 📋 BACKLOG | Refresh token in HttpOnly cookie is correct; access token migration to memory/sessionStorage is planned |
| SEC-007 | Two `bcrypt` implementations — `jwt_handler.get_password_hash` lacked 72-byte guard | `jwt_handler.py:15`, `security.py:31` | ✅ FIXED | `jwt_handler.get_password_hash` delegates to `core/security.py` canonical implementation |
| SEC-008 | Missing `ondelete` policy on several FK columns — user delete triggers `ForeignKeyViolation` | `models.py` multiple | 📋 BACKLOG | Affects `olusturan_id`, `EgitimKuyrugu.egiten_kullanici_id`, `SistemKonfig.guncelleyen_id` |

---

## 3. Data Integrity

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| DATA-001 | Double booking — `arac_repo.get_available_vehicles()` and `sofor_repo.get_available_drivers()` used Turkish status strings in availability query | `arac_repo.py:385`, `sofor_repo.py:360` | ✅ FIXED | Part of BUG-002 fix; queries use `'Planned'` |
| DATA-002 | `sefer_fuel_estimator` `arac_yasi` hard-coded to `5` for all vehicles | `sefer_fuel_estimator.py` | ✅ FIXED | `_derive_arac_yasi(arac)` method derives age from `arac.yil` |
| DATA-003 | `get_trip_stats()` durum filter broken both ways (Turkish input rejected, English input matched wrong column) | `sefer_repo.py:416` | ✅ FIXED | `_VALID_DURUM = set(CANONICAL_SEFER_STATUS_SET)` + `normalize_sefer_status()` |
| DATA-004 | `YakitFormul.updated_at` used `DateTime` without `timezone=True` | `models.py:711` | ✅ FIXED | Now `DateTime(timezone=True)` |
| DATA-005 | `sefer_repo.get_cost_leakage_stats()` used `'Tamamlandı'` in SQL → always returned 0 | `sefer_repo.py:215,225` | ✅ FIXED | Now `durum = 'Completed'` |

---

## 4. Contract Mismatches (service seam dict key bugs)

| ID | Description | Files | Status | Commit |
|----|-------------|-------|--------|--------|
| CONTRACT-1 | `anomaly_detector` read `prediction["prediction_l_100km"]` (key doesn't exist in `prediction_service` response) → anomaly detection always returned None | `anomaly_detector.py:197,558` | ✅ FIXED | `945e2c4` |
| CONTRACT-2 | `sofor_analiz_service` read `pred.get("prediction_l_100km")` → always 0 → elite score always None | `sofor_analiz_service.py:352,413` | ✅ FIXED | `945e2c4` |
| CONTRACT-3 | `ensemble_service` never emitted `confidence_score` key; `prediction_service` always used static fallback | `ensemble_service.py` | ✅ FIXED | `945e2c4` |
| CONTRACT-4 | `vehicle_health_factor.apply_maintenance_factor` only updated deprecated `prediction_liters` alias, not `tahmini_tuketim` or `tahmini_litre` → maintenance factor silently discarded before DB write | `vehicle_health_factor.py:198` | ✅ FIXED | `a760149` |
| CONTRACT-5 | `trip_planner` read `pred.get("prediction_liters")` (deprecated alias) for vehicle fuel ranking | `trip_planner.py:348,356,369` | ✅ FIXED | `a760149` |
| CONTRACT-6 | `anomaly_detector` read `prediction["method"]` (key doesn't exist) → KeyError in anomaly description | `anomaly_detector.py:211` | ✅ FIXED | `945e2c4` (reads `model_used`) |

---

## 5. API / Service Layer

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| API-002 | `request_password_reset` → `AttributeError` crash (same as BUG-001) | `auth_service.py:204` | ✅ FIXED | See BUG-001 |
| API-003 | Limit mismatch: `sefer_read_service` accepted up to 5005, repo capped at 1000 | `sefer_read_service.py:70` | ✅ FIXED | Service now uses `SeferRepository.MAX_LIMIT` |
| API-004 | `notification_service.mark_as_read` signature arity mismatch | `notification_service.py:135` | ✅ FIXED | See SEC-001 |
| API-005 | Coaching anomaly scope filtered all anomalies, not per-driver | `driver_coaching_engine.py:90` | ✅ FIXED | `sofor_id=sofor_id` filter added |

---

## 6. Model / Schema

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| MODEL-001 | `TripStatus` enum has `ASSIGNED`/`IN_PROGRESS` values not in DB CHECK constraint | `schemas/sefer.py:21` | ✅ FIXED | `ALLOWED_TRANSITIONS` in `sefer_write_service` cleaned to only Planned/Completed/Cancelled |
| MODEL-002 | Several domain models missing `updated_at` (`Arac`, `Sofor`, `Lokasyon`, etc.) | `models.py` | 📋 BACKLOG | Requires migrations; tracked separately |
| MODEL-003 | `SeferBelge` used `olusturulma` column name instead of `created_at` | `models.py:1330` | ✅ FIXED | Now uses `created_at` with `DateTime(timezone=True)` |
| MODEL-004 | `Lokasyon` model missing `created_at` and `updated_at` | `models.py:274` | 📋 BACKLOG | Requires migration |
| MODEL-005 | `DurumEnum` and `SeferDurumEnum` coexist with overlapping `.TAMAMLANDI = "Completed"` | `core/entities/models.py:24` | 📋 BACKLOG | Domain confusion; low crash risk |

---

## 7. Architecture / Design

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| ARCH-001 | Superadmin `id=0` (virtual user) → all audit entries have `kullanici_id=NULL` → superadmin unauditable | `deps.py:154` | 📋 BACKLOG | Known design debt; KVKK concern; requires seed migration rework |
| ARCH-002 | Two sefer import paths (`import_service.py` vs `sefer_import_service.py`) with different behavior | Both files | 📋 BACKLOG | `import_service` (admin) fixed for status; core divergence remains |
| ARCH-003 | `ALLOWED_TRANSITIONS` dead code for `ASSIGNED`/`IN_PROGRESS` states that DB never allows | `sefer_write_service.py:52` | ✅ FIXED | Transitions map now contains only Planned/Completed/Cancelled |
| ARCH-004 | mypy baseline 195 errors | `ci.yml:231` | 📋 BACKLOG | Ongoing ARCH-004 dilim epici; 6 dilim planned, partially done |
| ARCH-005 | Sync + async DB engine running in parallel — pool sizes not coordinated with PG max_connections | `connection.py:89` | 📋 BACKLOG | Sync engine deprecated; remove in next cleanup |

---

## 8. Celery / Background Tasks

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| HATA-1 | Coaching weekly digest hit global 90s Celery timeout for large fleets | `coaching_tasks.py` | ✅ FIXED | `soft_time_limit=3600` on task |
| HATA-4 | Singleton race condition in `get_driver_coaching_engine()` and `get_fuel_theft_classifier()` | `driver_coaching_engine.py`, `fuel_theft_classifier.py` | ✅ FIXED | `threading.Lock()` double-check pattern |

---

## 9. Minor / Style

| ID | Description | File | Status | Notes |
|----|-------------|------|--------|-------|
| HATA-2 | ICS calendar events had `DTSTART = DTEND` (zero-duration) — invisible in most calendar apps | `ics_generator.py` | ✅ FIXED | `DTEND = DTSTART + timedelta(days=1)` |
| HATA-3 | Redis connection leak — `_get_redis()` created new `ConnectionPool` on every HTTP request | `executive.py` | ✅ FIXED | Module-level `_exec_redis` singleton |
| HATA-5 | Coaching engine used ALL open anomalies system-wide instead of per-driver scope | `driver_coaching_engine.py:91` | ✅ FIXED | `sofor_id=sofor_id` filter |
| HATA-6 | PII (ad_soyad, plaka) logged in `theft_tasks.py` — KVKK violation | `theft_tasks.py:81` | ✅ FIXED | Logs only `sofor_id` and `arac_id` |
| MINOR-004 | `timedelta` not imported in `auth_service.py` | `auth_service.py` | ✅ FIXED | `from datetime import datetime, timedelta, timezone` |
| MINOR-007 | Inconsistent `import datetime` style project-wide | Multiple | 📋 BACKLOG | `from datetime import ...` is the standard; module-level import caused BUG-001 |
| MINOR-009 | `python-jose` CVE suppressed in CI | `.github/workflows/ci.yml` | 📋 BACKLOG | Migration to `PyJWT + cryptography` planned |
| MINOR-010 | `_SSE_SEMAPHORE.locked()` race window before `acquire()` in SSE endpoint | `error_stream.py:42` | 📋 BACKLOG | Analyzed: no await between `locked()` and `acquire()` → no real TOCTOU in asyncio single-thread; documented in source comment |

---

## 10. Test Coverage Gaps

| ID | Description | Status | Notes |
|----|-------------|--------|-------|
| TEST-001 | Enum mismatch not tested (BUG-002 regression) | ✅ FIXED | `test_sefer_repo_durum_filter.py` + new `test_sefer_status_filter_integration.py` |
| TEST-003 | IDOR notification test written, fix not applied | ✅ FIXED | SEC-001 fixed; `test_notification_ownership_integration.py` added |
| TEST-004 | `sefer_repo.get_trip_stats()` durum filter test written, fix not applied | ✅ FIXED | `test_sefer_repo_durum_filter.py` covers this |
| TEST-005 | Coverage threshold mismatch: `pytest.ini` says 83, CI uses 92 | 📋 BACKLOG | CI wins; `pytest.ini` should be updated to match |
| TEST-006 | Executive endpoint — 8 endpoints, 2 tested | 📋 BACKLOG | FVI, carbon, compliance, what-if untested |
| TEST-007 | WebSocket RS256 scenario not tested | 📋 BACKLOG | Low priority since RS256 is not default |
| TEST-008 | `sefer_fuel_estimator.arac_yasi` hard-coded test written, fix not applied | ✅ FIXED | DATA-002 fixed |
| CONTRACT-TESTS | Real-object integration tests for prediction/anomaly/sofor_analiz seams | ✅ FIXED | `test_prediction_contract_integration.py` (4 tests) |
| CONTRACT-TESTS-2 | Real-object tests for maintenance factor, notification IDOR, cashflow, status filter | ✅ FIXED | Added 2026-06-23 (see below) |

---

## New Integration Tests Added (2026-06-23)

| File | Seam Tested | Bug Regression |
|------|-------------|----------------|
| `test_maintenance_factor_integration.py` | `apply_maintenance_factor` → all 3 payload keys | CONTRACT-4 |
| `test_notification_ownership_integration.py` | `NotificationService.mark_as_read` ownership guard | SEC-001 |
| `test_cashflow_projector_integration.py` | `project_cashflow` counts `'Planned'` trips only | BUG-002 |
| `test_sefer_status_filter_integration.py` | `get_trip_stats()` + `get_cost_leakage_stats()` English status | BUG-002 |
| `test_prediction_contract_integration.py` | `ensemble→prediction→anomaly→sofor_analiz` chain | CONTRACT-1/2/3/6 |

---

## Open Items Summary

Items still requiring action:

| Priority | ID | Action |
|----------|----|--------|
| Medium | SEC-004 | Document Redis HA requirement; evaluate fail-secure option |
| Medium | SEC-006 | Migrate access token from localStorage to memory-based store |
| Low | SEC-008 | Add `ondelete="SET NULL"` to audit-trail FK columns |
| Low | MODEL-002/004 | Add `updated_at` to Arac, Sofor, Lokasyon (requires migration) |
| Low | ARCH-001 | Replace virtual superadmin `id=0` with real seeded user |
| Low | TEST-005 | Align `pytest.ini` coverage threshold to 92 |
| Low | TEST-006 | Add executive endpoint tests (FVI, carbon, compliance, what-if) |
| Backlog | ARCH-005 | Remove sync engine once all callers migrated |
| Backlog | MINOR-009 | Migrate `python-jose` → `PyJWT + cryptography` |
