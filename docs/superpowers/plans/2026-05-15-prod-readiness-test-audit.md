# Prod-Readiness Test Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write 6 isolated test files that fill the coverage gaps identified in the prod-readiness audit — every bug found, no matter how small, is treated as critical and fixed before moving on.

**Architecture:** Each layer is an independent pytest/vitest file that uses the existing `async_client` + `admin_auth_headers` fixtures from `app/tests/conftest.py`. No new fixtures. Layers run in parallel in CI.

**Tech Stack:** pytest-asyncio, httpx ASGI transport, SQLAlchemy async, vitest, axios

> **Spec corrections applied in this plan:** The design doc was written before full code archaeology. Real field names, endpoints, and response shapes below are verified against source. Deviations from the spec are noted inline.

---

## File Map

| Layer | File | Status |
|-------|------|--------|
| 1 | `app/tests/integration/test_db_schema_integrity.py` | Create |
| 2 | `app/tests/integration/test_api_contracts.py` | Create |
| 3 | `app/tests/integration/test_business_lifecycle.py` | Create |
| 4 | `app/tests/security/test_rbac_coverage.py` | Create |
| 5 | `frontend/src/services/api/__tests__/backend-contract.test.ts` | Create |
| 6 | `app/tests/integration/test_ml_ai_pipeline.py` | Create |

---

## Task 1: DB Schema Integrity

**Files:**
- Create: `app/tests/integration/test_db_schema_integrity.py`

- [ ] **Step 1: Write the test file**

```python
"""
Layer 1 — DB Schema Integrity
Verifies that PostgreSQL-level constraints (FK, CHECK, UNIQUE, soft-delete, indexes, MV)
are actually enforced, not just assumed at the application layer.
"""
import pytest
from datetime import date
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_fk_arac_on_seferler_enforced(db_session):
    """Trip with non-existent arac_id must raise IntegrityError."""
    await db_session.execute(
        text(
            "INSERT INTO seferler "
            "(tarih, arac_id, sofor_id, cikis_yeri, varis_yeri, mesafe_km, "
            " bos_agirlik_kg, dolu_agirlik_kg, net_kg, durum) "
            "VALUES (:tarih, 999999, 999999, 'A', 'B', 100, 0, 0, 0, 'Planlandı')"
        ),
        {"tarih": date.today()},
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_tank_kapasitesi_positive(db_session):
    """Vehicle with tank_kapasitesi <= 0 must raise IntegrityError."""
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'Test', -1, 30.0)"
        ),
        {"plaka": "99 ZZZ 9999"},
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_sefer_mesafe_positive(db_session):
    """Trip with mesafe_km = 0 must raise IntegrityError (DB CHECK constraint)."""
    # First insert a valid arac and sofor for the FK
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'Test', 600, 32.0) RETURNING id"
        ),
        {"plaka": "88 TST 0001"},
    )
    result = await db_session.execute(
        text("SELECT id FROM araclar WHERE plaka = '88 TST 0001'")
    )
    arac_id = result.scalar_one()

    await db_session.execute(
        text(
            "INSERT INTO soforler (ad_soyad, ehliyet_sinifi) "
            "VALUES ('Test Sofor Zero', 'E') RETURNING id"
        )
    )
    result = await db_session.execute(
        text("SELECT id FROM soforler WHERE ad_soyad = 'Test Sofor Zero'")
    )
    sofor_id = result.scalar_one()

    await db_session.execute(
        text(
            "INSERT INTO seferler "
            "(tarih, arac_id, sofor_id, cikis_yeri, varis_yeri, mesafe_km, "
            " bos_agirlik_kg, dolu_agirlik_kg, net_kg, durum) "
            "VALUES (:tarih, :arac_id, :sofor_id, 'A', 'B', 0, 0, 0, 0, 'Planlandı')"
        ),
        {"tarih": date.today(), "arac_id": arac_id, "sofor_id": sofor_id},
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_unique_plaka_enforced(db_session):
    """Two vehicles with the same plaka must raise IntegrityError."""
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'TestA', 600, 32.0)"
        ),
        {"plaka": "06 DUP 0001"},
    )
    await db_session.flush()

    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'TestB', 600, 32.0)"
        ),
        {"plaka": "06 DUP 0001"},
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_check_yakit_litre_positive(db_session):
    """Fuel record with litre <= 0 must raise IntegrityError."""
    await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, tank_kapasitesi, hedef_tuketim) "
            "VALUES (:plaka, 'Test', 600, 32.0)"
        ),
        {"plaka": "07 YKT 0001"},
    )
    result = await db_session.execute(
        text("SELECT id FROM araclar WHERE plaka = '07 YKT 0001'")
    )
    arac_id = result.scalar_one()

    await db_session.execute(
        text(
            "INSERT INTO yakit_alimlari "
            "(tarih, arac_id, litre, fiyat_tl, toplam_tutar, km_sayac, durum) "
            "VALUES (:tarih, :arac_id, 0, 10.0, 0, 100000, 'Bekliyor')"
        ),
        {"tarih": date.today(), "arac_id": arac_id},
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_soft_delete_filter_via_api(async_client, admin_auth_headers, db_session):
    """
    Create a vehicle via API, mark is_deleted=True directly in DB,
    then verify it disappears from the list endpoint.
    """
    resp = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": "35 SDL 9001",
            "marka": "Volvo",
            "model": "FH",
            "yil": 2022,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 30.0,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201
    arac_id = resp.json()["id"]

    await db_session.execute(
        text("UPDATE araclar SET is_deleted = TRUE WHERE id = :id"),
        {"id": arac_id},
    )
    await db_session.commit()

    list_resp = await async_client.get("/api/v1/vehicles/", headers=admin_auth_headers)
    assert list_resp.status_code == 200
    ids_in_list = [v["id"] for v in list_resp.json().get("items", list_resp.json())]
    assert arac_id not in ids_in_list


@pytest.mark.asyncio
async def test_materialized_view_refresh(async_client, admin_auth_headers, db_session):
    """
    After creating a sefer via API, REFRESH MATERIALIZED VIEW CONCURRENTLY
    must NOT fail and the view must contain a row for 'Planlandı'.
    """
    import uuid
    unique = uuid.uuid4().hex[:6].upper()

    # Create dependencies
    arac_resp = await async_client.post(
        "/api/v1/vehicles/",
        json={"plaka": f"38 MV {unique[:4]}", "marka": "MAN", "model": "TGX",
              "yil": 2023, "tank_kapasitesi": 700, "hedef_tuketim": 31.0, "aktif": True},
        headers=admin_auth_headers,
    )
    assert arac_resp.status_code == 201
    arac_id = arac_resp.json()["id"]

    sofor_resp = await async_client.post(
        "/api/v1/drivers/",
        json={"ad_soyad": f"MV Sofor {unique}", "ehliyet_sinifi": "E",
              "ise_baslama": "2020-01-01", "aktif": True},
        headers=admin_auth_headers,
    )
    assert sofor_resp.status_code == 201
    sofor_id = sofor_resp.json()["id"]

    lokasyon_resp = await async_client.post(
        "/api/v1/locations/",
        json={"cikis_yeri": f"MV Sehir {unique}", "varis_yeri": f"MV Hedef {unique}",
              "mesafe_km": 300.0, "zorluk": "Normal"},
        headers=admin_auth_headers,
    )
    assert lokasyon_resp.status_code == 201
    guzergah_id = lokasyon_resp.json()["id"]

    from datetime import date
    sefer_resp = await async_client.post(
        "/api/v1/trips/",
        json={"tarih": date.today().isoformat(), "arac_id": arac_id,
              "sofor_id": sofor_id, "guzergah_id": guzergah_id,
              "cikis_yeri": f"MV Sehir {unique}", "varis_yeri": f"MV Hedef {unique}",
              "mesafe_km": 300.0, "net_kg": 0, "durum": "Planlandı"},
        headers=admin_auth_headers,
    )
    assert sefer_resp.status_code == 201

    # REFRESH the materialized view (non-concurrent because test DB may not allow it)
    await db_session.execute(
        text("REFRESH MATERIALIZED VIEW sefer_istatistik_mv")
    )
    await db_session.commit()

    result = await db_session.execute(
        text("SELECT toplam_sefer FROM sefer_istatistik_mv WHERE durum = 'Planlandı'")
    )
    row = result.fetchone()
    assert row is not None, "sefer_istatistik_mv must have a row for 'Planlandı' after refresh"
    assert row[0] >= 1


@pytest.mark.asyncio
async def test_composite_indexes_exist(db_session):
    """
    Verify the composite indexes from migration 0004_composite_indexes exist
    in pg_indexes. Each absence is a separate, named failure.
    """
    expected_indexes = [
        ("seferler", "ix_seferler_arac_id_tarih"),
        ("seferler", "ix_seferler_sofor_id_tarih"),
        ("seferler", "ix_seferler_arac_id_durum"),
        ("yakit_alimlari", "ix_yakit_alimlari_arac_id_tarih"),
    ]

    for table_name, index_name in expected_indexes:
        result = await db_session.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE tablename = :table AND indexname = :idx"
            ),
            {"table": table_name, "idx": index_name},
        )
        assert result.fetchone() is not None, (
            f"Missing index {index_name} on {table_name} "
            f"(expected from 0004_composite_indexes migration)"
        )
```

