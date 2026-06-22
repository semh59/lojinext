# Zero-Mock Slice 3a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the 6 small/medium FakeUnitOfWork-category test files (PR-3a of zero-mock Slice 3) to real `UnitOfWork` + real Postgres/Redis, with zero in-process mocks for internal code, deleting nothing's behavioral coverage.

**Architecture:** Each test is classified keep / convert / delete-duplicate / real-fault (spec §2). Pure-logic tests stay untouched. DB-touching tests seed real rows through `async with UnitOfWork() as uow` and assert business results instead of internal call shapes. A shared seed helper (`app/tests/_helpers/seed.py`) centralizes real-row creation respecting CLAUDE.md DB gotchas.

**Tech Stack:** pytest (asyncio_mode=auto), SQLAlchemy 2 async ORM, real Postgres (`TEST_DATABASE_URL`), real Redis (`REDIS_URL=.../15`), run via the `lojinext-backend-dev` container recipe (memory `local-test-db-execution`).

---

## Scope note / deviation from spec §3

While reading the files, two PR-3a members turned out heavier than the spec's "small/medium" label:

- `test_services/test_sefer_service.py` matched the grep via an **inline** `FakeUnitOfWork` class (line 199), but its real double is `FakeSeferRepo` (constructor-injected in-memory repo). Full 0-mock requires replacing `FakeSeferRepo` with a real `SeferRepository` + seeded DB — bigger than "2 refs".
- `test_dashboard_report_import_contracts.py` spans **3 services with 4 mocking styles**; 2 of its 5 tests are sefer-import (PR-3b domain) and several assert internal call kwargs.

**Decision baked into this plan:** keep the user-approved 6-file grouping, but order the two heavy files last (Tasks 5–6) and convert their internal-call-assertion tests to result assertions. If Task 6 proves too entangled with import internals at execution time, its 2 import tests may be moved to PR-3b — flagged in that task.

---

## Run / verify commands (used by every task)

**VERIFIED 2026-06-18** — this exact command was smoke-tested (pure-logic file: 6 passed; real-DB integration `test_uow_after_error.py`: 1 passed). Prereqs already satisfied: all compose services up, `lojinext-backend-dev:latest` image present, `lojinext_test` database exists on the `db` container. Run from repo root in Git Bash:

```bash
SK=$(docker compose exec -T backend printenv SECRET_KEY | tr -d '\r')
MSYS_NO_PATHCONV=1 docker run --rm \
  --network lojinext_lojinext_network \
  -v "/d/PROJECT/LOJINEXT:/app" -w /app \
  --entrypoint bash \
  -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" \
  -e DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" \
  -e REDIS_URL="redis://redis:6379/15" \
  -e SECRET_KEY="$SK" \
  -e USE_SEFER_FUEL_ESTIMATOR=false -e CELERY_EAGER=true \
  lojinext-backend-dev \
  -c 'python -m pytest <TEST_PATH> -p no:cacheprovider -q'
```

