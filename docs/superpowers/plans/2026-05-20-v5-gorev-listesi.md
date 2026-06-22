# LojiNext v5 Görev Listesi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 2 critical bugs (error digest silent failure + CI Telegram gap), 3 medium improvements (Sentry warning, ML speed features, route similarity), and 1 future skeleton (driver route profile).

**Architecture:** Bug fixes target specific lines in existing files; ML additions extend `ensemble_core.py` and `sefer_repo.py` with backward-compatible feature additions (model retrain triggered automatically via hash change). New ML modules are pure-function files with async DB access via UnitOfWork.

**Tech Stack:** FastAPI, Celery, Redis (aioredis), SQLAlchemy 2 async, NumPy, pytest-asyncio, GitHub Actions YAML

---

## Verification Summary (pre-plan code audit)

| Görev | Durum | Notlar |
|-------|-------|--------|
| 1 — error_digest `_redis` | **CONFIRMED BUG** | Lines 30, 34, 42, 73 use `mgr._redis`; public `redis` property exists at `redis_pubsub.py:199` |
| 2 — CI Telegram | **CONFIRMED MISSING** | No Telegram step in `ci.yml`; only Playwright upload on failure |
| 3 — Sentry startup warn | **CONFIRMED MISSING** | `_wire_observability()` has no `else` branch for missing DSN in production |
| 4 — ML speed feature | **CONFIRMED MISSING** | `FEATURE_NAMES` has 26 features; `expected_avg_speed` / `urban_speed_ratio` / `highway_speed_ratio` absent |
| 5 — Route similarity | **FILE MISSING** | `app/core/ml/route_similarity.py` does not exist; `sefer_repo` lacks `get_with_route_analysis()` |
| 6 — Driver route profile | **FILE MISSING** | `app/core/ml/driver_route_profile.py` does not exist; `sefer_repo` lacks `get_driver_trips_by_route_type()` |

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `app/workers/tasks/error_digest.py` | Replace `mgr._redis` → local `redis = mgr.redis` (4 occurrences) |
| Modify | `.github/workflows/ci.yml` | Add Telegram notification step with `if: failure()` |
| Modify | `app/main.py` | Add `else` branch to `_wire_observability()` for production SENTRY_DSN warning |
| Modify | `app/core/ml/ensemble_core.py` | Add 3 speed features to `FEATURE_NAMES` + calculation in `prepare_features()` |
| Modify | `app/database/repositories/sefer_repo.py` | Add `get_with_route_analysis()` method |
| Create | `app/core/ml/route_similarity.py` | New file: cosine similarity engine for historical route matching |
| Modify | `app/database/repositories/sefer_repo.py` | Add `get_driver_trips_by_route_type()` method |
| Create | `app/core/ml/driver_route_profile.py` | New file: driver × route-type coefficient skeleton |
| Create | `app/tests/unit/test_error_digest.py` | Unit tests for Görev 1 |
| Create | `app/tests/unit/test_sentry_startup.py` | Unit tests for Görev 3 |
| Create | `app/tests/unit/test_ml_speed_features.py` | Unit tests for Görev 4 |
| Create | `app/tests/unit/test_route_similarity.py` | Unit tests for Görev 5 |
| Create | `app/tests/unit/test_driver_route_profile.py` | Unit tests for Görev 6 |

---

## Task 1: Fix `error_digest.py` — Private Field Bug (CRITICAL)

**Files:**
- Modify: `app/workers/tasks/error_digest.py:30,34,42,73`
- Create: `app/tests/unit/test_error_digest.py`

### Background
`_run_digest()` accesses `mgr._redis` directly. When `RedisPubSubManager` is freshly instantiated (Celery worker cold-start), `_redis` is `None` until `connect()` is awaited. The `get_pubsub_manager()` factory may return a manager that hasn't connected yet, causing silent early-return — 5-minute error digests never reach Telegram.

The public `redis` property at `redis_pubsub.py:199` exposes the same field safely, and that's what callers should use.

- [ ] **Step 1: Write the failing test**

Create `app/tests/unit/test_error_digest.py`:

```python
"""Tests for error_digest task — verifies public redis property usage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_digest_uses_public_redis_property():
    """_run_digest must use mgr.redis (public), not mgr._redis (private)."""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[])
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis    # public — non-None
    mock_mgr._redis = None         # private — None, simulates cold-start

    with patch(
        "app.workers.tasks.error_digest.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        from app.workers.tasks.error_digest import _run_digest
        await _run_digest()

    mock_redis.keys.assert_called_once()


@pytest.mark.asyncio
async def test_digest_exits_when_redis_is_none():
    """_run_digest must return early when mgr.redis is None (no connection)."""
    mock_mgr = MagicMock()
    mock_mgr.redis = None

    with patch(
        "app.workers.tasks.error_digest.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        from app.workers.tasks.error_digest import _run_digest
        await _run_digest()
        # No exception — silent early return is correct behavior


@pytest.mark.asyncio
async def test_digest_sends_telegram_when_keys_present():
    """_run_digest must call notify_error when error keys exist."""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[b"error:digest:api:auth_fail"])
    pipe_mock = AsyncMock()
    pipe_mock.execute = AsyncMock(
        return_value=[{b"count": b"3", b"message_sample": b"token expired"}]
    )
    mock_redis.pipeline = MagicMock(return_value=pipe_mock)

    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(
        "app.workers.tasks.error_digest.get_pubsub_manager",
        return_value=mock_mgr,
    ), patch(
        "app.workers.tasks.error_digest.notify_error",
        new_callable=AsyncMock,
    ) as mock_notify, patch(
        "app.workers.tasks.error_digest.check_beat_health",
        new_callable=AsyncMock,
    ), patch(
        "app.workers.tasks.error_digest._check_queue_depth",
        new_callable=AsyncMock,
    ), patch(
        "app.workers.tasks.error_digest.AsyncSessionLocal",
    ):
        from app.workers.tasks.error_digest import _run_digest
        await _run_digest()

    mock_notify.assert_called_once()
    call_kwargs = mock_notify.call_args.kwargs
    assert call_kwargs["level"] == "error"
    assert "5dk Özet" in call_kwargs["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest app/tests/unit/test_error_digest.py -v --tb=short
```