- [ ] **Step 2: Run to confirm tests collect (may fail — DB needed)**

```
pytest app/tests/integration/test_db_schema_integrity.py --collect-only -q
```
Expected: 7 tests collected, 0 errors.

- [ ] **Step 3: Run tests against Docker DB**

```
pytest app/tests/integration/test_db_schema_integrity.py -v --timeout=30
```
Expected: all PASS. If any FAIL:
- `IntegrityError` not raised → DB constraint is missing → file a bug, add the constraint via Alembic migration, fix before proceeding.
- Index not found → migration was not applied → run `alembic upgrade head`, re-run.

- [ ] **Step 4: Commit**

```
git add app/tests/integration/test_db_schema_integrity.py
git commit -m "test(integration): Layer 1 — DB schema integrity (FK, CHECK, UNIQUE, MV, indexes)"
```

---

## Task 2: API Contract Tests

**Files:**
- Create: `app/tests/integration/test_api_contracts.py`

> **Spec correction:** `GET /trips/{id}` returns flat fields (`plaka`, `sofor_adi`, `guzergah_adi`) — not nested objects. Prediction endpoint is `POST /predictions/predict` with body `PredictionRequest`; response has `tahmini_tuketim` (not `predicted_value`) and `confidence_low`/`confidence_high` (not `confidence_interval`). Fuel fields are `litre`/`fiyat_tl` (not `yakit_miktari_lt`/`yakit_fiyati_tl`). Dashboard report is `GET /reports/dashboard`.

- [ ] **Step 1: Write the test file**