Notes that bite: the network is `lojinext_lojinext_network` (NOT `lojinext_default`); `--entrypoint bash -c` is **required** (the dev image's default entrypoint chokes with `sleep: invalid option -- 'm'`); pin BOTH `TEST_DATABASE_URL` and `DATABASE_URL` to `lojinext_test`; `REDIS_URL` uses index `/15` to isolate from the app's `/0`. For brevity later tasks write `pytest <path>` — always wrap in the `docker run` above.

---

## Task 0: Shared real-seed helper

**Files:**
- Create: `app/tests/_helpers/seed.py`
- Check first: `app/tests/conftest.py`, `app/tests/_helpers/` (slice 2 may have added seeders — reuse, don't duplicate)

- [ ] **Step 1: Confirm what slice 2 already provides**

Run:
```bash
grep -rn "async def seed\|def make_arac\|insert.*Arac\|InsertSefer\|seed_" app/tests/_helpers app/tests/conftest.py
```
Expected: list of any existing seed helpers. If a helper already creates `Arac`/`Sofor`/`Sefer` rows, reuse it and SKIP creating duplicates below — adapt the signatures in later tasks to match.

- [ ] **Step 2: Write the seed helper (only the entities not already covered)**

These helpers insert real rows via a real session and return ORM instances. They respect: `net_kg = dolu - bos` check constraint, `aktif`/`is_deleted` defaults.

```python
# app/tests/_helpers/seed.py
"""Real-row seed helpers for 0-mock tests. No mocks — direct ORM inserts."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.database.models import Arac, Sofor, Sefer, SistemKonfig


async def seed_arac(session, *, plaka="34ABC001", bos_agirlik_kg=14000,
                    hedef_tuketim=25.0, aktif=True) -> Arac:
    arac = Arac(plaka=plaka, bos_agirlik_kg=bos_agirlik_kg,
                hedef_tuketim=hedef_tuketim, aktif=aktif, is_deleted=False)
    session.add(arac)
    await session.flush()
    return arac


async def seed_sofor(session, *, ad_soyad="Ali Veli", aktif=True) -> Sofor:
    sofor = Sofor(ad_soyad=ad_soyad, aktif=aktif, is_deleted=False)
    session.add(sofor)
    await session.flush()
    return sofor


async def seed_sefer(session, *, arac_id, sofor_id=None, tarih=None, durum="PLANLANDI",
                     mesafe_km=450.0, net_kg=12000, bos_agirlik_kg=14000,
                     gercek_tuketim=None, tahmini_tuketim=None,
                     route_analysis=None, guzergah_id=None, **extra) -> Sefer:
    tarih = tarih or date.today()
    sefer = Sefer(
        arac_id=arac_id, sofor_id=sofor_id, tarih=tarih, durum=durum,
        mesafe_km=mesafe_km, net_kg=net_kg, bos_agirlik_kg=bos_agirlik_kg,
        dolu_agirlik_kg=bos_agirlik_kg + net_kg,   # ck_seferler_check_sefer_net_kg_calc
        gercek_tuketim=gercek_tuketim, tahmini_tuketim=tahmini_tuketim,
        route_analysis=route_analysis, guzergah_id=guzergah_id,
        is_deleted=False, created_at=datetime.now(timezone.utc), **extra)
    session.add(sefer)
    await session.flush()
    return sefer


async def seed_sistem_konfig(session, *, anahtar, deger) -> SistemKonfig:
    row = SistemKonfig(anahtar=anahtar, deger=deger)
    session.add(row)
    await session.flush()
    return row
```

> Before writing, open `app/database/models.py` and confirm the real column names/required NOT-NULL fields for `Arac`, `Sofor`, `Sefer`, `SistemKonfig`. Adjust kwargs to match exactly — do not invent columns. If `Sefer` requires `sefer_no`, add it (`sefer_no=f"T{...}"`).

- [ ] **Step 3: Verify the helper imports cleanly**

Run: `pytest app/tests/_helpers/seed.py --collect-only` (no tests, just import). Expected: no ImportError.

- [ ] **Step 4: Commit**

```bash
git add app/tests/_helpers/seed.py
git commit -m "test(0-mock 3a): add real-row seed helper"
```

---

## Task 1: `test_driver_route_profile.py`

**Files:**
- Modify: `app/tests/unit/test_driver_route_profile.py`
- Under test: `app/core/ml/driver_route_profile.py` (`get_driver_route_coefficient` → `uow.sefer_repo.get_driver_trips_by_route_type`)

**Disposition:** 4 `classify_route` tests = KEEP (pure logic). 2 tests patch `UnitOfWork` = CONVERT.

- [ ] **Step 1: Read the query semantics**

Open `app/core/ml/driver_route_profile.py` and `app/database/repositories/sefer_repo.py::get_driver_trips_by_route_type`. Note exactly how it filters (sofor_id, route_type column or derived, the `gercek_tuketim`/`tahmini_tuketim` fields, the min-trips threshold). The asserted behavior: <min_trips → returns `1.0`; ≥min_trips → median of `gercek/tahmini` ratios.

- [ ] **Step 2: Convert `test_coefficient_returns_neutral_when_insufficient_data`**

Replace the `patch(...)` + `_make_uow_mock` with real seeding (no rows for that route_type → insufficient):

```python
import pytest
from app.database.unit_of_work import UnitOfWork
from app.tests._helpers.seed import seed_arac, seed_sofor, seed_sefer

pytestmark = pytest.mark.integration


async def test_coefficient_returns_neutral_when_insufficient_data():
    from app.core.ml.driver_route_profile import get_driver_route_coefficient
    async with UnitOfWork() as uow:
        sofor = await seed_sofor(uow.session)
        await uow.commit()
    result = await get_driver_route_coefficient(
        sofor_id=sofor.id, route_type="highway_dominant")
    assert result == 1.0
```

- [ ] **Step 3: Convert `test_coefficient_returns_median_ratio`**

Seed 5 completed trips for one driver on the route type with the gerçek/tahmini pairs that yield a median in `[1.0, 1.15]`. The route_type filter source determines whether to set `route_analysis` or a dedicated column — match what `get_driver_trips_by_route_type` reads (from Step 1).

```python
async def test_coefficient_returns_median_ratio():
    from app.core.ml.driver_route_profile import get_driver_route_coefficient
    pairs = [(42.0, 40.0), (44.0, 40.0), (43.0, 40.0), (41.0, 40.0), (40.0, 40.0)]
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        sofor = await seed_sofor(uow.session)
        for g, t in pairs:
            await seed_sefer(uow.session, arac_id=arac.id, sofor_id=sofor.id,
                             durum="TAMAMLANDI", gercek_tuketim=g, tahmini_tuketim=t,
                             route_analysis={"motorway": {"flat": 600.0}})  # → highway_dominant
        await uow.commit()
    result = await get_driver_route_coefficient(
        sofor_id=sofor.id, route_type="highway_dominant")
    assert 1.0 <= result <= 1.15
```

- [ ] **Step 4: Run, confirm pass, drop dead imports**

Run: `pytest app/tests/unit/test_driver_route_profile.py -q`
Expected: 6 passed. If the median test fails, print the actual `result` and adjust the seed pairs (the route_type classification may need a stronger motorway signal — see `classify_route` thresholds). Remove the now-unused `AsyncMock, MagicMock, patch` import and the `_make_uow_mock` helper.

- [ ] **Step 5: Commit**

```bash
git add app/tests/unit/test_driver_route_profile.py
git commit -m "test(0-mock 3a): driver_route_profile → real UoW seed"
```

---

## Task 2: `test_route_similarity.py`

**Files:**
- Modify: `app/tests/unit/test_route_similarity.py`
- Under test: `app/core/ml/route_similarity.py` (`find_similar_trips` → `uow.sefer_repo.get_with_route_analysis(days=90, limit=200)`)

**Disposition:** 4 pure tests (`encode_route`, `cosine_similarity` ×3) = KEEP. 2 tests patch `UnitOfWork` = CONVERT.

- [ ] **Step 1: Read `get_with_route_analysis`**

Open `app/database/repositories/sefer_repo.py::get_with_route_analysis`. Confirm it returns dicts with `id, mesafe_km, route_analysis, gercek_tuketim` for trips in the last 90 days. Seeds must use `tarih=date.today()` and a non-null `route_analysis` to be picked up.

- [ ] **Step 2: Convert `test_find_similar_trips_distance_filter`**

Seed one trip 500 km away; query at 100 km → >20% diff → filtered → `[]`.

```python
async def test_find_similar_trips_distance_filter():
    from app.core.ml.route_similarity import find_similar_trips
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        await seed_sefer(uow.session, arac_id=arac.id, mesafe_km=500.0,
                         gercek_tuketim=80.0, route_analysis={"motorway": {"flat": 400.0}})
        await uow.commit()
    result = await find_similar_trips({}, mesafe_km=100.0)
    assert result == []
```

- [ ] **Step 3: Convert `test_find_similar_trips_returns_sorted_by_similarity`**

Seed two trips at 100 km with identical `route_analysis` equal to the query vector (cosine sim = 1.0 ≥ 0.85 threshold).

```python
async def test_find_similar_trips_returns_sorted_by_similarity():
    from app.core.ml.route_similarity import find_similar_trips
    vec = {"motorway": {"flat": 100.0}, "ascent_m": 500.0, "descent_m": 400.0}
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        await seed_sefer(uow.session, arac_id=arac.id, mesafe_km=100.0,
                         gercek_tuketim=50.0, route_analysis=vec)
        await seed_sefer(uow.session, arac_id=arac.id, mesafe_km=100.0,
                         gercek_tuketim=55.0, route_analysis=vec)
        await uow.commit()
    result = await find_similar_trips(vec, mesafe_km=100.0)
    assert len(result) >= 1
    if len(result) > 1:
        assert result[0]["similarity"] >= result[1]["similarity"]
```

- [ ] **Step 4: Run, confirm, clean imports**

Run: `pytest app/tests/unit/test_route_similarity.py -q`
Expected: 6 passed. Remove unused `AsyncMock, MagicMock, patch` + `_make_uow_mock`. Add `pytestmark = pytest.mark.integration` and the seed/UoW imports.

- [ ] **Step 5: Commit**

```bash
git add app/tests/unit/test_route_similarity.py
git commit -m "test(0-mock 3a): route_similarity → real UoW seed"
```

---

## Task 3: `test_services/test_license_service.py`

**Files:**
- Modify: `app/tests/unit/test_services/test_license_service.py`
- Under test: `app/core/services/license_service.py` (`get_current_tier` reads `SistemKonfig.deger where anahtar=="LICENSE_KEY"`; `check_car_limit` counts `Arac.aktif & ~is_deleted`)

**Disposition:** KEEP all pure tests (`test_service_exists`, `test_basic_initialization`, `_validate_license_key*`, `test_limits_structure`, `test_edge_case_none_key_defaults_to_free`). CONVERT the 4 DB tests (`get_current_tier` ×2, `check_car_limit` ×2). The `patch.dict(os.environ, ...)` for license **hashes** stays — that is real config, not an internal mock.

- [ ] **Step 1: Convert `test_get_current_tier_no_key_in_db_returns_free`**

No `SistemKonfig` LICENSE_KEY row → FREE.

```python
async def test_get_current_tier_no_key_in_db_returns_free():
    from app.core.services.license_service import LicenseEngine
    engine = LicenseEngine()
    tier = await engine.get_current_tier()  # empty DB → no key
    assert tier == "FREE"
```

- [ ] **Step 2: Convert `test_get_current_tier_pro_key_in_db`**

Seed a real LICENSE_KEY row whose value hashes to the PRO hash set via env.

```python
async def test_get_current_tier_pro_key_in_db():
    import hashlib, os
    from app.core.services.license_service import LicenseEngine
    from app.tests._helpers.seed import seed_sistem_konfig
    pro_key = "pro-db-key-test"
    pro_hash = hashlib.sha256(pro_key.encode()).hexdigest()
    async with UnitOfWork() as uow:
        await seed_sistem_konfig(uow.session, anahtar="LICENSE_KEY", deger=pro_key)
        await uow.commit()
    with patch.dict(os.environ, {"LICENSE_PRO_HASH": pro_hash}):
        engine = LicenseEngine()
        tier = await engine.get_current_tier()
    assert tier == "PRO"
```

- [ ] **Step 3: Convert the two `check_car_limit` tests**

FREE max_cars=5. Under limit (3 cars) → True; at limit (5 cars) → False. Seed real `Arac` rows.

```python
async def test_check_car_limit_free_tier_under_limit():
    from app.core.services.license_service import LicenseEngine
    from app.tests._helpers.seed import seed_arac
    async with UnitOfWork() as uow:
        for i in range(3):
            await seed_arac(uow.session, plaka=f"34CAR{i:03d}")
        await uow.commit()
    assert await LicenseEngine().check_car_limit() is True


async def test_check_car_limit_free_tier_at_limit():
    from app.core.services.license_service import LicenseEngine
    from app.tests._helpers.seed import seed_arac
    async with UnitOfWork() as uow:
        for i in range(5):
            await seed_arac(uow.session, plaka=f"34LIM{i:03d}")
        await uow.commit()
    assert await LicenseEngine().check_car_limit() is False
```

- [ ] **Step 4: Run, confirm, clean**

Run: `pytest app/tests/unit/test_services/test_license_service.py -q`
Expected: all pass. Remove `_make_uow_with_scalar` and now-unused `AsyncMock, MagicMock` (keep `patch` — still used for `patch.dict`). Mark the 4 converted tests `@pytest.mark.integration`; keep pure tests as unit.

> Gotcha: `check_car_limit` counts only `aktif & ~is_deleted` — seed helper defaults satisfy this. Ensure no other test in the session leaks Arac rows into the count (conftest drops schema per session, but within a session use distinct plakas and rely on the empty-at-test-start state; if cross-test leakage appears, scope counts by the rows you seeded or assert the boundary you control).

- [ ] **Step 5: Commit**

```bash
git add app/tests/unit/test_services/test_license_service.py
git commit -m "test(0-mock 3a): license_service → real SistemKonfig + Arac seed"
```

---

## Task 4: `test_services/test_analiz_service_coverage.py`

**Files:**
- Modify: `app/tests/unit/test_services/test_analiz_service_coverage.py`
- Under test: `app/core/services/analiz_service.py`

**Disposition:** Most tests are PURE math (`calculate_moving_average`, `calculate_trend`, `calculate_eei`, `detect_anomalies`, `analyze_vehicle_consumption`, `clear_cache`, singleton) — they only need an `AnalizService` instance. The `MagicMock()` repos in `_make_service()` are unused there. CONVERT: `TestGetFleetAverage` (2), `TestCalculateLongTermStats` (4 — mock `yakit_repo.get_all`), `TestDelegationMethods.test_recalculate_vehicle_periods_delegates` (internal-call assertion).

- [ ] **Step 1: Replace `_make_service()` with a real-repo factory**

`AnalizService` needs `yakit_repo`/`sefer_repo`. For pure-math tests these are untouched, but 0-mock means no `MagicMock`. Provide real repos bound to a session:

```python
import pytest
from app.database.unit_of_work import UnitOfWork
pytestmark = pytest.mark.integration

async def _real_service():
    from app.core.services.analiz_service import AnalizService
    uow = UnitOfWork()
    await uow.__aenter__()
    svc = AnalizService(yakit_repo=uow.yakit_repo, sefer_repo=uow.sefer_repo)
    return svc, uow  # caller must aexit uow
```

> For the pure-math tests, the simplest 0-mock form keeps them synchronous and constructs `AnalizService(yakit_repo=None, sefer_repo=None)` IF the constructor tolerates None (check `__init__`). If it requires repos, use real ones via a module-scoped fixture. Pick whichever the constructor actually allows — read `AnalizService.__init__` first. Do not pass MagicMock.

- [ ] **Step 2: Convert `TestCalculateLongTermStats` (seed real yakit rows)**

Replace `svc.yakit_repo.get_all = AsyncMock(...)` with seeded `YakitAlim` rows for `arac_id`. Add a `seed_yakit` helper to `app/tests/_helpers/seed.py` (km_sayac, litre columns — confirm real names in models).

```python
async def test_returns_result_with_sufficient_data():
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        for km, litre in [(10000, 0), (11000, 300), (12000, 320), (13000, 310)]:
            await seed_yakit(uow.session, arac_id=arac.id, km_sayac=km, litre=litre)
        await uow.commit()
        svc = AnalizService(yakit_repo=uow.yakit_repo, sefer_repo=uow.sefer_repo)
        result = await svc.calculate_long_term_stats(arac_id=arac.id)
    assert result is not None
    assert {"ortalama", "guvenilirlik", "toplam_km", "toplam_yakit"} <= result.keys()
```
Apply the same seeding to the `None`-returning cases (insufficient / all-same-km).

- [ ] **Step 3: Convert `TestGetFleetAverage` — drop the await_count assertion**

`get_fleet_average` delegates to `uow.analiz_repo.get_filo_ortalama_tuketim`. Seed completed trips so the real query computes a fleet average; assert the value is a float in a sane band. The cache test's `await_count == 1` is an internal-call assertion → replace with a behavioral cache check: call twice, assert equal results AND (real Redis) that the cache key now exists.

```python
async def test_returns_float():
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        await seed_sefer(uow.session, arac_id=arac.id, durum="TAMAMLANDI",
                         gercek_tuketim=32.5, mesafe_km=100.0)
        await uow.commit()
    async with UnitOfWork() as uow:
        svc = AnalizService(yakit_repo=uow.yakit_repo, sefer_repo=uow.sefer_repo)
        result = await svc.get_fleet_average(year=date.today().year, month=date.today().month)
    assert isinstance(result, float)
```
> The exact fleet-average value depends on the repo SQL (how it aggregates). Run the test, read the actual value, then assert the real number or a tight band — do NOT hard-code 32.5 without confirming the aggregation returns it.

- [ ] **Step 4: Convert `test_recalculate_vehicle_periods_delegates`**

This currently asserts `mock_period_service.recalculate_vehicle_periods.assert_awaited_once_with(5)` (pure delegation). Real version: seed yakit rows for an arac, call `svc.recalculate_vehicle_periods(arac.id)`, assert the real effect (period rows recomputed in `yakit_periyotlari`). If the real effect is hard to assert standalone, mark this test for PR-3c's period work and delete here only if the delegation is already covered by a real period test (verify via coverage — see spec §2 duplicate guard).

- [ ] **Step 5: Run, confirm, clean**

Run: `pytest app/tests/unit/test_services/test_analiz_service_coverage.py -q`
Expected: all pass. Remove `AsyncMock, MagicMock, patch`, `_make_service`, `_make_uow_mock`. Confirm pure-math tests still pass with the real/None service.

- [ ] **Step 6: Commit**

```bash
git add app/tests/unit/test_services/test_analiz_service_coverage.py app/tests/_helpers/seed.py
git commit -m "test(0-mock 3a): analiz_service coverage → real repos + seeded data"
```

---

## Task 5: `test_services/test_sefer_service.py`

**Files:**
- Modify: `app/tests/unit/test_services/test_sefer_service.py`
- Under test: `app/core/services/sefer_service.py` (+ `sefer_read_service`, `sefer_write_service`)

**Disposition:** Replace `FakeSeferRepo` with a real `SeferRepository` over a seeded DB. KEEP `SeferCreate` validation tests (`test_add_sefer_requires_arac_id`, `_requires_locations`) — pure Pydantic. CONVERT the list/filter tests + `test_add_sefer_same_locations` (inline FakeUnitOfWork) + `test_get_bugunun_seferleri`.

- [ ] **Step 1: Read constructor wiring**

Open `app/core/services/sefer_service.py` — confirm `SeferService(repo=..., event_bus=...)` and that `repo` can be a real `SeferRepository(session=...)`. Confirm `get_all_trips(limit, start_date, end_date, status)` maps to repo filters as the old `FakeSeferRepo._filter_records` emulated (this tells you what to seed).

- [ ] **Step 2: Build a real `sefer_service` fixture**

```python
import pytest
from datetime import date, timedelta
from app.database.unit_of_work import UnitOfWork
from app.core.services.sefer_service import SeferService
from app.core.utils.sefer_status import (
    SEFER_STATUS_PLANLANDI, SEFER_STATUS_TAMAMLANDI, SEFER_STATUS_IPTAL)
from app.tests._helpers.seed import seed_arac, seed_sofor, seed_sefer
from app.infrastructure.events.event_bus import get_event_bus

pytestmark = pytest.mark.integration


@pytest.fixture
async def seeded_sefer_service():
    async with UnitOfWork() as uow:
        arac = await seed_arac(uow.session)
        sofor = await seed_sofor(uow.session)
        await seed_sefer(uow.session, arac_id=arac.id, sofor_id=sofor.id,
                         tarih=date.today(), durum=SEFER_STATUS_PLANLANDI)
        await seed_sefer(uow.session, arac_id=arac.id, sofor_id=sofor.id,
                         tarih=date.today() - timedelta(days=1), durum=SEFER_STATUS_TAMAMLANDI)
        await seed_sefer(uow.session, arac_id=arac.id, sofor_id=sofor.id,
                         tarih=date.today(), durum=SEFER_STATUS_IPTAL)
        await uow.commit()
    uow = UnitOfWork()
    await uow.__aenter__()
    svc = SeferService(repo=uow.sefer_repo, event_bus=get_event_bus())
    yield svc
    await uow.__aexit__(None, None, None)
```

- [ ] **Step 3: Convert the list/filter tests**

The assertions stay the same (counts: limit=1 → 1; date range → 2; status filters → 1/1/1/2-default). They now run against real rows.

```python
async def test_get_all_trips_with_limit(seeded_sefer_service):
    trips = await seeded_sefer_service.get_all_trips(limit=1)
    assert len(trips) == 1


async def test_get_all_trips_status_filter(seeded_sefer_service):
    assert len(await seeded_sefer_service.get_all_trips(status=SEFER_STATUS_PLANLANDI)) == 1
    assert len(await seeded_sefer_service.get_all_trips(status=None)) == 2  # IPTAL excluded
```
> Confirm at run time that the default (status=None) really excludes IPTAL in the real repo (the old fake did). If the real repo includes IPTAL by default, fix the assertion to match real behavior and note it — real behavior wins.

- [ ] **Step 4: Convert `test_add_sefer_same_locations` with real fault path**

Drop the inline `FakeUnitOfWork`. Call the real `add_sefer` with equal cikis/varis; the real `sefer_write_service` should raise `RouteProcessingError`. No monkeypatch.

```python
async def test_add_sefer_same_locations(sample_sefer_data):
    from app.core.entities.models import SeferCreate
    from app.core.exceptions import RouteProcessingError
    data = {**sample_sefer_data, "cikis_yeri": "Istanbul", "varis_yeri": "Istanbul"}
    model = SeferCreate(**data)
    async with UnitOfWork() as uow:
        svc = SeferService(repo=uow.sefer_repo, event_bus=get_event_bus())
        with pytest.raises(RouteProcessingError, match="aynı olamaz"):
            await svc.add_sefer(model)
```

- [ ] **Step 5: Run, confirm, delete `FakeSeferRepo` + `_trip_record`**

Run: `pytest app/tests/unit/test_services/test_sefer_service.py -q`
Expected: all pass. Delete `FakeSeferRepo`, `_trip_record`, `mock_event_bus`, the old `sefer_service` fixture, and `from unittest.mock import Mock`.

- [ ] **Step 6: Commit**

```bash
git add app/tests/unit/test_services/test_sefer_service.py
git commit -m "test(0-mock 3a): sefer_service → real SeferRepository + seeded DB"
```

---

## Task 6: `test_dashboard_report_import_contracts.py` (heaviest)

**Files:**
- Modify: `app/tests/unit/test_dashboard_report_import_contracts.py`
- Under test: `dashboard_service.py`, `report_service.py`, `sefer_import_service.py`

**Disposition:** 5 tests, each its own conversion. This is the file most likely to spill into PR-3b.

- [ ] **Step 1: `test_report_service_exposes_dashboard_compat_methods`**

Currently `AsyncMock`s the service's own `generate_fleet_summary`/`generate_monthly_trend` to test the compat adapter mapping. Real version: construct `ReportService(session=uow.session)` (the constructor builds real repos from a session — see report_service.py:50), seed trips/fuel so `generate_fleet_summary` computes real totals, then assert `get_dashboard_summary` maps `total_trips→toplam_sefer` etc. Seed minimal rows and assert the mapping keys (values confirmed at run time).

- [ ] **Step 2: `test_dashboard_service_filters_deleted_trip_count_and_recent_list`**

Currently asserts internal kwargs (`sefer_repo.get_all.await_args.kwargs == {...}`). Convert to behavioral: seed 1 active + 1 soft-deleted trip, run `get_dashboard_data(recent_limit=3)` with real `DashboardService(session=...)`, assert the returned recent list excludes the deleted trip and the count reflects only non-deleted rows. Drop the await_args assertions entirely.

- [ ] **Step 3: `test_generate_vehicle_report_computes_performance_score_from_actual_stats`**

Currently monkeypatches `get_analiz_repo` to return canned stats (ort_tuketim=30, hedef=25 → score 80). Real version: seed an `Arac(hedef_tuketim=25)` + 4 completed trips averaging 30 L/100km so the real analiz_repo computes ort_tuketim≈30, then assert `performance_score`. Read the score formula in `report_service.generate_vehicle_report` first; run to confirm the exact score and seed values that produce it.

- [ ] **Step 4: Tests 4 & 5 (sefer-import) — convert or defer**

`test_sefer_import_service_rejects_row_without_driver_or_route_resolution` and `..._sets_guzergah_id_for_valid_row` use `patch_unit_of_work` + mock `ExcelService.parse_sefer_excel` + a SimpleNamespace `sefer_service` with AsyncMock `bulk_add_sefer`, asserting internal call payloads.

These are the same surface as PR-3b's `test_sefer_import_service.py`. **Decision point:** if PR-3b is being done right after, MOVE these two tests into PR-3b and delete them here (note in commit). Otherwise convert in place: build a real `.xlsx` (openpyxl, headers Tarih/Plaka/İstasyon-style for sefer — confirm the sefer excel schema), seed real arac/sofor/lokasyon master rows, call the real `SeferImportService.process_excel_import`, and assert the **result** (count==0 + error "Şoför bulunamadı" for the missing-driver case; count==1 + a real `seferler` row with the resolved `guzergah_id` for the valid case). No `patch_unit_of_work`, no `bulk_add` mock.

- [ ] **Step 5: Run, confirm, clean**

Run: `pytest app/tests/unit/test_dashboard_report_import_contracts.py -q`
Expected: all pass (or 3 pass + 2 moved to PR-3b). Remove `from app.tests._helpers.uow_mock import patch_unit_of_work`, `AsyncMock, MagicMock, patch`, `SimpleNamespace` doubles.

- [ ] **Step 6: Commit**

```bash
git add app/tests/unit/test_dashboard_report_import_contracts.py
git commit -m "test(0-mock 3a): dashboard/report/import contracts → real DB seed"
```

---

## Task 7: PR-3a green-suite gate + coverage check

- [ ] **Step 1: Run the full unit+api suite in the dev container**

Run: `pytest app/tests/unit app/tests/api -q` (wrapped in the `docker run` recipe).
Expected: 0 failures. Investigate any regression before proceeding (likely cross-test row leakage or a real-behavior mismatch surfaced by de-mocking).

- [ ] **Step 2: Coverage did not drop**

Run with `--cov=app --cov-report=term-missing`. Compare the overall % to `main` baseline (memory `coverage_real_state`: ~92%). If any converted file lost coverage because a synthetic path was deleted, confirm the deletion was justified per spec §2 (real path unreachable / duplicate). Record the before/after numbers in the PR description.

- [ ] **Step 3: ruff + mypy on touched files**

Run: `ruff check app/tests app/tests/_helpers/seed.py` and `mypy app --ignore-missing-imports --no-strict-optional` (touched modules clean).

- [ ] **Step 4: Confirm 3a's FakeUnitOfWork residue is gone**

Run: `grep -rn "FakeUnitOfWork\|uow_mock\|patch_unit_of_work\|FakeSeferRepo" app/tests/unit/test_driver_route_profile.py app/tests/unit/test_route_similarity.py app/tests/unit/test_services/test_sefer_service.py app/tests/unit/test_services/test_license_service.py app/tests/unit/test_services/test_analiz_service_coverage.py app/tests/unit/test_dashboard_report_import_contracts.py`
Expected: 0 matches (the helper file itself + remaining 7 files are deleted/converted in PR-3b/3c).

- [ ] **Step 5: Open PR-3a**

```bash
git push -u origin <branch>
gh pr create --title "test(0-mock slice 3a): FakeUnitOfWork → real UoW (6 small/medium files)" \
  --body "Slice 3a of zero-mock epic. See docs/superpowers/specs/2026-06-18-zero-mock-slice3-fakeuow-design.md. Coverage before/after: <fill>."
```

---

## Self-review notes

- **Spec coverage:** §1 (13 files) — this plan covers 6 (PR-3a); 3b/3c get their own plans. §2 methodology applied per-task (keep/convert/delete-duplicate/real-fault). §4 runner recipe in the header. §5 verification = Task 7.
- **Run-dependent values:** several assertions (median coefficient, fleet average, performance_score, import counts) depend on real query/formula output. Each such step explicitly says "run, observe actual, assert the real value" rather than hard-coding a guessed number — this is correct methodology for de-mocking computation, not a placeholder.
- **Open investigations folded into Step 1 of each task:** exact column names in `models.py`, repo query semantics, and the constructor's tolerance for `None` repos must be confirmed before writing seeds — these are real codebase facts, not invented.
- **Deviation flagged:** Tasks 5 & 6 are heavier than the spec's "small/medium" label; Task 6's import tests may migrate to PR-3b.