Expected: `test_digest_uses_public_redis_property` FAILS because `mgr._redis` is None → `_run_digest` returns early without calling `mock_redis.keys`.

- [ ] **Step 3: Fix `_run_digest()` in `error_digest.py`**

Open `app/workers/tasks/error_digest.py`. The current `_run_digest` function starts at line 25. Replace the `_redis` usages with a local `redis` variable bound to the public property:

```python
async def _run_digest() -> None:
    from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
    from app.infrastructure.notifications.telegram_notifier import notify_error

    mgr = get_pubsub_manager()
    redis = mgr.redis          # public property — None if not yet connected
    if redis is None:
        return

    try:
        keys = await redis.keys("error:digest:*")
    except Exception as exc:
        logger.warning("Digest Redis scan failed: %s", exc)
        return

    if not keys:
        return

    pipe = redis.pipeline()
    for key in keys:
        pipe.hgetall(key)
    results = await pipe.execute()

    layer_totals: dict[str, int] = {}
    lines: list[str] = []
    for key, data in zip(keys, results):
        if not data:
            continue
        parts = key.split(":", 3)  # error:digest:{layer}:{category}
        if len(parts) < 4:
            continue
        layer = parts[2]
        category = parts[3]
        count = int(data.get("count", "1"))
        sample = data.get("message_sample", "")[:100]
        layer_totals[layer] = layer_totals.get(layer, 0) + count
        lines.append(f"  • {layer}/{category}: {count}× — {sample}")

    if not lines:
        return

    summary_parts = [f"{layer}: {cnt}" for layer, cnt in sorted(layer_totals.items())]
    header = f"📊 5dk Özet — {', '.join(summary_parts)}"
    body = "\n".join(lines[:20])
    if len(lines) > 20:
        body += f"\n  …ve {len(lines) - 20} daha"

    await notify_error(level="error", message=f"{header}\n{body}", path="digest")

    del_pipe = redis.pipeline()
    for key in keys:
        del_pipe.delete(key)
    await del_pipe.execute()

    try:
        from sqlalchemy import text

        from app.database.connection import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY error_hourly_stats")
            )
            await session.commit()
    except Exception as exc:
        logger.warning("error_hourly_stats refresh failed: %s", exc)

    # Check Celery beat health
    from app.infrastructure.monitoring.celery_probe import check_beat_health
    await check_beat_health()

    # Check queue depth
    await _check_queue_depth()
```

Note: The key change is lines 30-34: `mgr._redis` → `redis = mgr.redis` + local `redis` variable used throughout. The `del_pipe = mgr._redis.pipeline()` at line 73 also changes to `del_pipe = redis.pipeline()`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest app/tests/unit/test_error_digest.py -v --tb=short
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Run full unit suite to catch regressions**

```bash
pytest -m "unit or not integration" -q --tb=short --ignore=app/tests/integration
```

Expected: No new failures.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks/error_digest.py app/tests/unit/test_error_digest.py
git commit -m "fix(digest): use public redis property to prevent silent digest failure

mgr._redis is None on cold-start; mgr.redis is the public property.
5-minute error digests were silently exiting before sending to Telegram."
```

---

## Task 2: CI — Telegram Failure Notification (CRITICAL)

**Files:**
- Modify: `.github/workflows/ci.yml`

### Background
When `hard-gates` job fails, only a GitHub notification email is sent. The ops team relies on Telegram for real-time alerting. The step must use `|| true` so a curl failure (e.g., network timeout) doesn't mask the original CI failure.

The secrets `TELEGRAM_OPS_BOT_TOKEN` and `TELEGRAM_OPS_CHAT_ID` must be added to GitHub repo Settings → Secrets → Actions manually — they match the values in `docker-compose.yml`.

- [ ] **Step 1: Add Telegram notification step to `ci.yml`**

In `.github/workflows/ci.yml`, find the `Stop backend` step (currently the last step in `hard-gates`):

```yaml
      - name: Stop backend
        if: always()
        run: kill $UVICORN_PID || true