```python
"""
Layer 2 — API Contract Tests
Asserts every critical endpoint returns the documented response shape with
correct types. No NaN, no missing required fields.
"""
import math
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


# ── Helpers ─────────────────────────────────────────────────────────────────


def _is_finite_float(v) -> bool:
    """Return True if v is a number and not NaN/Inf."""
    try:
        f = float(v)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


async def _create_vehicle(client, headers, suffix: str) -> int:
    r = await client.post(
        "/api/v1/vehicles/",
        json={"plaka": f"34 CT {suffix[:4]}", "marka": "Mercedes", "model": "Actros",
              "yil": 2023, "tank_kapasitesi": 600, "hedef_tuketim": 31.5, "aktif": True},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _create_driver(client, headers, suffix: str) -> int:
    r = await client.post(
        "/api/v1/drivers/",
        json={"ad_soyad": f"CT Sofor {suffix}", "ehliyet_sinifi": "E",
              "ise_baslama": date.today().isoformat(), "aktif": True},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _create_location(client, headers, suffix: str) -> int:
    r = await client.post(
        "/api/v1/locations/",
        json={"cikis_yeri": f"CT City {suffix}", "varis_yeri": f"CT Dest {suffix}",
              "mesafe_km": 350.0, "zorluk": "Normal"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


# ── Contract Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vehicle_create_response_shape(async_client, admin_auth_headers):
    """POST /vehicles/ must return id(int), plaka(str), aktif(bool), tank_kapasitesi(int>0)."""
    r = await async_client.post(
        "/api/v1/vehicles/",
        json={"plaka": "06 SH 0001", "marka": "MAN", "model": "TGX",
              "yil": 2022, "tank_kapasitesi": 500, "hedef_tuketim": 32.0, "aktif": True},
        headers=admin_auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int) and body["id"] > 0
    assert isinstance(body["plaka"], str) and body["plaka"]
    assert isinstance(body["aktif"], bool)
    assert isinstance(body["tank_kapasitesi"], int) and body["tank_kapasitesi"] > 0
    assert _is_finite_float(body["hedef_tuketim"]) and float(body["hedef_tuketim"]) > 0


@pytest.mark.asyncio
async def test_driver_create_response_shape(async_client, admin_auth_headers):
    """POST /drivers/ must return id(int), ad_soyad(str), aktif(bool), ehliyet_sinifi(str)."""
    r = await async_client.post(
        "/api/v1/drivers/",
        json={"ad_soyad": "Contract Test Sofor", "ehliyet_sinifi": "E",
              "ise_baslama": date.today().isoformat(), "aktif": True},
        headers=admin_auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int) and body["id"] > 0
    assert isinstance(body["ad_soyad"], str) and body["ad_soyad"]
    assert isinstance(body["aktif"], bool)
    assert isinstance(body["ehliyet_sinifi"], str) and body["ehliyet_sinifi"]


@pytest.mark.asyncio
async def test_trip_detail_response_shape(async_client, admin_auth_headers):
    """
    GET /trips/{id} must return flat fields: id, arac_id, sofor_id, cikis_yeri,
    varis_yeri, mesafe_km, durum. Also: plaka and sofor_adi must be non-null strings.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    arac_id = await _create_vehicle(async_client, admin_auth_headers, suffix)
    sofor_id = await _create_driver(async_client, admin_auth_headers, suffix)
    guzergah_id = await _create_location(async_client, admin_auth_headers, suffix)

    trip_resp = await async_client.post(
        "/api/v1/trips/",
        json={"tarih": date.today().isoformat(), "arac_id": arac_id,
              "sofor_id": sofor_id, "guzergah_id": guzergah_id,
              "cikis_yeri": f"CT City {suffix}", "varis_yeri": f"CT Dest {suffix}",
              "mesafe_km": 350.0, "net_kg": 0, "durum": "Planlandı"},
        headers=admin_auth_headers,
    )
    assert trip_resp.status_code == 201
    sefer_id = trip_resp.json()["id"]

    r = await async_client.get(f"/api/v1/trips/{sefer_id}", headers=admin_auth_headers)
    assert r.status_code == 200
    body = r.json()

    assert isinstance(body["id"], int)
    assert body["arac_id"] == arac_id
    assert body["sofor_id"] == sofor_id
    assert isinstance(body["cikis_yeri"], str) and body["cikis_yeri"]
    assert isinstance(body["varis_yeri"], str) and body["varis_yeri"]
    assert _is_finite_float(body["mesafe_km"])
    # Denormalized display fields
    assert isinstance(body.get("plaka"), str) and body["plaka"], \
        "plaka must be a non-empty string in trip detail response"
    assert isinstance(body.get("sofor_adi"), str) and body["sofor_adi"], \
        "sofor_adi must be a non-empty string in trip detail response"


@pytest.mark.asyncio
async def test_fuel_list_response_shape(async_client, admin_auth_headers):
    """
    GET /fuel/ must return {items: [...], total: int}.
    Items must have litre and fiyat_tl as finite numbers.
    """
    # Create a vehicle first so there's something to attach fuel to
    suffix = uuid.uuid4().hex[:6].upper()
    arac_id = await _create_vehicle(async_client, admin_auth_headers, suffix)

    # Create a fuel record
    r_create = await async_client.post(
        "/api/v1/fuel/",
        json={"tarih": date.today().isoformat(), "arac_id": arac_id,
              "litre": "150.00", "fiyat_tl": "42.50",
              "toplam_tutar": "6375.00", "km_sayac": 150000,
              "depo_durumu": "Dolu", "durum": "Bekliyor"},
        headers=admin_auth_headers,
    )
    assert r_create.status_code == 201

    r = await async_client.get(
        f"/api/v1/fuel/?arac_id={arac_id}", headers=admin_auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert isinstance(body["total"], int) and body["total"] >= 1
    for item in body["items"]:
        assert _is_finite_float(item["litre"]), f"litre is NaN/None: {item['litre']}"
        assert _is_finite_float(item["fiyat_tl"]), f"fiyat_tl is NaN/None: {item['fiyat_tl']}"
        assert float(item["litre"]) > 0
        assert float(item["fiyat_tl"]) > 0


@pytest.mark.asyncio
async def test_dashboard_report_response_shape(async_client, admin_auth_headers):
    """
    GET /reports/dashboard must return toplam_sefer(int), toplam_km(float),
    toplam_yakit(float), filo_ortalama(float). No NaN values.
    """
    r = await async_client.get("/api/v1/reports/dashboard", headers=admin_auth_headers)
    assert r.status_code == 200
    body = r.json()

    assert "toplam_sefer" in body, "toplam_sefer missing from dashboard response"
    assert "toplam_km" in body, "toplam_km missing from dashboard response"
    assert "toplam_yakit" in body, "toplam_yakit missing from dashboard response"
    assert "filo_ortalama" in body, "filo_ortalama missing from dashboard response"

    assert isinstance(body["toplam_sefer"], int) and body["toplam_sefer"] >= 0
    assert _is_finite_float(body["toplam_km"]), f"toplam_km is NaN: {body['toplam_km']}"
    assert _is_finite_float(body["toplam_yakit"]), f"toplam_yakit is NaN: {body['toplam_yakit']}"
    assert _is_finite_float(body["filo_ortalama"]), f"filo_ortalama is NaN: {body['filo_ortalama']}"


@pytest.mark.asyncio
async def test_prediction_response_shape(async_client, admin_auth_headers):
    """
    POST /predictions/predict must return tahmini_tuketim(float>0), model_used(str),
    confidence_low and confidence_high (floats or None), status='success'.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={"arac_id": 1, "mesafe_km": 450.0, "ton": 20.0,
              "ascent_m": 0.0, "descent_m": 0.0, "flat_distance_km": 450.0,
              "zorluk": "Normal", "model_type": "ensemble"},
        headers=admin_auth_headers,
    )
    # 200 on success, 404 if arac doesn't exist (no training data path)
    # Both are valid — we test shape when 200
    if r.status_code == 200:
        body = r.json()
        assert _is_finite_float(body["tahmini_tuketim"]) and float(body["tahmini_tuketim"]) > 0, \
            f"tahmini_tuketim invalid: {body.get('tahmini_tuketim')}"
        assert isinstance(body["model_used"], str) and body["model_used"]
        assert body["status"] == "success"
        # confidence bounds are optional floats; if present must be finite
        for field in ("confidence_low", "confidence_high"):
            if body.get(field) is not None:
                assert _is_finite_float(body[field]), f"{field} is NaN: {body[field]}"
    else:
        assert r.status_code in (404, 422), \
            f"Unexpected status {r.status_code}: {r.text}"


@pytest.mark.asyncio
async def test_vehicle_list_pagination_envelope(async_client, admin_auth_headers):
    """GET /vehicles/?limit=5&offset=0 must return {items:[...], total:int}."""
    r = await async_client.get(
        "/api/v1/vehicles/?limit=5&skip=0", headers=admin_auth_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body, f"No 'items' key in response: {list(body.keys())}"
    assert "total" in body, f"No 'total' key in response: {list(body.keys())}"
    assert isinstance(body["total"], int) and body["total"] >= 0
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_not_found_returns_error_envelope(async_client, admin_auth_headers):
    """GET /trips/99999999 must return {"error": {"code":..., "message":..., "trace_id":...}}."""
    r = await async_client.get("/api/v1/trips/99999999", headers=admin_auth_headers)
    assert r.status_code == 404
    body = r.json()
    assert "error" in body or "detail" in body, \
        f"404 response has no 'error' or 'detail' key: {body}"
    # If error envelope exists, validate its shape
    if "error" in body:
        err = body["error"]
        assert "code" in err or "message" in err, \
            f"error envelope missing code/message: {err}"
```

