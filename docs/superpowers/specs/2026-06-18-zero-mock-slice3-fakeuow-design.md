# Zero-Mock Slice 3 — Finish the FakeUnitOfWork Category

**Date:** 2026-06-18
**Branch base:** `main` (repo: `github.com/semh59/lojinext-app`)
**Epic:** Mutlak 0-Mock test dönüşümü — see `docs/superpowers/audits/MOCK-INVENTORY.md`
**Predecessors:** Slice 1 (Redis de-mock, `e616f078`) ✅ · Slice 2 (yakit-import → real DB+xlsx, `f2133454`) ✅

---

## 1. Goal & scope

Convert the **13 remaining `FakeUnitOfWork` / `uow_mock` / `patch("...UnitOfWork")` consumers**
to a real `UnitOfWork` backed by real Postgres + real Redis, then **delete
`app/tests/_helpers/uow_mock.py`**. This closes Category A's "primary target" in
`MOCK-INVENTORY.md`.

After this slice, the only Category-A residue remaining is the broader
internal-monkeypatch surface (~200 files) — a later slice, explicitly out of scope here.

### In scope (13 files + helper)

| # | File | Lines | FUoW refs |
|---|------|------:|----------:|
| 1 | `app/tests/unit/test_driver_route_profile.py` | 79 | 3 |
| 2 | `app/tests/unit/test_route_similarity.py` | 108 | 3 |
| 3 | `app/tests/unit/test_services/test_sefer_service.py` | 234 | 2 |
| 4 | `app/tests/unit/test_services/test_license_service.py` | 171 | 7 |
| 5 | `app/tests/unit/test_services/test_analiz_service_coverage.py` | 363 | 3 |
| 6 | `app/tests/unit/test_dashboard_report_import_contracts.py` | 225 | 4 |
| 7 | `app/tests/unit/test_workers/test_theft_tasks.py` | 134 | 6 |
| 8 | `app/tests/unit/test_workers/test_driver_tasks.py` | 116 | 4 |
| 9 | `app/tests/unit/test_sefer_import_service.py` | 312 | 2 |
| 10 | `app/tests/unit/test_services/test_import_service.py` | 502 | 5 |
| 11 | `app/tests/unit/test_services/test_import_service_coverage.py` | 1291 | 28 |
| 12 | `app/tests/unit/test_coverage_boost.py` | 1145 | 7 |
| 13 | `app/tests/unit/test_yakit_import_periyot_trigger.py` | 236 | 1 |
| — | `app/tests/_helpers/uow_mock.py` (delete) | 113 | helper |

### Done criteria

- `grep -r "FakeUnitOfWork\|uow_mock\|patch_unit_of_work" app/tests` → **0 matches**
- Full unit+api suite **green** in the dev container
- Coverage **≥ baseline** (measured per PR with `--cov`)
- `app/tests/_helpers/uow_mock.py` deleted; CI grep-gate forbids reintroduction

---

## 2. Per-test conversion methodology

Classify every test first, then act:

- **Pure-logic, already mock-free** (e.g. `classify_route` tests) → **leave untouched.**
- **Mocks repo/UoW data** → seed real rows via real `UnitOfWork`, call the real
  service/function, assert on the **business result** (rows created, computed value) —
  not internal calls (`recalc_calls == {1,2}`, `isinstance(x, YakitCreate)`).
- **Fault-injection** (`session.execute side_effect=Exception(...)`) → **trigger a real
  fault** (closed session / query against a dropped or nonexistent table / invalid SQL).
  **No patch, no mock.** (Decision: pure 0-mock for error paths.)
- **Synthetic / unreachable path** (e.g. the `missing_tarih` row the real parser at
  `excel_parser.py:132-141` already silently skips — the mock artificially opened that
  path) → **delete**, since the real code path can't reach it.
- **Proven duplicate** (behavior already asserted by a surviving real test, e.g. slice-2
  import tests) → delete **only after** proving coverage holds via `--cov` before/after
  diff. No blind deletion.