```

Insert the Telegram step **before** `Stop backend` (after the `Upload Playwright report` step):

```yaml
      - name: Telegram CI Bildirimi
        if: failure()
        run: |
          MSG="🔴 CI HATA
Repo: ${{ github.repository }}
Branch: ${{ github.ref_name }}
Commit: ${{ github.sha }}
Workflow: ${{ github.workflow }}
Link: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          curl -s -X POST \
            "https://api.telegram.org/bot${{ secrets.TELEGRAM_OPS_BOT_TOKEN }}/sendMessage" \
            --data-urlencode "chat_id=${{ secrets.TELEGRAM_OPS_CHAT_ID }}" \
            --data-urlencode "text=${MSG}" \
            || true
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`

- [ ] **Step 3: Manual action — add GitHub Secrets**

Go to: GitHub repo → Settings → Secrets and variables → Actions → New repository secret

Add:
- `TELEGRAM_OPS_BOT_TOKEN` — same value as in `docker-compose.yml` `OPS_BOT_TOKEN`
- `TELEGRAM_OPS_CHAT_ID` — same value as in `docker-compose.yml` `OPS_CHAT_ID`

This cannot be automated. Document the status in PR description.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Telegram failure notification to hard-gates job

CI failures now send an immediate Telegram message to the ops channel.
curl uses || true so a bot timeout doesn't mask the real failure."
```

---

## Task 3: Sentry DSN Startup Warning (MEDIUM)

**Files:**
- Modify: `app/main.py:114-142`
- Create: `app/tests/unit/test_sentry_startup.py`

### Background
`_wire_observability()` silently skips Sentry init when `SENTRY_DSN` is not set. In production this means errors are never captured — and no one knows. The fix adds an `else` branch that logs a WARNING when running in the `production` environment without a DSN.

- [ ] **Step 1: Write the failing test**

Create `app/tests/unit/test_sentry_startup.py`:

```python
"""Tests for Sentry startup warning in _wire_observability."""
import logging
import pytest
from unittest.mock import patch, MagicMock


def test_sentry_warns_when_dsn_missing_in_production(caplog):
    """Must log WARNING when ENVIRONMENT=production and SENTRY_DSN is unset."""
    import importlib

    with patch("app.config.settings.SENTRY_DSN", None), \
         patch("app.config.settings.ENVIRONMENT", "production"):
        with caplog.at_level(logging.WARNING, logger="app.main"):
            from app.main import _wire_observability
            fake_app = MagicMock()
            _wire_observability(fake_app)

    assert any("SENTRY_DSN not set" in r.message for r in caplog.records), (
        f"Expected 'SENTRY_DSN not set' warning. Got: {[r.message for r in caplog.records]}"
    )


def test_sentry_no_warn_in_dev_without_dsn(caplog):
    """Must NOT log SENTRY_DSN warning in non-production environment."""
    with patch("app.config.settings.SENTRY_DSN", None), \
         patch("app.config.settings.ENVIRONMENT", "development"):
        with caplog.at_level(logging.WARNING, logger="app.main"):
            from app.main import _wire_observability
            fake_app = MagicMock()
            _wire_observability(fake_app)

    sentry_warnings = [r for r in caplog.records if "SENTRY_DSN not set" in r.message]
    assert len(sentry_warnings) == 0, (
        f"Should not warn about SENTRY_DSN in dev. Got: {sentry_warnings}"
    )


def test_sentry_logs_init_success(caplog):
    """Must log info when Sentry initializes successfully."""
    fake_dsn = "https://abc123@sentry.example.com/1"
    with patch("app.config.settings.SENTRY_DSN", fake_dsn), \
         patch("sentry_sdk.init"), \
         patch("sentry_sdk.integrations.logging.LoggingIntegration"):
        with caplog.at_level(logging.INFO, logger="app.main"):
            from app.main import _wire_observability
            fake_app = MagicMock()
            _wire_observability(fake_app)

    assert any("Sentry initialized" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest app/tests/unit/test_sentry_startup.py::test_sentry_warns_when_dsn_missing_in_production -v --tb=short
```

Expected: FAIL — no warning is currently logged.

- [ ] **Step 3: Add `else` branch to `_wire_observability()` in `app/main.py`**

Current code at `app/main.py:117`:
```python
    if settings.SENTRY_DSN:
        try:
            import logging as _logging
            import sentry_sdk
            ...
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("SENTRY_DSN set but sentry_sdk not installed")
```

Add immediately after the `try/except` block (after line 141), still inside `_wire_observability`:
```python
    else:
        if settings.ENVIRONMENT == "production":
            logger.warning(
                "SENTRY_DSN not set — Sentry disabled. "
                "Set SENTRY_DSN in .env for production error tracking."
            )
```

- [ ] **Step 4: Run all Sentry tests**

```bash
pytest app/tests/unit/test_sentry_startup.py -v --tb=short
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Verify no import-level side effects from test patching**

```bash
pytest -m "unit or not integration" -q --tb=short --ignore=app/tests/integration -x
```

Expected: No new failures.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/tests/unit/test_sentry_startup.py
git commit -m "fix(observability): warn when SENTRY_DSN unset in production

Prevents silent error-tracking blackout in production.
Non-production environments are not warned (DSN-less dev is normal)."
```

---