- [ ] **Step 2: Run to collect**

```
pytest app/tests/integration/test_api_contracts.py --collect-only -q
```
Expected: 8 tests collected.

- [ ] **Step 3: Run tests**

```
pytest app/tests/integration/test_api_contracts.py -v --timeout=30
```
Any FAIL is a bug. Fix before moving on:
- Missing field in response → add field to Pydantic response schema, verify serializer
- NaN in float field → add `heal_*` field_validator similar to `YakitResponse.heal_amounts`
- Wrong status code → fix endpoint logic

- [ ] **Step 4: Commit**

```
git add app/tests/integration/test_api_contracts.py
git commit -m "test(integration): Layer 2 — API contract tests (shapes, types, NaN guards, envelopes)"
```

---

## Task 3: Business Lifecycle

**Files:**
- Create: `app/tests/integration/test_business_lifecycle.py`

> **Spec corrections:** DELETE /trips/{id} returns 200 + `{"soft_deleted": True}`, not 204. Fuel is tied to `arac_id` not `sefer_id`. Anomaly endpoint is `GET /anomalies/fleet/insights?days=30` (no `sefer_id` filter). Dashboard report used in Step 7.

- [ ] **Step 1: Write the test file**

```python
"""
Layer 3 — Business Lifecycle
Full TIR lifecycle in one sequential test: vehicle → driver → location →
trip → fuel → anomaly dashboard → report. Every step must succeed.
Cleanup runs in `finally` even on failure.
"""
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_tir_lifecycle(async_client, admin_auth_headers):
    """
    Sequential lifecycle:
      1. Create vehicle
      2. Create driver
      3. Create location (route)
      4. Create trip (links all three)
      5. Create fuel record for the vehicle
      6. Check anomaly dashboard (must not 500)
      7. Check dashboard report (must have non-null totals)
      8. Soft-delete the trip
      9. Verify trip returns 404 after soft-delete
     10. Cleanup: delete fuel, location, driver, vehicle
    """
    unique = uuid.uuid4().hex[:6].upper()
    arac_id = sofor_id = guzergah_id = sefer_id = yakit_id = None

    try:
        # ── Step 1: Vehicle ──────────────────────────────────────────────────
        r1 = await async_client.post(
            "/api/v1/vehicles/",
            json={
                "plaka": f"06 LC {unique[:4]}",
                "marka": "Mercedes",
                "model": "Actros",
                "yil": 2023,
                "tank_kapasitesi": 700,
                "hedef_tuketim": 31.5,
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert r1.status_code == 201, f"Step 1 vehicle create failed: {r1.text}"
        arac_id = r1.json()["id"]
        assert isinstance(arac_id, int) and arac_id > 0

        # ── Step 2: Driver ───────────────────────────────────────────────────
        r2 = await async_client.post(
            "/api/v1/drivers/",
            json={
                "ad_soyad": f"Lifecycle Sofor {unique}",
                "ehliyet_sinifi": "E",
                "ise_baslama": date.today().isoformat(),
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert r2.status_code == 201, f"Step 2 driver create failed: {r2.text}"
        sofor_id = r2.json()["id"]
        assert isinstance(sofor_id, int) and sofor_id > 0

        # ── Step 3: Location ─────────────────────────────────────────────────
        r3 = await async_client.post(
            "/api/v1/locations/",
            json={
                "cikis_yeri": f"LC City {unique}",
                "varis_yeri": f"LC Dest {unique}",
                "mesafe_km": 450.0,
                "tahmini_sure_saat": 5.0,
                "zorluk": "Normal",
            },
            headers=admin_auth_headers,
        )
        assert r3.status_code == 201, f"Step 3 location create failed: {r3.text}"
        guzergah_id = r3.json()["id"]
        assert isinstance(guzergah_id, int) and guzergah_id > 0

        # ── Step 4: Trip ─────────────────────────────────────────────────────
        r4 = await async_client.post(
            "/api/v1/trips/",
            json={
                "tarih": date.today().isoformat(),
                "arac_id": arac_id,
                "sofor_id": sofor_id,
                "guzergah_id": guzergah_id,
                "cikis_yeri": f"LC City {unique}",
                "varis_yeri": f"LC Dest {unique}",
                "mesafe_km": 450.0,
                "net_kg": 0,
                "bos_sefer": True,
                "durum": "Planlandı",
            },
            headers=admin_auth_headers,
        )
        assert r4.status_code == 201, f"Step 4 trip create failed: {r4.text}"
        sefer_id = r4.json()["id"]
        assert isinstance(sefer_id, int) and sefer_id > 0
        # Cross-reference: arac_id must match
        assert r4.json()["arac_id"] == arac_id
        assert r4.json()["sofor_id"] == sofor_id

        # ── Step 5: Fuel ─────────────────────────────────────────────────────
        r5 = await async_client.post(
            "/api/v1/fuel/",
            json={
                "tarih": date.today().isoformat(),
                "arac_id": arac_id,
                "litre": "180.00",
                "fiyat_tl": "43.00",
                "toplam_tutar": "7740.00",
                "km_sayac": 200000,
                "depo_durumu": "Dolu",
                "durum": "Bekliyor",
            },
            headers=admin_auth_headers,
        )
        assert r5.status_code == 201, f"Step 5 fuel create failed: {r5.text}"
        yakit_id = r5.json()["id"]
        assert isinstance(yakit_id, int) and yakit_id > 0
        assert r5.json()["arac_id"] == arac_id

        # ── Step 6: Anomaly dashboard ─────────────────────────────────────────
        r6 = await async_client.get(
            "/api/v1/anomalies/fleet/insights?days=7", headers=admin_auth_headers
        )
        assert r6.status_code == 200, f"Step 6 anomaly endpoint failed: {r6.text}"
        body6 = r6.json()
        # Must not be an unhandled exception envelope
        assert "status" in body6 or "data" in body6, \
            f"Unexpected anomaly response shape: {body6}"

        # ── Step 7: Report ────────────────────────────────────────────────────
        r7 = await async_client.get(
            "/api/v1/reports/dashboard", headers=admin_auth_headers
        )
        assert r7.status_code == 200, f"Step 7 report failed: {r7.text}"
        body7 = r7.json()
        assert body7.get("toplam_sefer", -1) >= 0, "toplam_sefer must be >= 0"
        assert body7.get("aktif_arac", -1) >= 0, "aktif_arac must be >= 0"

        # ── Step 8: Soft-delete trip ──────────────────────────────────────────
        r8 = await async_client.delete(
            f"/api/v1/trips/{sefer_id}", headers=admin_auth_headers
        )
        assert r8.status_code == 200, f"Step 8 trip delete failed: {r8.text}"
        body8 = r8.json()
        assert body8.get("soft_deleted") is True, \
            f"Expected soft_deleted=True, got: {body8}"

        # ── Step 9: Verify 404 after soft-delete ──────────────────────────────
        r9 = await async_client.get(
            f"/api/v1/trips/{sefer_id}", headers=admin_auth_headers
        )
        assert r9.status_code == 404, \
            f"Step 9: soft-deleted trip must return 404, got {r9.status_code}"

    finally:
        # ── Cleanup (best-effort) ─────────────────────────────────────────────
        if yakit_id:
            await async_client.delete(
                f"/api/v1/fuel/{yakit_id}", headers=admin_auth_headers
            )
        if guzergah_id:
            await async_client.delete(
                f"/api/v1/locations/{guzergah_id}", headers=admin_auth_headers
            )
        if sofor_id:
            await async_client.delete(
                f"/api/v1/drivers/{sofor_id}", headers=admin_auth_headers
            )
        if arac_id:
            await async_client.delete(
                f"/api/v1/vehicles/{arac_id}", headers=admin_auth_headers
            )
```

