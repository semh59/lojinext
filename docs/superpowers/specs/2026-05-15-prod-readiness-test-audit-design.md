# Prod-Readiness Test Audit — LojiNext

**Date:** 2026-05-15
**Scope:** End-to-end business processes; fill coverage gaps only (preserve existing tests)
**Environment:** Docker stack running with real env vars (`docker-compose up -d`)

---

## Context

LojiNext has ~90 backend test files and ~27 frontend test files across unit, integration, security, and resilience categories. However, analysis reveals these gaps:

- No full TIR lifecycle integration test (vehicle → trip → fuel → anomaly → report as one flow)
- API response schema validation is scattered and incomplete — several endpoints return unverified shapes
- ML ensemble predictor cold-start invariants (physics weight ≥ 0.80) are not asserted at the API level
- RBAC is tested for auth but not systematically enforced across all admin endpoints
- Frontend Vitest tests mock all API calls — no test verifies the real backend contract

---

## Approach: Layered Gap-Filling (B)

Six isolated test files. Each layer can run independently in CI as a separate stage.

```
Layer 1  →  app/tests/integration/test_db_schema_integrity.py
Layer 2  →  app/tests/integration/test_api_contracts.py
Layer 3  →  app/tests/integration/test_business_lifecycle.py
Layer 4  →  app/tests/security/test_rbac_coverage.py
Layer 5  →  frontend/src/services/api/__tests__/backend-contract.test.ts
Layer 6  →  app/tests/integration/test_ml_ai_pipeline.py
```

All backend tests use `@pytest.mark.integration`, the existing `async_client` and `admin_auth_headers` fixtures from `app/tests/conftest.py`. No new fixtures required.

---

## Layer 1 — DB Schema Integrity

**File:** `app/tests/integration/test_db_schema_integrity.py`

**Goal:** Verify that database-level constraints are actually enforced, not just assumed.

| Test | What it does | Expected |
|------|-------------|----------|
| `test_fk_vehicles_on_trips` | Insert a trip with a non-existent `arac_id` | `IntegrityError` raised |
| `test_fk_drivers_on_trips` | Insert a trip with a non-existent `sofor_id` | `IntegrityError` raised |
| `test_check_tank_kapasitesi` | Insert vehicle with `tank_kapasitesi = -1` | `IntegrityError` raised |
| `test_check_mesafe_km` | Insert location with `mesafe_km = 0` | `IntegrityError` raised |
| `test_soft_delete_filter` | Create vehicle, set `is_deleted=True`, call `GET /vehicles/` | Vehicle absent from list |
| `test_materialized_view_refresh` | Create trip + fuel entry, call `REFRESH MATERIALIZED VIEW sefer_istatistik_mv` | MV returns updated aggregate |
| `test_unique_plaka` | Insert two vehicles with same `plaka` | `IntegrityError` raised |
| `test_composite_indexes_exist` | Query `pg_indexes` for expected indexes from `0004_composite_indexes.py` | All indexes present |

---

## Layer 2 — API Contract Tests

**File:** `app/tests/integration/test_api_contracts.py`

**Goal:** Assert that every critical endpoint returns the documented response shape with correct types. No NaN, no missing required fields.

### Vehicles — `POST /api/v1/vehicles/`
Response must contain: `id` (int), `plaka` (str), `aktif` (bool), `tank_kapasitesi` (float > 0), `hedef_tuketim` (float > 0)

### Drivers — `POST /api/v1/drivers/`
Response must contain: `id` (int), `ad_soyad` (str), `aktif` (bool), `ehliyet_sinifi` (str)

### Trips — `GET /api/v1/trips/{id}`
Response must contain nested: `arac.plaka`, `sofor.ad_soyad`, `lokasyon.cikis_yeri`, `lokasyon.varis_yeri`. All must be non-null strings.

### Fuel — `GET /api/v1/fuel/?sefer_id={id}`
`yakit_miktari_lt` and `yakit_fiyati_tl` must be `float`, not NaN, not null.

### Reports — `GET /api/v1/reports/fuel`
`toplam_yakit_lt`, `toplam_maliyet_tl`, `ortalama_tuketim` must be `float` (never NaN).
Response must include `generated_at` ISO timestamp.

### Predictions — `GET /api/v1/predictions/{sefer_id}`
Must contain: `predicted_value` (float > 0), `confidence_interval` (object with `lower`, `upper`), `model_used` (str), `physics_weight` (float).

### Pagination envelope — any list endpoint
`GET /api/v1/vehicles/?limit=5&offset=0` → response must have `total` (int ≥ 0) and `items` (list).

### Error envelope — `GET /api/v1/trips/99999999`
Response body must match `{"error": {"code": ..., "message": ..., "trace_id": ...}}`.

---

## Layer 3 — Business Lifecycle

**File:** `app/tests/integration/test_business_lifecycle.py`

**Goal:** Verify the full TIR lifecycle in sequence. Each step depends on the previous step's output. The entire test is a single `async` function with a `finally` cleanup block.