## Task 4: ML — Hız Profili Feature Engineering (MEDIUM)

**Files:**
- Modify: `app/core/ml/ensemble_core.py:105-134` (FEATURE_NAMES)
- Modify: `app/core/ml/ensemble_core.py:370-401` (features.append list)
- Modify: `app/core/ml/ensemble_core.py:346-368` (calculation block)
- Create: `app/tests/unit/test_ml_speed_features.py`

### Background
The physics predictor internally uses road-type speed maps, but the ML ensemble never sees "what average speed is expected on this route." Adding `expected_avg_speed`, `urban_speed_ratio`, and `highway_speed_ratio` gives the ensemble a direct signal. **Feature count changes from 26 → 29.** The `_feature_hash` will change, triggering automatic model retrain on next startup — physics cold-start is the correct fallback.

- [ ] **Step 1: Write the failing test**

Create `app/tests/unit/test_ml_speed_features.py`:

```python
"""Tests for speed profile ML features added to EnsemblePredictor."""
import pytest
import numpy as np
from app.core.ml.ensemble_core import EnsemblePredictor


SAMPLE_SEFER = {
    "ton": 20.0,
    "mesafe_km": 500.0,
    "ascent_m": 800.0,
    "descent_m": 750.0,
    "flat_distance_km": 350.0,
    "zorluk": "Normal",
    "arac_yasi": 5.0,
    "yas_faktoru": 1.0,
    "mevsim_faktor": 1.0,
    "sofor_katsayi": 1.0,
    "dorse_bos_agirlik": 6500.0,
    "dorse_lastik_sayisi": 6,
    "rota_detay": {
        "motorway": {"flat": 200.0, "up": 10.0, "down": 10.0},
        "trunk":    {"flat": 80.0, "up": 5.0, "down": 5.0},
        "primary":  {"flat": 50.0, "up": 8.0, "down": 7.0},
        "residential": {"flat": 15.0, "up": 2.0, "down": 1.0},
        "other":    {"flat": 5.0, "up": 1.0, "down": 1.0},
        "ascent_m": 800.0,
        "descent_m": 750.0,
    },
}


def test_feature_count_matches_feature_names():
    """Feature matrix column count must equal len(FEATURE_NAMES)."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    assert features.shape[1] == len(EnsemblePredictor.FEATURE_NAMES), (
        f"Shape[1]={features.shape[1]} != len(FEATURE_NAMES)={len(EnsemblePredictor.FEATURE_NAMES)}"
    )


def test_speed_feature_names_present():
    """New speed features must appear in FEATURE_NAMES."""
    assert "expected_avg_speed" in EnsemblePredictor.FEATURE_NAMES
    assert "urban_speed_ratio" in EnsemblePredictor.FEATURE_NAMES
    assert "highway_speed_ratio" in EnsemblePredictor.FEATURE_NAMES


def test_expected_avg_speed_is_positive():
    """expected_avg_speed must be positive when route_analysis is present."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    idx = EnsemblePredictor.FEATURE_NAMES.index("expected_avg_speed")
    assert features[0, idx] > 0.0, f"expected_avg_speed={features[0, idx]} should be > 0"


def test_highway_speed_ratio_between_0_and_1():
    """highway_speed_ratio = motorway_ratio + trunk_ratio, capped at 1.0."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    idx = EnsemblePredictor.FEATURE_NAMES.index("highway_speed_ratio")
    assert 0.0 <= features[0, idx] <= 1.0


def test_empty_route_analysis_produces_zero_speed_features():
    """Without route_analysis, speed features must default to 0."""
    sefer_no_route = {**SAMPLE_SEFER, "rota_detay": {}}
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([sefer_no_route])
    idx_speed = EnsemblePredictor.FEATURE_NAMES.index("expected_avg_speed")
    assert features[0, idx_speed] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest app/tests/unit/test_ml_speed_features.py -v --tb=short
```

Expected: `test_speed_feature_names_present` and `test_feature_count_matches_feature_names` FAIL.

- [ ] **Step 3: Add features to `FEATURE_NAMES` in `ensemble_core.py`**

In `app/core/ml/ensemble_core.py`, find the `FEATURE_NAMES` list (line 105). After `"dorse_lastik_sayisi"` (current last element), add:

```python
    FEATURE_NAMES = [
        "ton",
        "ascent_m",
        "descent_m",
        "net_elevation",
        "yuk_yogunlugu",
        "zorluk",
        "arac_yasi",
        "yas_faktoru",
        "mevsim_faktor",
        "sofor_katsayi",
        # Route Analysis Features (Phase 2G)
        "motorway_ratio",
        "trunk_ratio",
        "primary_ratio",
        "residential_ratio",
        "unclassified_ratio",
        "flat_km",
        # TIR Physics Features (Phase 5A - Refined)
        "grade_gentle_ratio",  # 0–2.5%
        "grade_moderate_ratio",  # 2.5–5.5%
        "grade_steep_ratio",  # 5.5%+
        "weight_x_gradient",  # ton × (ascent / (mesafe + 1))
        "stopgo_proxy",  # residential_ratio × sqrt(mesafe)
        "aero_speed_factor",  # motorway_ratio × Cd proxy
        "engine_load_proxy",  # (1 - flat_ratio)^1.3 × load_ratio
        "route_fatigue",  # proxy via duration
        "dorse_bos_agirlik",
        "dorse_lastik_sayisi",
        # Speed Profile Features (Phase 6A)
        "expected_avg_speed",   # weighted avg expected speed km/h
        "urban_speed_ratio",    # residential km / mesafe (stop-go proxy)
        "highway_speed_ratio",  # motorway + trunk ratio combined
    ]
```