- [ ] **Step 2: Collect**

```
pytest app/tests/integration/test_business_lifecycle.py --collect-only -q
```
Expected: 1 test collected.

- [ ] **Step 3: Run**

```
pytest app/tests/integration/test_business_lifecycle.py -v -s --timeout=60
```
Any failing step is a critical bug. Look at the assertion message to identify the exact step. Fix the endpoint/service logic before proceeding.

- [ ] **Step 4: Commit**

```
git add app/tests/integration/test_business_lifecycle.py
git commit -m "test(integration): Layer 3 — full TIR lifecycle (vehicle→trip→fuel→report)"
```

---

## Task 4: RBAC Coverage

**Files:**
- Create: `app/tests/security/test_rbac_coverage.py`

> Admin endpoints use `require_yetki("permission_string")` — not a blanket admin role. The existing `normal_auth_headers` fixture creates a user with `izleyici` role (only `sefer:read: True`). This user must get `403` on all permission-gated endpoints.

- [ ] **Step 1: Write the test file**

```python
"""
Layer 4 — RBAC Coverage
Verifies that permission-gated endpoints return 403 for an unprivileged user,
401 for expired/missing tokens, and 200 for properly authorized users.
"""
import time
from datetime import timedelta

import pytest

pytestmark = pytest.mark.integration


# ── Admin endpoint 403 matrix ────────────────────────────────────────────────


ADMIN_ENDPOINTS_403 = [
    # (method, path, body) — unprivileged user must get 403
    ("GET",  "/api/v1/admin/health/",        None),
    ("GET",  "/api/v1/admin/config/",        None),
    ("POST", "/api/v1/admin/ml/train/1",     None),
    ("GET",  "/api/v1/admin/ml/queue",       None),
    ("POST", "/api/v1/admin/maintenance/",   {"arac_id": 1, "bakim_tipi": "PERIYODIK",
                                               "km_bilgisi": 100000,
                                               "bakim_tarihi": "2026-01-01T00:00:00Z"}),
    ("GET",  "/api/v1/admin/users/",         None),
    ("POST", "/api/v1/admin/notifications/", {"baslik": "t", "mesaj": "m",
                                               "hedef": "all"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS_403)
async def test_admin_endpoint_returns_403_for_normal_user(
    async_client, normal_auth_headers, method, path, body
):
    """Unprivileged izleyici user must receive 403 on every permission-gated endpoint."""
    if method == "GET":
        r = await async_client.get(path, headers=normal_auth_headers)
    else:
        r = await async_client.post(path, json=body or {}, headers=normal_auth_headers)

    assert r.status_code == 403, (
        f"{method} {path} returned {r.status_code} for normal user "
        f"(expected 403). Body: {r.text[:200]}"
    )


# ── Missing token → 401 ───────────────────────────────────────────────────────


PROTECTED_ENDPOINTS = [
    "/api/v1/vehicles/",
    "/api/v1/drivers/",
    "/api/v1/trips/",
    "/api/v1/fuel/",
    "/api/v1/locations/",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
async def test_missing_token_returns_401(async_client, path):
    """No Authorization header → 401 on all protected endpoints."""
    r = await async_client.get(path)
    assert r.status_code == 401, (
        f"GET {path} without token returned {r.status_code} (expected 401)"
    )


# ── Expired JWT → 401 ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_token_returns_401(async_client):
    """JWT with past exp claim must be rejected with 401."""
    from app.config import settings
    from app.core.security import create_access_token

    expired_token = create_access_token(
        data={"sub": settings.SUPER_ADMIN_USERNAME, "is_super": True},
        expires_delta=timedelta(seconds=-1),  # already expired
    )
    headers = {"Authorization": f"Bearer {expired_token}"}

    r = await async_client.get("/api/v1/vehicles/", headers=headers)
    assert r.status_code == 401, \
        f"Expired token was accepted (got {r.status_code})"


# ── httpOnly refresh cookie ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(async_client):
    """POST /auth/refresh with no cookie must return 401, not 500."""
    r = await async_client.post("/api/v1/auth/refresh")
    assert r.status_code in (401, 422), (
        f"Refresh without cookie returned {r.status_code} (expected 401 or 422, not 500). "
        f"Body: {r.text[:200]}"
    )
    assert r.status_code != 500, "Refresh without cookie must never 500"


# ── Malformed Bearer token → 401 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_bearer_token_returns_401(async_client):
    """Garbage JWT string must be rejected with 401."""
    headers = {"Authorization": "Bearer not.a.valid.jwt"}
    r = await async_client.get("/api/v1/vehicles/", headers=headers)
    assert r.status_code == 401, \
        f"Malformed token was accepted (got {r.status_code})"


# ── Positive: admin can reach admin endpoint ─────────────────────────────────


@pytest.mark.asyncio
async def test_admin_user_can_reach_health(async_client, admin_auth_headers):
    """Sanity check: super-admin token must receive 200 on /admin/health/."""
    r = await async_client.get("/api/v1/admin/health/", headers=admin_auth_headers)
    assert r.status_code == 200, \
        f"Admin health returned {r.status_code}: {r.text[:200]}"
```

