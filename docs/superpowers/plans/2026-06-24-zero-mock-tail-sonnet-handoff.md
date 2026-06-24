# Zero-mock tail — Sonnet-medium handoff plan

**Status:** active · **Owner model:** Claude Sonnet 4.6 (medium effort), escalating to Opus
**Created:** 2026-06-24 (Opus) after the FakeUnitOfWork epic closed.

## Why this exists

The high-value core of the zero-mock campaign is done (FakeUnitOfWork helper
deleted + CI gate; Population B; **5 real prod bugs** found+fixed). What remains
is a large, lower-risk, mostly-mechanical tail. Per the user's cost decision
(2026-06-24), **Sonnet-medium runs the mechanical slices; Opus handles judgment**.

Rules live in memory — read them first:
- `model-split-policy` — who does what + the 5 escalation triggers.
- `demock-playbook` — the 7-step per-slice recipe ("work like Opus").
- `local-test-db-execution` — the faithful Docker test recipe.
- `no-error-no-fake-code` — the hard rule: 0 mock-that-hides-bugs, 0 fake code, everything proven by a real run + CI.

## The one rule that matters most

> **Sonnet does mechanical conversions that stay GREEN. The moment a de-mock
> makes a real-DB test FAIL, STOP — do not patch blindly. That is a suspected
> real prod bug → hand to Opus** (root-cause + migration/schema verify). Same
> for: fixes needing business-data/defaults, "is this a real boundary or
> artifact?" diag, any prod-code change, schema/migration/alembic work.

## Per-slice protocol (every file, no exceptions)

Follow `demock-playbook` exactly: **diag → convert → prove locally (Docker
recipe, 0 skip/0 xfail) → ruff/format/mypy clean → one-slice-one-commit
(no `--no-verify`) → push → `gh run watch` until `hard-gates` is green.**
Never claim done on local-green alone. Never stack a new slice on an
unproven prod change.

## Ordered work batches

Source of file lists: `docs/superpowers/audits/MOCK-INVENTORY.md`. Re-grep
before starting each batch (the inventory may drift).

### Batch 1 — Category A: internal monkeypatch → real DB  *(Sonnet-medium)*
Unit tests that `monkeypatch`/`patch` an **internal** service/repo function
instead of exercising real logic. Convert file-by-file: seed real rows, drop
the internal patch, assert real results. Keep **external** boundaries mocked
(Groq/Redis/httpx/Mapbox/Open-Meteo/event-bus) — those are legitimate.
- Find: `grep -rln "monkeypatch.setattr\|@patch" app/tests` minus external-only files.
- Expect most to stay green. Any failure → Opus (trigger #1).

### Batch 2 — Frontend: vi.mock → real fetch / Playwright  *(Sonnet-medium)*
~133 `vi.mock` test files. Prefer real `fetch` against MSW/handlers or
Playwright e2e for flows; keep mocking only true externals. Big volume, low
per-file risk. Prove with `npx vitest --run` + the e2e lane.

### Batch 3 — Category B: external-API seams  *(Opus, low priority)*
Mostly legitimate external boundaries — **do not mechanically convert.** Only
the *internal* seam around an external call is a candidate. Requires judgment
(real-stub container vs live lane) → Opus decides per case. Often the right
answer is "leave mocked, it's a real boundary."

## Done-definition

A batch is done when: every targeted file is de-mocked or explicitly
documented as a legitimate boundary, each slice's `hard-gates` CI is green,
and no `app/tests` file reintroduces `patch_unit_of_work`/`uow_mock` (the CI
gate enforces this). Update `MOCK-INVENTORY.md` counts as you go.