- [ ] **Step 4: Add speed feature calculation in `prepare_features()`**

In `app/core/ml/ensemble_core.py`, find the block after the grade histogram calculation (around line 346, after `grade_steep_ratio` is computed). Add the speed calculations before `# ── Elite TIR Interaction Refinements`:

```python
            # ── Speed Profile Features (Phase 6A) ──
            speed_map_reference = {
                "motorway": 85.0, "trunk": 75.0, "primary": 65.0,
                "secondary": 55.0, "residential": 40.0, "other": 50.0,
            }
            if analysis and mesafe > 0:
                weighted_speed = 0.0
                total_weighted = 0.0
                for road_cls, spd in speed_map_reference.items():
                    road_km = sum(
                        float((analysis.get(road_cls) or {}).get(k, 0) or 0)
                        for k in ("flat", "up", "down")
                    )
                    weighted_speed += spd * road_km
                    total_weighted += road_km
                expected_avg_speed = weighted_speed / max(total_weighted, 1.0)
                urban_speed_ratio = sum(
                    float((analysis.get("residential") or {}).get(k, 0) or 0)
                    for k in ("flat", "up", "down")
                ) / mesafe
                highway_speed_ratio = min(1.0, motorway_ratio + trunk_ratio)
            else:
                expected_avg_speed = 0.0
                urban_speed_ratio = 0.0
                highway_speed_ratio = 0.0
```

- [ ] **Step 5: Add speed features to `features.append(...)` list**

In `app/core/ml/ensemble_core.py`, find `features.append([...])` (line 370). Add the 3 new features at the end, before the closing `]`:

```python
            features.append(
                [
                    ton,
                    ascent,
                    descent,
                    net_elevation,
                    yuk_yogunlugu,
                    zorluk,
                    arac_yasi,
                    yas_faktoru,
                    mevsim_faktor,
                    sofor_katsayi,
                    motorway_ratio,
                    trunk_ratio,
                    primary_ratio,
                    residential_ratio,
                    unclassified_ratio,
                    flat_km,
                    grade_gentle_ratio,
                    grade_moderate_ratio,
                    grade_steep_ratio,
                    weight_x_gradient,
                    stopgo_proxy,
                    aero_speed_factor,
                    engine_load_proxy,
                    route_fatigue,
                    dorse_bos_agirlik,
                    dorse_lastik_sayisi,
                    expected_avg_speed,
                    urban_speed_ratio,
                    highway_speed_ratio,
                ]
            )
```

- [ ] **Step 6: Run speed feature tests**

```bash
pytest app/tests/unit/test_ml_speed_features.py -v --tb=short
```

Expected: All 5 tests PASS.

- [ ] **Step 7: Run existing ML tests to check for regressions**

```bash
pytest app/tests/unit/test_ml_reliability.py app/tests/unit/test_ml_prediction_safety.py app/tests/unit/test_ml_audit.py -v --tb=short
```

Expected: PASS (these tests mock `prepare_features` or use feature count from `FEATURE_NAMES` dynamically).

- [ ] **Step 8: Commit**

```bash
git add app/core/ml/ensemble_core.py app/tests/unit/test_ml_speed_features.py
git commit -m "feat(ml): add speed profile features to ensemble (Phase 6A)

Adds expected_avg_speed, urban_speed_ratio, highway_speed_ratio (26→29 features).
Feature hash changes — existing trained models auto-retrain on next startup.
Physics cold-start weight (0.80) remains active until retraining completes."
```

---

## Task 5: ML — Tarihsel Güzergah Eşleştirmesi (MEDIUM)

**Files:**
- Create: `app/core/ml/route_similarity.py`
- Modify: `app/database/repositories/sefer_repo.py` (add `get_with_route_analysis()`)
- Create: `app/tests/unit/test_route_similarity.py`

### Background
The strongest ML signal — "this route has been driven before, and the actual consumption was X" — is currently unused. This module provides a cosine-similarity engine over an 8-dim route vector (6 road categories + ascent + descent) to find historical matches. It requires `gercek_tuketim` in the matched trips to be useful.

- [ ] **Step 1: Write the failing tests**

Create `app/tests/unit/test_route_similarity.py`:

```python
"""Tests for route similarity engine."""
import pytest
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock


def test_encode_route_returns_8d_vector():
    from app.core.ml.route_similarity import encode_route
    analysis = {
        "motorway": {"flat": 100.0, "up": 10.0, "down": 10.0},
        "trunk": {"flat": 50.0},
        "primary": {},
        "secondary": {},
        "residential": {"flat": 5.0},
        "other": {},
        "ascent_m": 800.0,
        "descent_m": 750.0,
    }
    vec = encode_route(analysis)
    assert vec.shape == (8,)
    assert vec.dtype == np.float32


def test_cosine_similarity_identical():
    from app.core.ml.route_similarity import cosine_similarity
    v = np.array([1.0, 0.5, 0.3, 0.0, 0.2, 0.0, 500.0, 300.0], dtype=np.float32)
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    from app.core.ml.route_similarity import cosine_similarity
    a = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vectors():
    from app.core.ml.route_similarity import cosine_similarity
    z = np.zeros(8, dtype=np.float32)
    assert cosine_similarity(z, z) == 0.0


@pytest.mark.asyncio
async def test_find_similar_trips_distance_filter():
    """Trips with >20% distance difference must be filtered out."""
    with patch("app.core.ml.route_similarity.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.sefer_repo.get_with_route_analysis = AsyncMock(
            return_value=[{
                "id": 1,
                "mesafe_km": 500.0,  # query: 100km → 400% diff → filtered
                "route_analysis": {},
                "gercek_tuketim": 80.0,
            }]
        )
        mock_uow_cls.return_value = mock_uow

        from app.core.ml.route_similarity import find_similar_trips
        result = await find_similar_trips({}, mesafe_km=100.0)
    assert result == []


@pytest.mark.asyncio
async def test_find_similar_trips_returns_sorted_by_similarity():
    """Results must be sorted by similarity descending."""
    vec = {"motorway": {"flat": 100.0}, "ascent_m": 500.0, "descent_m": 400.0}

    with patch("app.core.ml.route_similarity.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.sefer_repo.get_with_route_analysis = AsyncMock(
            return_value=[
                {"id": 1, "mesafe_km": 100.0, "route_analysis": vec, "gercek_tuketim": 50.0},
                {"id": 2, "mesafe_km": 100.0, "route_analysis": vec, "gercek_tuketim": 55.0},
            ]
        )
        mock_uow_cls.return_value = mock_uow

        from app.core.ml.route_similarity import find_similar_trips
        result = await find_similar_trips(vec, mesafe_km=100.0)

    assert len(result) >= 1
    if len(result) > 1:
        assert result[0]["similarity"] >= result[1]["similarity"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest app/tests/unit/test_route_similarity.py -v --tb=short
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'app.core.ml.route_similarity'`.

- [ ] **Step 3: Create `app/core/ml/route_similarity.py`**

```python
"""Güzergah benzerlik motoru — benzer geçmiş seferleri bulur."""
from __future__ import annotations

from typing import Dict, List

import numpy as np

SIMILARITY_THRESHOLD = 0.85


def encode_route(route_analysis: Dict) -> np.ndarray:
    """Güzergahı 8 boyutlu vektöre çevir: [motorway, trunk, primary, secondary, residential, other, ascent, descent]."""
    road_keys = ["motorway", "trunk", "primary", "secondary", "residential", "other"]
    vect = []
    for k in road_keys:
        cat = route_analysis.get(k) or {}
        vect.append(float(cat.get("flat", 0) or 0))
    vect.append(float(route_analysis.get("ascent_m") or 0))
    vect.append(float(route_analysis.get("descent_m") or 0))
    return np.array(vect, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def find_similar_trips(
    route_analysis: Dict,
    mesafe_km: float,
    limit: int = 5,
) -> List[Dict]:
    """Son 90 günden benzer güzergahlı seferleri döndürür."""
    from app.database.unit_of_work import UnitOfWork

    query_vec = encode_route(route_analysis)

    async with UnitOfWork() as uow:
        recent = await uow.sefer_repo.get_with_route_analysis(days=90, limit=200)

    similar = []
    for sefer in recent:
        if not sefer.get("route_analysis"):
            continue
        dist_diff = abs(sefer.get("mesafe_km", 0) - mesafe_km) / max(mesafe_km, 1)
        if dist_diff > 0.20:
            continue
        sim = cosine_similarity(query_vec, encode_route(sefer["route_analysis"]))
        if sim >= SIMILARITY_THRESHOLD:
            similar.append({
                "sefer_id": sefer["id"],
                "similarity": round(sim, 3),
                "gercek_tuketim": sefer.get("gercek_tuketim"),
                "mesafe_km": sefer.get("mesafe_km"),
            })

    return sorted(similar, key=lambda x: x["similarity"], reverse=True)[:limit]
```

- [ ] **Step 4: Add `get_with_route_analysis()` to `sefer_repo.py`**

Open `app/database/repositories/sefer_repo.py`. At the end of the `SeferRepository` class body (before the module-level `get_sefer_repo` function), add:

```python
    async def get_with_route_analysis(
        self, days: int = 90, limit: int = 200
    ) -> list[dict]:
        """Son N günün route_analysis ve gercek_tuketim dolu seferlerini döndürür."""
        import datetime

        from sqlalchemy import select

        from app.database.models import Sefer

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        async with self._get_session() as session:
            result = await session.execute(
                select(Sefer)
                .where(
                    Sefer.created_at >= cutoff,
                    Sefer.route_analysis.isnot(None),
                    Sefer.gercek_tuketim.isnot(None),
                    ~Sefer.is_deleted,
                )
                .limit(limit)
            )
            return [
                {
                    "id": s.id,
                    "mesafe_km": s.mesafe_km,
                    "route_analysis": s.route_analysis,
                    "gercek_tuketim": s.gercek_tuketim,
                }
                for s in result.scalars().all()
            ]
```