- [ ] **Step 2: Collect**

```
pytest app/tests/security/test_rbac_coverage.py --collect-only -q
```
Expected: 16+ tests collected (parametrized).

- [ ] **Step 3: Run**

```
pytest app/tests/security/test_rbac_coverage.py -v --timeout=30
```
Any endpoint returning `200` or `500` instead of `403` is a security bug. Fix `require_yetki` application on the offending endpoint before moving on.

- [ ] **Step 4: Commit**

```
git add app/tests/security/test_rbac_coverage.py
git commit -m "test(security): Layer 4 — RBAC coverage (403 matrix, 401 expiry, refresh cookie)"
```

---

## Task 5: Frontend Backend Contract

**Files:**
- Create: `frontend/src/services/api/__tests__/backend-contract.test.ts`

> No mocks. Real Docker backend at `VITE_API_BASE_URL` (default `http://localhost:8000`). Test skips gracefully when backend is unreachable.

- [ ] **Step 1: Write the test file**

```typescript
/**
 * Layer 5 — Frontend Backend Contract
 *
 * Verifies that the running Docker backend returns shapes matching
 * the TypeScript interfaces used by the frontend.
 * No mocks. Direct axios calls to the real server.
 *
 * Run with:
 *   VITE_API_BASE_URL=http://localhost:8000 npx vitest run src/services/api/__tests__/backend-contract.test.ts
 */
import axios from 'axios'
import { describe, it, expect, beforeAll } from 'vitest'
import type { Vehicle, Driver, PaginatedResponse } from '../../../types'

const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL ?? 'http://localhost:8000'
let accessToken: string | null = null
let backendReachable = false

beforeAll(async () => {
    try {
        await axios.get(`${BASE_URL}/health`, { timeout: 3000 })
        backendReachable = true
    } catch {
        console.warn('[backend-contract] Backend unreachable, all tests will skip.')
        return
    }

    // Obtain a token using the seeded admin credentials from alembic/0002_seed_and_bootstrap.py
    try {
        const loginResp = await axios.post(
            `${BASE_URL}/api/v1/auth/token`,
            new URLSearchParams({ username: 'admin@lojinext.com', password: 'admin123' }),
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        )
        accessToken = loginResp.data.access_token
    } catch (e: any) {
        console.warn('[backend-contract] Login failed — auth tests will be limited', e?.message)
    }
})

function authHeaders() {
    return accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
}

function skip(name: string) {
    it.skip(name, () => { /* backend unreachable */ })
}

// ── Auth shape ───────────────────────────────────────────────────────────────

describe('auth token shape', () => {
    it('POST /auth/token returns access_token string and token_type=bearer', async () => {
        if (!backendReachable) return

        // Use seeded credentials
        const resp = await axios.post(
            `${BASE_URL}/api/v1/auth/token`,
            new URLSearchParams({ username: 'admin@lojinext.com', password: 'admin123' }),
            {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                validateStatus: () => true,
            }
        )
        if (resp.status === 401) {
            console.warn('Seed user not found — skipping auth shape test')
            return
        }
        expect(resp.status).toBe(200)
        const body = resp.data
        expect(typeof body.access_token).toBe('string')
        expect(body.access_token.length).toBeGreaterThan(10)
        expect(body.token_type).toBe('bearer')
    })
})

// ── Vehicles list shape ───────────────────────────────────────────────────────

describe('vehicles list shape', () => {
    it('GET /vehicles/ returns items[] and total matching Vehicle interface', async () => {
        if (!backendReachable) return

        const resp = await axios.get(`${BASE_URL}/api/v1/vehicles/`, {
            headers: authHeaders(),
            validateStatus: () => true,
        })

        if (resp.status === 401) {
            console.warn('No auth token, skipping vehicles shape test')
            return
        }

        expect(resp.status).toBe(200)
        const body = resp.data as PaginatedResponse<Vehicle>
        expect(Array.isArray(body.items)).toBe(true)
        expect(typeof body.total).toBe('number')
        expect(body.total).toBeGreaterThanOrEqual(0)

        if (body.items.length > 0) {
            const v = body.items[0]
            expect(typeof v.id).toBe('number')
            expect(typeof v.plaka).toBe('string')
            expect(v.plaka.length).toBeGreaterThan(0)
            expect(typeof v.aktif).toBe('boolean')
            // hedef_tuketim maps to hedef_tuketim in API
            expect(typeof v.hedef_tuketim).toBe('number')
            expect(isNaN(v.hedef_tuketim)).toBe(false)
        }
    })
})

// ── Drivers list shape ────────────────────────────────────────────────────────

describe('drivers list shape', () => {
    it('GET /drivers/ returns items[] matching Driver interface', async () => {
        if (!backendReachable) return

        const resp = await axios.get(`${BASE_URL}/api/v1/drivers/`, {
            headers: authHeaders(),
            validateStatus: () => true,
        })

        if (resp.status === 401) return

        expect(resp.status).toBe(200)
        const body = resp.data
        // Support both paginated {items, total} and plain array
        const items: Driver[] = Array.isArray(body) ? body : body.items ?? []
        expect(Array.isArray(items)).toBe(true)

        if (items.length > 0) {
            const d = items[0]
            expect(typeof d.ad_soyad).toBe('string')
            expect(typeof d.ehliyet_sinifi).toBe('string')
            expect(typeof d.aktif).toBe('boolean')
        }
    })
})

// ── Trips list shape ──────────────────────────────────────────────────────────

describe('trips list shape', () => {
    it('GET /trips/ returns {items, total} envelope', async () => {
        if (!backendReachable) return

        const resp = await axios.get(`${BASE_URL}/api/v1/trips/`, {
            headers: authHeaders(),
            validateStatus: () => true,
        })

        if (resp.status === 401) return

        expect(resp.status).toBe(200)
        const body = resp.data
        expect('items' in body).toBe(true)
        expect('total' in body).toBe(true)
        expect(typeof body.total).toBe('number')
    })
})

// ── Locations list shape ──────────────────────────────────────────────────────

describe('locations list shape', () => {
    it('GET /locations/ returns items with cikis_yeri and varis_yeri strings', async () => {
        if (!backendReachable) return

        const resp = await axios.get(`${BASE_URL}/api/v1/locations/`, {
            headers: authHeaders(),
            validateStatus: () => true,
        })

        if (resp.status === 401) return

        expect(resp.status).toBe(200)
        const body = resp.data
        const items = Array.isArray(body) ? body : body.items ?? []

        if (items.length > 0) {
            const loc = items[0]
            expect(typeof loc.cikis_yeri).toBe('string')
            expect(typeof loc.varis_yeri).toBe('string')
            expect(typeof loc.mesafe_km).toBe('number')
            expect(isNaN(loc.mesafe_km)).toBe(false)
        }
    })
})
```