> Rationale (from epic memory): these mock tests verify *internal calls*; converting is
> NOT mechanical — each test needs its business logic read and re-expressed as a real
> result assertion. Period-calc logic in particular: one receipt may not create a period
> row, so assertions must reflect the real rule.

---

## 3. Delivery — 3 sub-PRs, each its own green suite

Difficulty-ordered; helper stays until PR-3c.

### PR-3a — small / medium (6 files, ~1,150 L)
`test_driver_route_profile.py`, `test_route_similarity.py`,
`test_services/test_sefer_service.py`, `test_services/test_license_service.py`,
`test_services/test_analiz_service_coverage.py`,
`test_dashboard_report_import_contracts.py`.

Mostly seed-and-assert conversions. `test_driver_route_profile.py` is the model case:
keep the 4 `classify_route` pure-logic tests, convert the 2 that patch `UnitOfWork`
by seeding real `seferler` rows (correct route_type + gerçek/tahmini values) and
asserting the computed coefficient.

### PR-3b — workers + import core (4 files, ~1,060 L)
`test_workers/test_theft_tasks.py`, `test_workers/test_driver_tasks.py`,
`test_sefer_import_service.py`, `test_services/test_import_service.py`.

Contains the real-fault-injection work (theft/driver task DB-error paths). Raw-SQL
result mocks (`uow.session.execute` → mapped rows) become real seeded data so the
pattern-scan query returns real rows.

### PR-3c — giants + finish (3 files + delete, ~2,670 L)
`test_services/test_import_service_coverage.py` (1291 L / 28 refs),
`test_coverage_boost.py` (1145 L), `test_yakit_import_periyot_trigger.py`.

Apply the duplicate-pruning methodology (§2) — convert faithfully, then remove
coverage-only duplicates proven redundant. Finish with:
- **delete `app/tests/_helpers/uow_mock.py`**
- add a CI grep-gate line forbidding reintroduction of
  `FakeUnitOfWork`/`uow_mock`/`patch_unit_of_work` in `app/tests`.

---

## 4. Test infrastructure (already established)

See memory `local-test-db-execution`. `lojinext-backend-dev` image (backend image +
`requirements-dev`, `docker commit`), repo-mounted via `docker run`, connected to the
running `db` / `redis` containers.

Critical env:
- `USE_SEFER_FUEL_ESTIMATOR=false` — else the mounted dev `.env` leaks `true` and opens
  the estimator path, breaking prediction tests.
- `REDIS_URL=redis://redis:6379/15` — isolated DB index, never flush app's `/0`.
- `SECRET_KEY` + `POSTGRES_PASSWORD` pulled from the running backend via `printenv`
  (the multiline JWT key in `.env` breaks `--env-file`).
- `MSYS_NO_PATHCONV=1` — Git Bash path mangling.
- `TEST_DATABASE_URL` must point at a DB whose name contains `test` (conftest drops the
  public schema).

Seeding uses real repos through `async with UnitOfWork() as uow`, respecting CLAUDE.md
gotchas:
- `seferler` `net_kg` check constraint: pre-fetch `arac.bos_agirlik_kg`, compute
  `dolu = bos + net`.
- Non-uniform `get_all` kwargs (`sadece_aktif=False` vs `include_inactive=True`).
- Singleton repos need UoW for raw-SQL methods.

---

## 5. Verification per PR (no "done" without proof)

1. `pytest` unit+api **green** in the dev container.
2. `--cov` before/after — coverage must **not drop**; any deletion justified by the
   coverage diff.
3. `ruff check` + `mypy` clean on touched files.
4. PR-3c only: the 0-match grep + helper deletion + CI gate line.

Each PR is a separate branch off `main`, merged green before the next begins — matching
the kademeli-merge method from the ARCH-004 mypy epic and slices 1–2.

---

## 6. Out of scope

- The ~200-file internal-monkeypatch surface (Category A residue) — later slice.
- External-API stub containers (Category B) — later slice.
- Frontend Playwright / `vi.mock` removal — later slice.
- The 2 pre-existing uncommitted working-tree files (`BakimPage.tsx`, `sw-push.ts`) —
  unrelated to this epic, left as-is.