- [ ] **Step 5: Run route similarity tests**

```bash
pytest app/tests/unit/test_route_similarity.py -v --tb=short
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Run full unit suite**

```bash
pytest -m "unit or not integration" -q --tb=short --ignore=app/tests/integration
```

Expected: No new failures. Coverage must stay ≥ 70%.

- [ ] **Step 7: Commit**

```bash
git add app/core/ml/route_similarity.py app/database/repositories/sefer_repo.py app/tests/unit/test_route_similarity.py
git commit -m "feat(ml): add route similarity engine for historical trip matching

Cosine similarity over 8-dim route vector (road types + ascent/descent).
Filters by ±20% distance, threshold 0.85. Queries last 90 days via UoW.
Enables 'similar route → similar consumption' signal in future ensemble."
```

---

## Task 6: ML — Şoför × Güzergah Tipi Profili Skeleton (FUTURE)

**Files:**
- Create: `app/core/ml/driver_route_profile.py`
- Modify: `app/database/repositories/sefer_repo.py` (add `get_driver_trips_by_route_type()`)
- Create: `app/tests/unit/test_driver_route_profile.py`

### Background
Global driver coefficient ignores route-type behavior. A driver who is efficient on highways may be poor in urban stop-go. This module classifies routes into 4 types and computes per-type median deviation ratio. Returns 1.0 (neutral) until ≥5 trips of that type exist — safe for production with sparse data.

- [ ] **Step 1: Write the failing tests**

Create `app/tests/unit/test_driver_route_profile.py`:

```python
"""Tests for driver × route-type coefficient module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_classify_route_highway_dominant():
    from app.core.ml.driver_route_profile import classify_route
    analysis = {"motorway": {"flat": 600.0, "up": 10.0, "down": 10.0}}
    assert classify_route(analysis) == "highway_dominant"


def test_classify_route_mountain():
    from app.core.ml.driver_route_profile import classify_route
    analysis = {
        "primary": {"flat": 0.0, "up": 80.0, "down": 80.0},
        "ascent_m": 2400.0,
    }
    assert classify_route(analysis) == "mountain"


def test_classify_route_urban():
    from app.core.ml.driver_route_profile import classify_route
    analysis = {"residential": {"flat": 40.0, "up": 2.0, "down": 2.0},
                "primary": {"flat": 60.0, "up": 5.0, "down": 5.0}}
    assert classify_route(analysis) == "urban"


def test_classify_route_empty_returns_mixed():
    from app.core.ml.driver_route_profile import classify_route
    assert classify_route({}) == "mixed"


@pytest.mark.asyncio
async def test_coefficient_returns_neutral_when_insufficient_data():
    """Must return 1.0 when fewer than min_trips exist."""
    with patch("app.core.ml.driver_route_profile.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.sefer_repo.get_driver_trips_by_route_type = AsyncMock(
            return_value=[]  # 0 trips < min_trips=5
        )
        mock_uow_cls.return_value = mock_uow

        from app.core.ml.driver_route_profile import get_driver_route_coefficient
        result = await get_driver_route_coefficient(sofor_id=1, route_type="highway_dominant")

    assert result == 1.0


@pytest.mark.asyncio
async def test_coefficient_returns_median_ratio():
    """With enough trips, must return median of gercek/tahmini ratios."""
    trips = [
        {"gercek_tuketim": 42.0, "tahmini_tuketim": 40.0},
        {"gercek_tuketim": 44.0, "tahmini_tuketim": 40.0},
        {"gercek_tuketim": 43.0, "tahmini_tuketim": 40.0},
        {"gercek_tuketim": 41.0, "tahmini_tuketim": 40.0},
        {"gercek_tuketim": 40.0, "tahmini_tuketim": 40.0},
    ]
    # Ratios: 1.05, 1.10, 1.075, 1.025, 1.00 → median ≈ 1.05

    with patch("app.core.ml.driver_route_profile.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.sefer_repo.get_driver_trips_by_route_type = AsyncMock(return_value=trips)
        mock_uow_cls.return_value = mock_uow

        from app.core.ml.driver_route_profile import get_driver_route_coefficient
        result = await get_driver_route_coefficient(sofor_id=1, route_type="highway_dominant")

    assert 1.0 <= result <= 1.15
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest app/tests/unit/test_driver_route_profile.py -v --tb=short
```

Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/core/ml/driver_route_profile.py`**

```python
"""Şoför × güzergah tipi profili — per-type consumption coefficient."""
from __future__ import annotations

import statistics
from typing import Optional

ROUTE_TYPES = ["highway_dominant", "mountain", "urban", "mixed"]


def classify_route(route_analysis: dict) -> str:
    """Güzergahı 4 kategoriden birine atar."""
    total = sum(
        sum(float((v or {}).get(k, 0) or 0) for k in ("flat", "up", "down"))
        for v in route_analysis.values()
        if isinstance(v, dict)
    )
    if total == 0:
        return "mixed"

    motorway_km = sum(
        float((route_analysis.get("motorway") or {}).get(k, 0) or 0)
        for k in ("flat", "up", "down")
    )
    ascent = float(route_analysis.get("ascent_m") or 0)
    urban_km = sum(
        float((route_analysis.get("residential") or {}).get(k, 0) or 0)
        for k in ("flat", "up", "down")
    )

    if motorway_km / total > 0.6:
        return "highway_dominant"
    if ascent / max(total, 1) > 15:
        return "mountain"
    if urban_km / total > 0.3:
        return "urban"
    return "mixed"


async def get_driver_route_coefficient(
    sofor_id: int,
    route_type: str,
    min_trips: int = 5,
) -> float:
    """Şoförün belirli güzergah tipindeki tüketim sapma katsayısı.

    Yeterli veri yoksa 1.0 döndürür (nötr — tahmine dokunmaz).
    """
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        trips = await uow.sefer_repo.get_driver_trips_by_route_type(
            sofor_id=sofor_id, route_type=route_type, limit=50
        )

    if len(trips) < min_trips:
        return 1.0

    ratios = [
        t["gercek_tuketim"] / t["tahmini_tuketim"]
        for t in trips
        if t.get("gercek_tuketim") and t.get("tahmini_tuketim")
        and t["tahmini_tuketim"] > 0
    ]
    return round(statistics.median(ratios), 3) if ratios else 1.0
```

- [ ] **Step 4: Add `get_driver_trips_by_route_type()` to `sefer_repo.py`**

In `app/database/repositories/sefer_repo.py`, after `get_with_route_analysis()`, add:

```python
    async def get_driver_trips_by_route_type(
        self,
        sofor_id: int,
        route_type: str,
        limit: int = 50,
    ) -> list[dict]:
        """Şofore ait, belirtilen güzergah tipine sahip tamamlanmış seferleri döndürür.

        route_type sınıflandırması caller tarafından yapılır (driver_route_profile.classify_route).
        Bu metod route_type'ı sefer.rota_detay JSON'undan dinamik filtreler, ya da
        caller classify_route() + Python filtre aşamasında kullanır.
        """
        import datetime

        from sqlalchemy import select

        from app.database.models import Sefer

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        async with self._get_session() as session:
            result = await session.execute(
                select(Sefer)
                .where(
                    Sefer.sofor_id == sofor_id,
                    Sefer.gercek_tuketim.isnot(None),
                    Sefer.tahmini_tuketim.isnot(None),
                    Sefer.route_analysis.isnot(None),
                    Sefer.created_at >= cutoff,
                    ~Sefer.is_deleted,
                )
                .order_by(Sefer.created_at.desc())
                .limit(limit)
            )
            from app.core.ml.driver_route_profile import classify_route
            return [
                {
                    "id": s.id,
                    "gercek_tuketim": s.gercek_tuketim,
                    "tahmini_tuketim": s.tahmini_tuketim,
                }
                for s in result.scalars().all()
                if classify_route(s.route_analysis or {}) == route_type
            ]
```

- [ ] **Step 5: Run driver route profile tests**

```bash
pytest app/tests/unit/test_driver_route_profile.py -v --tb=short
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Run full unit suite**

```bash
pytest -m "unit or not integration" -q --tb=short --ignore=app/tests/integration
```

Expected: No new failures.

- [ ] **Step 7: Commit**

```bash
git add app/core/ml/driver_route_profile.py app/database/repositories/sefer_repo.py app/tests/unit/test_driver_route_profile.py
git commit -m "feat(ml): add driver × route-type coefficient skeleton (Phase 7)

Classifies routes into highway_dominant/mountain/urban/mixed.
Returns neutral 1.0 until ≥5 trips per type exist.
sefer_repo.get_driver_trips_by_route_type() filters by route classification."
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|-------------|------|
| `error_digest` `_redis` → `redis` | Task 1 ✓ |
| CI Telegram failure notification | Task 2 ✓ |
| Sentry DSN production warning | Task 3 ✓ |
| ML hız profili features (3 new) | Task 4 ✓ |
| Route similarity engine + sefer_repo method | Task 5 ✓ |
| Driver × route profile skeleton + sefer_repo method | Task 6 ✓ |

### Placeholder Scan

No TBDs, TODOs, or "similar to Task N" references. All code blocks are complete.

### Type Consistency

- `encode_route` returns `np.ndarray` (float32, shape (8,)) — consistent with `cosine_similarity` signature
- `find_similar_trips` returns `List[Dict]` — consistent in both module and tests
- `get_with_route_analysis` / `get_driver_trips_by_route_type` return `list[dict]` — consistent with other `sefer_repo` methods
- `classify_route` called from `get_driver_trips_by_route_type` — import is inside the function body to avoid circular import with `driver_route_profile → sefer_repo → driver_route_profile`

### Risk Notes

- **Task 4 (ML features):** `_feature_hash` will change. Existing trained `.pkl` models in `app/core/ml/models/` will be rejected and retraining queued. Cold-start physics fallback (weight 0.80) is safe.
- **Task 6 (sefer_repo import):** `get_driver_trips_by_route_type` imports `classify_route` inside the function body to avoid circular import — both files import from each other's domain.