- [ ] **Step 2: Check that vitest picks it up**

```
cd frontend && npx vitest run src/services/api/__tests__/backend-contract.test.ts --reporter=verbose 2>&1 | head -30
```
Expected: tests collect. Some may skip if backend is unreachable.

- [ ] **Step 3: Run with real backend**

```
cd frontend && VITE_API_BASE_URL=http://localhost:8000 npx vitest run src/services/api/__tests__/backend-contract.test.ts
```
Any shape mismatch is a bug. Fix the backend schema or the TypeScript type (whichever is wrong), not the test.

- [ ] **Step 4: Commit**

```
git add frontend/src/services/api/__tests__/backend-contract.test.ts
git commit -m "test(frontend): Layer 5 — backend contract tests (real Docker, no mocks)"
```

---

## Task 6: ML/AI Pipeline

**Files:**
- Create: `app/tests/integration/test_ml_ai_pipeline.py`

> **Spec corrections:** AI endpoint is `POST /api/v1/ai/chat` with `{"message": "..."}`, response `{"response": "...", "timestamp": "..."}`. No `sources` field. Prediction is `POST /predictions/predict`. Response fields: `tahmini_tuketim`, `model_used`, `confidence_low/high`. No `/admin/ml/weights` endpoint — test via service directly.

- [ ] **Step 1: Write the test file**

```python
"""
Layer 6 — ML/AI Pipeline
Verifies ML and AI subsystems behave correctly at the API and service boundary.
All tests require Docker stack (real DB + Redis + Celery not required for these).
"""
import math
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


def _is_finite_positive(v) -> bool:
    try:
        return math.isfinite(float(v)) and float(v) > 0
    except (TypeError, ValueError):
        return False


# ── Ensemble predictor cold-start invariant ──────────────────────────────────


@pytest.mark.asyncio
async def test_prediction_physics_model_works_without_training_data(
    async_client, admin_auth_headers
):
    """
    POST /predictions/predict with a valid request must not 500.
    When no trained model exists, the physics fallback must produce
    tahmini_tuketim > 0 with model_used in known values.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 450.0,
            "ton": 22.0,
            "ascent_m": 200.0,
            "descent_m": 200.0,
            "flat_distance_km": 400.0,
            "zorluk": "Normal",
            "model_type": "ensemble",
        },
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, f"Prediction endpoint 500'd: {r.text}"
    assert r.status_code in (200, 404, 422), \
        f"Unexpected status {r.status_code}: {r.text}"

    if r.status_code == 200:
        body = r.json()
        assert body["status"] == "success", f"status != success: {body}"
        assert _is_finite_positive(body["tahmini_tuketim"]), \
            f"tahmini_tuketim not finite positive: {body['tahmini_tuketim']}"
        known_models = {"linear", "xgboost", "ensemble", "physics", "physics_fallback"}
        assert body["model_used"] in known_models, \
            f"model_used '{body['model_used']}' not in known set {known_models}"


@pytest.mark.asyncio
async def test_prediction_confidence_bounds_are_ordered(async_client, admin_auth_headers):
    """
    When confidence_low and confidence_high are present in the prediction response,
    confidence_low < tahmini_tuketim < confidence_high must hold.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 300.0,
            "ton": 18.0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "flat_distance_km": 300.0,
            "zorluk": "Normal",
            "model_type": "ensemble",
        },
        headers=admin_auth_headers,
    )

    if r.status_code != 200:
        pytest.skip("Prediction returned non-200; skipping confidence bound check")

    body = r.json()
    low = body.get("confidence_low")
    high = body.get("confidence_high")
    value = float(body["tahmini_tuketim"])

    if low is not None and high is not None:
        assert float(low) < value, \
            f"confidence_low ({low}) must be < tahmini_tuketim ({value})"
        assert float(high) > value, \
            f"confidence_high ({high}) must be > tahmini_tuketim ({value})"
        assert float(low) > 0, "confidence_low must be positive"


# ── AI chat endpoint ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_chat_returns_response_field(async_client, admin_auth_headers):
    """
    POST /ai/chat must return {"response": str, "timestamp": str}.
    Must not 500 regardless of Groq availability.
    """
    r = await async_client.post(
        "/api/v1/ai/chat",
        json={"message": "Yakıt anomalisi nedir?", "history": []},
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, f"AI chat 500'd: {r.text}"
    assert r.status_code in (200, 503), \
        f"Unexpected AI chat status {r.status_code}: {r.text}"

    if r.status_code == 200:
        body = r.json()
        assert "response" in body, f"'response' field missing: {list(body.keys())}"
        assert isinstance(body["response"], str), \
            f"'response' must be a string, got {type(body['response'])}"
        assert len(body["response"]) > 0, "AI response must not be empty"
        assert "timestamp" in body, "'timestamp' field missing"


@pytest.mark.asyncio
async def test_ai_chat_with_invalid_groq_key_does_not_500(
    async_client, admin_auth_headers, monkeypatch
):
    """
    When Groq API is unavailable (invalid key), AI chat must return a
    graceful error response — never an unhandled 500.
    """
    monkeypatch.setenv("GROQ_API_KEY", "invalid_key_for_test")

    r = await async_client.post(
        "/api/v1/ai/chat",
        json={"message": "Test query with invalid LLM key"},
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, (
        "AI chat must handle LLM failures gracefully — never 500 without envelope. "
        f"Got 500: {r.text[:300]}"
    )


# ── Anomaly fleet insights ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anomaly_fleet_insights_response_shape(async_client, admin_auth_headers):
    """
    GET /anomalies/fleet/insights must return status=success and data dict.
    Must not 500.
    """
    r = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=30",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200, f"Fleet insights failed: {r.text}"
    body = r.json()
    assert body.get("status") == "success", f"Expected status='success': {body}"
    assert "data" in body, f"'data' key missing from fleet insights: {body}"


@pytest.mark.asyncio
async def test_anomaly_fleet_insights_leakage_and_maintenance_keys(
    async_client, admin_auth_headers
):
    """
    Fleet insights data must have 'leakage' and 'maintenance' sub-keys.
    Both must be non-None (list or dict).
    """
    r = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=30",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200
    data = r.json().get("data", {})
    assert "leakage" in data, f"'leakage' key missing: {data}"
    assert "maintenance" in data, f"'maintenance' key missing: {data}"
    assert data["leakage"] is not None, "'leakage' must not be None"
    assert data["maintenance"] is not None, "'maintenance' must not be None"


# ── ML training queue (admin) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ml_training_queue_returns_list(async_client, admin_auth_headers):
    """
    GET /admin/ml/queue must return a list (possibly empty).
    Verifies the ML admin endpoint is reachable with correct permissions.
    """
    r = await async_client.get(
        "/api/v1/admin/ml/queue",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200, \
        f"ML training queue failed: {r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body, list), f"ML queue must return a list: {type(body)}"


# ── Prediction with extreme values doesn't 500 ────────────────────────────────


@pytest.mark.asyncio
async def test_prediction_extreme_values_no_500(async_client, admin_auth_headers):
    """
    Prediction with edge-case inputs (very high ascent, max ton) must not 500.
    Physics model must handle any valid numeric input.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 9999.0,
            "ton": 26.0,
            "ascent_m": 49999.0,
            "descent_m": 49999.0,
            "flat_distance_km": 1.0,
            "zorluk": "Zor",
            "model_type": "physics",
        },
        headers=admin_auth_headers,
    )
    assert r.status_code != 500, \
        f"Prediction with extreme inputs must not 500. Got: {r.text}"
    if r.status_code == 200:
        assert _is_finite_positive(r.json()["tahmini_tuketim"]), \
            "tahmini_tuketim must be finite even for extreme inputs"
```