```
Step 1  POST /api/v1/vehicles/       →  arac_id
Step 2  POST /api/v1/drivers/        →  sofor_id
Step 3  POST /api/v1/locations/      →  lokasyon_id
Step 4  POST /api/v1/trips/          →  sefer_id   (references arac_id, sofor_id, lokasyon_id)
Step 5  POST /api/v1/fuel/           →  yakit_id   (references sefer_id)
Step 6  GET  /api/v1/anomalies/?sefer_id={sefer_id}  →  list (may be empty, must not 500)
Step 7  GET  /api/v1/reports/fuel?sefer_id={sefer_id}  →  report with non-null totals
Step 8  DELETE /api/v1/trips/{sefer_id}  →  204 (soft-delete)
Step 9  Cleanup: delete yakit, lokasyon, sofor, arac
```

**Assertions at each step:**
- HTTP status is `2xx`
- Response body parses as JSON
- Required fields are present and non-null
- Cross-references (IDs) in later responses match earlier created entities

---

## Layer 4 — RBAC Coverage

**File:** `app/tests/security/test_rbac_coverage.py`

**Goal:** Systematically verify that every admin endpoint returns `403` for non-admin users, and that expired / missing tokens return `401`.

### Admin endpoint 403 matrix (user role)
| Endpoint | Method | Expected |
|----------|--------|----------|
| `/api/v1/admin/users/` | GET | 403 |
| `/api/v1/admin/users/{id}` | DELETE | 403 |
| `/api/v1/admin/ml/retrain` | POST | 403 |
| `/api/v1/admin/config` | GET | 403 |
| `/api/v1/admin/maintenance` | POST | 403 |
| `/api/v1/admin/calibration` | POST | 403 |

### Token expiry — 401
- Expired JWT (manually backdated `exp` claim) → all protected endpoints return 401
- Missing `Authorization` header → 401

### httpOnly refresh cookie
- `POST /api/v1/auth/refresh` with no cookie → 401 (not 500, not 200)
- `POST /api/v1/auth/refresh` with valid httpOnly cookie → 200 + new `access_token`

### Driver role isolation
- Driver token can `GET /api/v1/trips/?sofor_id={own_id}` → 200
- Driver token cannot `DELETE /api/v1/trips/{other_sefer_id}` → 403

---

## Layer 5 — Frontend Backend Contract

**File:** `frontend/src/services/api/__tests__/backend-contract.test.ts`

**Goal:** Verify that the real running Docker backend returns shapes the frontend TypeScript types expect. No mocks — direct `axios` calls to `http://localhost:8000`.

**Setup:** Skip test if `VITE_API_BASE_URL` not set or if backend is unreachable (detect with a pre-test health check).

| Test | Endpoint | TypeScript type asserted |
|------|----------|--------------------------|
| `vehicles list shape` | `GET /api/v1/vehicles/` | `VehicleResponse[]` — `id`, `plaka`, `aktif` present |
| `trips list shape` | `GET /api/v1/trips/` | `TripListResponse` — `items`, `total` present |
| `locations list shape` | `GET /api/v1/locations/` | `LocationResponse[]` |
| `auth token shape` | `POST /api/v1/auth/login` | `access_token` (str), `token_type === "bearer"` |

All type assertions are runtime checks using `typeof` and property existence — not TypeScript compilation.

---

## Layer 6 — ML/AI Pipeline

**File:** `app/tests/integration/test_ml_ai_pipeline.py`

**Goal:** Verify ML and AI subsystems behave correctly at the API boundary.

### Ensemble predictor cold-start invariant
After creating a sefer with no historical training data:
`GET /api/v1/predictions/{sefer_id}` → `physics_weight ≥ 0.80`

### Ensemble output validity
- `predicted_value > 0`
- `confidence_interval.lower < predicted_value < confidence_interval.upper`
- `model_used` is one of `["physics", "ensemble", "lightgbm", "fallback"]`

### Dynamic weights sum
`GET /api/v1/admin/ml/weights` → all model weights sum to `1.0` (within `0.001` tolerance)

### RAG engine
`POST /api/v1/ai/query` with `{"query": "Yakıt anomalisi nedir?"}`:
- Status `200`
- `answer` field is non-empty string in Turkish
- `sources` list is non-empty (FAISS index has entries)

### Anomaly detection pipeline
After creating a sefer and adding a fuel record with extreme consumption (3× expected):
`GET /api/v1/anomalies/?sefer_id={sefer_id}` → at least one anomaly with `severity`, `description`, `detected_at` fields non-null.

### LLM graceful fallback
When Groq API is unavailable (mock with `monkeypatch` or use invalid key in test):
`POST /api/v1/ai/query` → `200` or `503` with proper error envelope — must NOT raise unhandled exception (not 500 without envelope).

---

## CI Integration

Add these stages to `.github/workflows/ci.yml` after existing unit tests:

```yaml
- name: Integration tests (DB + contracts + lifecycle)
  run: pytest app/tests/integration/ -m integration -x -q --timeout=60

- name: Security tests (RBAC)
  run: pytest app/tests/security/ -x -q

- name: ML/AI pipeline tests
  run: pytest app/tests/integration/test_ml_ai_pipeline.py -x -q

- name: Frontend backend contract
  run: cd frontend && npx vitest run src/services/api/__tests__/backend-contract.test.ts
  env:
    VITE_API_BASE_URL: http://localhost:8000
```

---

## Success Criteria

- All 6 layers pass with 0 failures on Docker stack
- No `pytest.skip` unless explicitly marked with reason
- Coverage delta: +5% minimum on `app/core/ml/`, `app/core/ai/`, `app/api/v1/endpoints/`
- No test modifies shared state without cleanup in `finally` block
- Each layer completes in < 60 seconds independently