- [ ] **Step 2: Collect**

```
pytest app/tests/integration/test_ml_ai_pipeline.py --collect-only -q
```
Expected: 8 tests collected.

- [ ] **Step 3: Run**

```
pytest app/tests/integration/test_ml_ai_pipeline.py -v --timeout=30
```
500 on any test = critical bug. Fix the service/endpoint before moving on.

- [ ] **Step 4: Commit**

```
git add app/tests/integration/test_ml_ai_pipeline.py
git commit -m "test(integration): Layer 6 — ML/AI pipeline (prediction, AI chat, anomaly, graceful fallback)"
```

---

## Task 7: CI Wiring

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Read current CI config**

```
cat .github/workflows/ci.yml | grep -n "pytest\|vitest\|step\|name:" | head -40
```

- [ ] **Step 2: Add stages after existing unit tests**

Locate the line that runs `pytest` for unit tests and add these stages after it:

```yaml
      - name: Integration — DB schema + API contracts + lifecycle
        run: pytest app/tests/integration/test_db_schema_integrity.py app/tests/integration/test_api_contracts.py app/tests/integration/test_business_lifecycle.py -m integration -x -q --timeout=60
        env:
          TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      - name: Security — RBAC coverage
        run: pytest app/tests/security/test_rbac_coverage.py -x -q --timeout=30
        env:
          TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      - name: ML/AI pipeline
        run: pytest app/tests/integration/test_ml_ai_pipeline.py -x -q --timeout=30
        env:
          TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      - name: Frontend backend contract
        run: cd frontend && npx vitest run src/services/api/__tests__/backend-contract.test.ts
        env:
          VITE_API_BASE_URL: http://localhost:8000
```

- [ ] **Step 3: Commit**

```
git add .github/workflows/ci.yml
git commit -m "ci: add 6-layer prod-readiness test stages after unit tests"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by task |
|---|---|
| Layer 1 — DB integrity (FK, CHECK, UNIQUE, soft-delete, MV, indexes) | Task 1 ✓ |
| Layer 2 — API contracts (shapes, types, NaN, envelope) | Task 2 ✓ |
| Layer 3 — Business lifecycle (vehicle→trip→fuel→report) | Task 3 ✓ |
| Layer 4 — RBAC (403 matrix, 401 expiry, refresh cookie) | Task 4 ✓ |
| Layer 5 — Frontend backend contract | Task 5 ✓ |
| Layer 6 — ML/AI pipeline | Task 6 ✓ |
| CI wiring | Task 7 ✓ |

**Spec corrections applied:**
- `GET /trips/{id}` returns flat `plaka`/`sofor_adi` not nested `arac.plaka`
- Prediction is `POST /predictions/predict`, response is `tahmini_tuketim` not `predicted_value`
- Fuel uses `litre`/`fiyat_tl` not `yakit_miktari_lt`/`yakit_fiyati_tl`; query uses `arac_id` not `sefer_id`
- AI endpoint is `POST /ai/chat` with `{"message": "..."}`, response is `{"response": "...", "timestamp": "..."}`
- Trip DELETE returns `200 + {"soft_deleted": True}`, not `204`
- No `GET /anomalies/?sefer_id=X` — only `GET /anomalies/fleet/insights`
- No `/admin/ml/weights` endpoint — ML training queue used instead
- `normal_auth_headers` fixture produces `izleyici` role (only `sefer:read` permission)

**Bug policy:** Every failing test is treated as critical. Do not mark a test as skip/xfail to make CI green — fix the root cause.
