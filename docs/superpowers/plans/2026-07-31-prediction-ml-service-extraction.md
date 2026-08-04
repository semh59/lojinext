# prediction_ml Service Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `v2/modules/prediction_ml` into an independently-deployed FastAPI service (`v2/services/prediction_ml_service/`), reached over HTTP from the main backend via a feature-flagged thin client, with zero call-site changes across its 18 existing consumers.

**Architecture:** Mechanical move of `domain/`/`application/`/`infrastructure/` into the new service (own Dockerfile, own `requirements.txt`, own Celery worker/beat for training tasks), keeping `v2/modules/prediction_ml/public.py`'s function signatures byte-identical. `public.py` becomes an HTTP client wrapped in the existing `with_async_retry` + `CircuitBreakerRegistry` resilience primitives, gated by a `PREDICTION_ML_REMOTE` flag (default `false`) so rollout is reversible at any point.

**Tech Stack:** FastAPI, httpx, Celery, Redis, PostgreSQL (role `m_prediction_ml`, already exists), Docker Compose, existing `X-Internal-Token` internal-auth pattern.

## Global Constraints

- `v2/modules/prediction_ml/public.py`'s existing function signatures (see module's own `CLAUDE.md` "Public API" section) MUST NOT change — 18 consumer files across 7 modules call these directly today and must require zero changes.
- The sefer-create path (`SeferFuelEstimator`) has a 2.5s total budget — any new network hop must degrade to the existing "save without a prediction" fallback on timeout/failure, never block or 500.
- No behavior change from the mechanical move itself — only the 3 explicitly-scoped improvements (dead code removal, model-version cache invalidation via Redis, `fit()` split) change behavior, and each must leave existing tests green.
- Every task must be verified with real command output (pytest, docker, curl) before being marked done — no "should work" claims.
- Code identifiers/comments/commit messages in English; conversation with the user in Turkish (per project convention).

---

### Task 1: Scaffold the new service directory

**Files:**
- Create: `v2/services/prediction_ml_service/Dockerfile`
- Create: `v2/services/prediction_ml_service/requirements.txt`
- Create: `v2/services/prediction_ml_service/main.py`
- Create: `v2/services/prediction_ml_service/CLAUDE.md`

**Interfaces:**
- Produces: a runnable (but empty-router) FastAPI app on port `8002`, health-checked via `GET /health`, matching `v2/services/ocr_service/main.py`'s lifespan/auth pattern.

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
numpy>=1.26.0
pandas>=2.2.0
scikit-learn>=1.4.0
xgboost>=2.0.0
lightgbm>=4.0.0
scipy>=1.12.0
statsmodels>=0.14.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
redis>=5.0.0
celery>=5.3.0
```

(Version floors copied from `app/requirements.txt`'s existing ML dependency block — verify with `grep -iE "scikit|xgboost|lightgbm|statsmodels|numpy|pandas|scipy|celery|redis|asyncpg" app/requirements.txt` and match exact pins if the root file pins rather than floors.)

- [ ] **Step 2: Create `Dockerfile`** (mirrors `v2/services/ocr_service/Dockerfile`, no OCR-specific apt packages needed)

```dockerfile
FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

- [ ] **Step 3: Create `main.py`** with health check + internal-auth dependency (business routers added in Task 5)

```python
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

_INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")


def check_internal_auth(x_internal_token: str | None = Header(default=None)) -> None:
    """Validate X-Internal-Token when INTERNAL_API_SECRET is configured.

    Mirrors admin_platform/api/internal_routes.py's existing check --
    same secret, same header name, so no new auth mechanism is introduced.
    """
    if not _INTERNAL_SECRET:
        return  # Auth disabled (dev / unset)
    if x_internal_token != _INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Create `CLAUDE.md`** documenting the service's scope (mirrors `v2/services/ocr_service/CLAUDE.md`'s structure — responsibility boundary, what it does NOT do, auth, how it's tested)

```markdown
# Service: prediction_ml_service

Standalone FastAPI service hosting the fuel-consumption ML pipeline
(5-model ensemble, physics fallback, Kalman, ARIMA) previously in-process
inside `v2/modules/prediction_ml`. Reached by the main backend over HTTP
via `v2/modules/prediction_ml/public.py`'s thin client (feature-flagged:
`PREDICTION_ML_REMOTE`, see root CLAUDE.md).

Not publicly routed (no Traefik rule, no host port) -- internal Docker
network only, same pattern as `ocr_service`/`telegram_bot`.

Auth: `X-Internal-Token` header, matching `INTERNAL_API_SECRET` -- same
secret and mechanism the telegram bot services already use.

Owns its own Celery worker + beat schedule for training tasks (moved
from the main backend's `celery_app.py` in Task 8).
```

- [ ] **Step 5: Verify the scaffold builds and starts**

```bash
docker build -t prediction-ml-service-scaffold v2/services/prediction_ml_service/
docker run --rm -d --name pml-scaffold-test -p 8002:8002 prediction-ml-service-scaffold
sleep 3
curl -sf http://localhost:8002/health
docker stop pml-scaffold-test
```

Expected: `{"status": "ok"}` printed, container starts without error.

- [ ] **Step 6: Commit**

```bash
git add v2/services/prediction_ml_service/
git commit -m "feat(prediction-ml-service): scaffold new standalone service"
```

---

### Task 2: Delete verified-dead code (Improvement 1)

**Files:**
- Delete: `v2/modules/prediction_ml/domain/kalman_estimator.py`
- Delete: `v2/modules/prediction_ml/domain/lightgbm_predictor.py`
- Delete: `v2/modules/prediction_ml/domain/benchmark.py`
- Modify: `v2/modules/prediction_ml/domain/physics_fuel_predictor.py` (remove `HybridFuelPredictor` class only, keep `PhysicsBasedFuelPredictor`/`VehicleSpecs`/`RouteConditions`/`FuelPrediction`)
- Modify: `v2/modules/prediction_ml/public.py` (remove exports: `KalmanFuelEstimator`, `KalmanEstimatorService`, `get_kalman_service`, `LightGBMFuelPredictor`, `LightGBMAnomalyClassifier`, `HybridFuelPredictor`, and any `MLBenchmark`/`ABTestFramework`/`EnsembleBenchmark` exports)
- Delete test files whose only subject is the deleted code (find via `grep -rl` in the step below — do not guess names)

**Interfaces:**
- Produces: nothing new (pure removal) — `public.py`'s remaining exports are unchanged for every symbol used by the 18 real consumer files.

- [ ] **Step 1: Re-verify zero callers exist before deleting anything**

```bash
for sym in KalmanEstimatorService get_kalman_service HybridFuelPredictor \
           LightGBMFuelPredictor LightGBMAnomalyClassifier \
           MLBenchmark ABTestFramework EnsembleBenchmark; do
  echo "=== $sym ==="
  grep -rl "$sym" v2/ app/ --include="*.py" | grep -v "/domain/\|test_"
done
```

Expected: no output for any symbol except `HybridFuelPredictor` appearing only in `public.py`'s own export list (a re-export, not a real caller). If ANY of these greps returns a real caller file, STOP and report to the user before deleting that symbol — the design's dead-code claim was based on a point-in-time audit and must be re-confirmed here.

- [ ] **Step 2: Find and list the dedicated test files for these classes**

```bash
grep -rl "KalmanEstimatorService\|LightGBMFuelPredictor\|LightGBMAnomalyClassifier\|MLBenchmark\|ABTestFramework\|EnsembleBenchmark\|HybridFuelPredictor" app/tests/
```

Record the resulting file list (expected: `test_kalman_estimator*.py`, `test_lightgbm_predictor*.py`, `test_ml_reliability.py`, `test_ml_audit.py`, and any `HybridFuelPredictor`-specific test functions inside `test_physics_fuel_predictor.py` — the latter needs a partial edit, not a full-file delete, since that file also tests the kept `PhysicsBasedFuelPredictor`).

- [ ] **Step 3: Delete the fully-dead files**

```bash
git rm v2/modules/prediction_ml/domain/kalman_estimator.py
git rm v2/modules/prediction_ml/domain/lightgbm_predictor.py
git rm v2/modules/prediction_ml/domain/benchmark.py
# Repeat git rm for each dedicated test file found in Step 2 that is
# ENTIRELY about deleted code (test_ml_reliability.py / test_ml_audit.py
# per the module's own CLAUDE.md -- confirm each file's full content is
# in-scope before removing; do not remove a file that also covers
# still-live code).
```

- [ ] **Step 4: Remove `HybridFuelPredictor` from `physics_fuel_predictor.py`**

Open the file, delete the `class HybridFuelPredictor:` definition and its docstring block only. Keep `PhysicsBasedFuelPredictor`, `VehicleSpecs`, `RouteConditions`, `FuelPrediction` untouched.

- [ ] **Step 5: Remove the deleted symbols from `public.py`'s export list**

Open `v2/modules/prediction_ml/public.py`, remove the import lines and `__all__` entries for: `KalmanFuelEstimator`, `KalmanEstimatorService`, `get_kalman_service`, `LightGBMFuelPredictor`, `LightGBMAnomalyClassifier`, `HybridFuelPredictor`, and any benchmark classes.

- [ ] **Step 6: Run the module's full test suite to confirm nothing broke**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/ -q"  # pragma: allowlist secret
```

Expected: all remaining tests pass (deleted test files no longer collected, no import errors from the removed symbols anywhere else in the codebase).

- [ ] **Step 7: Run ruff + mypy on the touched files**

```bash
ruff check v2/modules/prediction_ml/domain/physics_fuel_predictor.py v2/modules/prediction_ml/public.py --select E,F,W,I
mypy v2/modules/prediction_ml/ --ignore-missing-imports --no-strict-optional
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(prediction_ml): remove verified zero-caller dead code

KalmanEstimatorService, HybridFuelPredictor, LightGBMFuelPredictor/
LightGBMAnomalyClassifier, and domain/benchmark.py's 3 classes had zero
prod callers (re-verified via grep, matching the module's own CLAUDE.md
audit) -- removed rather than carried into the new standalone service."
```

---

### Task 3: Split `ensemble_core.py::fit()` (Improvement 3, CC=61 → 4 helpers)

**Files:**
- Modify: `v2/modules/prediction_ml/domain/ensemble_core.py:544-923` (the `fit` method body)

**Interfaces:**
- Consumes: `EnsembleFuelPredictor`'s existing instance attributes (`self.scaler`, `self.gb_model`, `self.rf_model`, `self.xgb_model`, `self.lgb_model`, `self.strategy`, `self.weights`, `self.physics_weight`, `self.training_stats`, `self.is_trained`, `self._model_lock`, `self.FEATURE_NAMES`, `self.DEFAULT_WEIGHTS`, `self.prepare_features()`, `self._get_physics_predictions()`).
- Produces: `fit(self, seferler, y_actual=None) -> Dict` — **same public signature and return shape**, now a thin orchestrator calling 3 new private instance methods:
  - `_prepare_training_data(self, seferler, y_actual) -> tuple[list, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | dict` — returns either the early-exit error dict (`{"success": False, "error": ...}`) or `(seferler, X_scaled, y_train_split_data, sample_weights, y_physics)` bundled as needed by the next step. (Covers: y_actual defaulting, min-10-rows guard, sklearn-available guard, outlier guard, temporal weighting, feature prep, label-leak guard, temporal sort, train/test split.)
  - `_train_component_models(self, X_train, y_train, X_test, y_test, sw_train) -> dict` — returns `{"gb_test_r2", "rf_test_r2", "xgb_r2", "lgb_r2", "gb_cv_mean", "feat_imp"}`. (Covers: gb/rf/xgb/lgb `.fit()` calls, feature importance, cross-validation.)
  - `_compute_ensemble_weights(self, model_scores: dict) -> dict` — returns the normalized `weights` dict. (Covers: strategy-based weighting, physics-weight base, normalization, fallback-to-physics-only branch.)
  - `_evaluate_and_build_stats(self, X_test, y_test, y_physics, y_train, use_split, model_scores, weights) -> dict` — returns the final `training_stats` dict (same shape as today's). (Covers: weighted final predictions, error/MAE/RMSE/R2/MAPE calculation, `training_stats` assembly.)

- [ ] **Step 1: Write a characterization test capturing today's exact output shape**

Before touching `fit()`, add a test that trains on a small deterministic dataset and snapshots the full returned dict (this test must pass BEFORE and AFTER the split — it is the safety net):

```python
# app/tests/unit/test_ml/test_ensemble_core_fit_split.py
import numpy as np
import pytest

from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

pytestmark = pytest.mark.unit


def _make_seferler(n=20):
    return [
        {
            "tuketim": 30.0 + (i % 5),
            "tarih": f"2026-0{1 + i % 6}-15",
            "mesafe_km": 200.0 + i * 10,
            "ton": 18.0,
        }
        for i in range(n)
    ]


def test_fit_returns_success_shape_before_and_after_split():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(20))

    assert result["success"] is True
    assert "sample_count" in result
    assert "ensemble_r2" in result
    assert "measurements" in result
    assert set(result["measurements"].keys()) == {"mae", "rmse", "mape", "physics_mae"}
    assert "metrics" in result
    assert "feature_importance" in result
    assert "model_weights" in result
    assert "is_honest_test" in result
    assert predictor.is_trained is True


def test_fit_insufficient_data_returns_error():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(3))

    assert result["success"] is False
    assert "Yetersiz veri" in result["error"]
```

- [ ] **Step 2: Run it against the CURRENT (unsplit) `fit()` to confirm it passes**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_ensemble_core_fit_split.py -v"  # pragma: allowlist secret
```

Expected: 2 passed. This proves the characterization test is valid before refactoring.

- [ ] **Step 3: Extract `_prepare_training_data`**

Move lines 557-716 (from `if y_actual is None:` through the `else:` branch of the train/test split, i.e. everything up to but not including `# ML modelleri eğit`) into a new private method. Keep every line of logic identical — only wrap it in a method boundary and `return` the tuple of locals the next stage needs, or the early-exit error dict.

- [ ] **Step 4: Extract `_train_component_models`**

Move lines 717-777 (gb/rf fit through `gb_cv_mean` calculation) into the second method, taking `X_train, y_train, X_test, y_test, sw_train` as params, returning a dict of the computed scores/importances.

- [ ] **Step 5: Extract `_compute_ensemble_weights`**

Move lines 779-827 (strategy-based weighting through `self.physics_weight = ...`) into the third method, taking the model-scores dict, returning the normalized weights dict AND setting `self.weights`/`self.physics_weight` as a side effect (same as today — these are real instance-state mutations, not pure).

- [ ] **Step 6: Extract `_evaluate_and_build_stats`**

Move lines 829-913 (extended metrics through `training_stats` assembly) into the fourth method.

- [ ] **Step 7: Rewrite `fit()` as the orchestrator**

```python
def fit(self, seferler: List[Dict], y_actual: Optional[np.ndarray] = None) -> Dict:
    """
    Model eğitimi

    1. Feature'ları hazırla
    2. Fizik tahminleri al
    3. Residual (hata) hesapla
    4. ML ile residual öğren
    5. Ağırlıkları belirle
    """
    prep = self._prepare_training_data(seferler, y_actual)
    if isinstance(prep, dict):  # early-exit error
        return prep
    (seferler, X_train, X_test, y_train, y_test, sw_train,
     y_physics, use_split) = prep

    if not SKLEARN_AVAILABLE:
        return {"success": False, "error": "sklearn kütüphanesi yüklü değil."}

    try:
        with self._model_lock:
            self.is_trained = False
            model_scores = self._train_component_models(
                X_train, y_train, X_test, y_test, sw_train
            )
            weights = self._compute_ensemble_weights(model_scores)
            self.training_stats = self._evaluate_and_build_stats(
                X_test, y_test, y_physics, y_train, use_split, model_scores, weights
            )
            self.is_trained = True
        return {"success": True, **self.training_stats}
    except Exception as e:
        logger.error(f"Ensemble training error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

(Exact tuple contents in `prep` and `model_scores`/`weights` dict keys must be reconciled against the real extracted code in Steps 3-6 — this is a structural skeleton; the implementer fills parameter/return shapes to match exactly what each extracted block reads and writes, verified by Step 8.)

- [ ] **Step 8: Run the characterization test again**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_ensemble_core_fit_split.py -v"  # pragma: allowlist secret
```

Expected: same 2 passed, byte-identical assertions to Step 2.

- [ ] **Step 9: Run the full ensemble_core test suite**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/ -k 'ensemble_core or ensemble_service' -v"  # pragma: allowlist secret
```

Expected: all pass, no behavior change.

- [ ] **Step 10: Verify complexity actually dropped**

```bash
docker exec lojinext-backend-1 sh -c "cd /app && pip install --quiet radon && radon cc v2/modules/prediction_ml/domain/ensemble_core.py -s | grep -A1 'fit\|_prepare_training_data\|_train_component_models\|_compute_ensemble_weights\|_evaluate_and_build_stats'"
```

Expected: no single method above roughly CC 15-20 (down from 61).

- [ ] **Step 11: Commit**

```bash
git add v2/modules/prediction_ml/domain/ensemble_core.py app/tests/unit/test_ml/test_ensemble_core_fit_split.py
git commit -m "refactor(prediction_ml): split ensemble_core.fit() (CC=61) into 4 helpers

Behavior unchanged (characterization test passes identically before
and after). Extracted: _prepare_training_data, _train_component_models,
_compute_ensemble_weights, _evaluate_and_build_stats."
```

---

### Task 4: Model-version Redis invalidation signal (Improvement 2)

**Files:**
- Modify: `v2/modules/prediction_ml/application/ensemble_service.py` (`get_predictor`, and wherever a training success persists a new model — the `_register_model_version`/`train_for_vehicle` call sites)
- Test: `app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py` (new)

**Interfaces:**
- Consumes: `platform_infra.public.get_cache_manager()` (existing `CacheManager`, already used by other modules — real Redis in tests via the existing `mock_redis_for_cache_manager` autouse fixture, which despite its name now wraps a REAL Redis per `app/tests/conftest.py`'s own docstring).
- Produces: `EnsemblePredictorService._get_model_version(arac_id: int) -> int` (reads `predictor_version:{arac_id}` from Redis, defaults to `0` if unset) and `_bump_model_version(arac_id: int) -> None` (INCRs it) — both new private methods. `get_predictor()`'s cache-hit branch now additionally compares the in-memory predictor's own tracked version against Redis's current version and reloads from disk if stale.

- [ ] **Step 1: Write the failing test**

```python
# app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py
import pytest

from v2.modules.prediction_ml.application.ensemble_service import (
    EnsemblePredictorService,
)

pytestmark = pytest.mark.unit


async def test_bump_model_version_increments_and_is_readable():
    svc = EnsemblePredictorService()
    v0 = await svc._get_model_version(999)
    assert v0 == 0

    await svc._bump_model_version(999)
    v1 = await svc._get_model_version(999)
    assert v1 == 1

    await svc._bump_model_version(999)
    v2 = await svc._get_model_version(999)
    assert v2 == 2


def test_get_predictor_reloads_when_redis_version_is_newer(monkeypatch):
    svc = EnsemblePredictorService()
    # Seed an in-memory cached predictor at version 0
    predictor = svc.get_predictor(998)
    predictor._cached_model_version = 0

    # Simulate another worker having trained a newer version
    import asyncio

    asyncio.get_event_loop().run_until_complete(svc._bump_model_version(998))

    reloaded = svc.get_predictor(998)
    assert reloaded._cached_model_version == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
docker cp app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py lojinext-backend-1:/app/app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py -v"  # pragma: allowlist secret
```

Expected: FAIL with `AttributeError: '_get_model_version'`.

- [ ] **Step 3: Implement `_get_model_version`/`_bump_model_version` in `ensemble_service.py`**

```python
async def _get_model_version(self, arac_id: int) -> int:
    from v2.modules.platform_infra.public import get_cache_manager

    cache = get_cache_manager()
    raw = await cache.get(f"predictor_version:{arac_id}")
    return int(raw) if raw is not None else 0

async def _bump_model_version(self, arac_id: int) -> None:
    from v2.modules.platform_infra.public import get_cache_manager

    cache = get_cache_manager()
    current = await self._get_model_version(arac_id)
    await cache.set(f"predictor_version:{arac_id}", str(current + 1))
```

(Exact `CacheManager` method names must be confirmed against `v2/modules/platform_infra/cache/cache_manager.py`'s real public methods — `get`/`set` are the expected async signatures based on its existing usage elsewhere in the codebase; adjust if the real API differs, e.g. `aget`/`aset`.)

- [ ] **Step 4: Add `_cached_model_version` tracking to `get_predictor()`**

In `EnsembleFuelPredictor.__init__` (or wherever the predictor object is constructed), add `self._cached_model_version: int = 0`. In `get_predictor()`'s cache-hit branch (the `if arac_id in self.predictors:` block), before returning, compare against Redis:

```python
if arac_id in self.predictors:
    self.predictors.move_to_end(arac_id)
    cached = self.predictors[arac_id]
    current_version = asyncio.get_event_loop().run_until_complete(
        self._get_model_version(arac_id)
    ) if not asyncio.get_event_loop().is_running() else None
    # (Real implementation must handle get_predictor's existing sync-vs-async
    # calling contexts -- get_predictor() is called from both sync and async
    # call sites today; the implementer must check every existing call site
    # before choosing between making get_predictor async or adding a
    # separate async-safe variant. This is the one genuinely open design
    # question in this task -- flag it to the user if the sync call sites
    # can't cleanly await.)
    if cached._cached_model_version >= current_version:
        return cached
    # else fall through to reload from disk below
```

- [ ] **Step 5: Call `_bump_model_version` after every successful training persist**

Find the call site(s) in `ensemble_service.py` where `_register_model_version()` is called after a successful `train_for_vehicle`/`train_general_model` (per the module's own CLAUDE.md, this is already a single free function called from those two training methods). Add `await self._bump_model_version(arac_id)` immediately after each successful `_register_model_version()` call.

- [ ] **Step 6: Run the tests again**

```bash
docker cp v2/modules/prediction_ml/application/ensemble_service.py lojinext-backend-1:/app/v2/modules/prediction_ml/application/ensemble_service.py
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py -v"  # pragma: allowlist secret
```

Expected: both tests pass, against real Redis (the existing `mock_redis_for_cache_manager` autouse fixture is real Redis per its own docstring, not a mock).

- [ ] **Step 7: Run the full ensemble_service suite for regressions**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/ -k ensemble_service -v"  # pragma: allowlist secret
```

- [ ] **Step 8: Commit**

```bash
git add v2/modules/prediction_ml/application/ensemble_service.py app/tests/unit/test_ml/test_ensemble_service_cache_invalidation.py
git commit -m "feat(prediction_ml): Redis-backed model-version cache invalidation

Each worker/replica's in-memory+disk predictor cache now checks a
shared Redis version counter (predictor_version:{arac_id}) on cache
hit, reloading from disk when a newer version was trained elsewhere.
Fixes the documented multi-worker LRU staleness gap (module CLAUDE.md
§Gotchas) -- more important once this module scales as its own
service with multiple replicas."
```

---

### Task 5: Move domain/application/infrastructure code to the new service

**Files:**
- Move (via `git mv`): every file under `v2/modules/prediction_ml/{domain,application,infrastructure}/` (post Task 2/3/4 edits) to `v2/services/prediction_ml_service/{domain,application,infrastructure}/`
- Move: `v2/modules/prediction_ml/schemas.py`, `v2/modules/prediction_ml/events.py`
- Move: `app/tests/unit/test_ml/*` to `v2/services/prediction_ml_service/tests/`
- Modify: every moved file's cross-module imports (e.g. `from v2.modules.fleet.public import ...` stays as-is — cross-module imports to OTHER v2 modules do not change, only imports that referenced `v2.modules.prediction_ml.*` internally need their prefix updated to the new service's own package root)
- Create: `v2/services/prediction_ml_service/routers/*.py` (thin FastAPI routers wrapping the moved application-layer functions)
- Modify: `v2/services/prediction_ml_service/main.py` (register the new routers)

**Interfaces:**
- Produces: `POST /predict` (wraps `PredictionService.predict_consumption`), `POST /predict/explain` (wraps `explain_consumption`), `POST /predict/batch` (wraps `EnsemblePredictorService.predict_batch`), `POST /train/{arac_id}` (wraps `train_for_vehicle`), `POST /train/general` (wraps `train_general_model`), `GET /route-similarity` (wraps `find_similar_trips`) — request/response bodies are the JSON-serializable equivalent of each wrapped function's existing dict-in/dict-out contract (these functions already return plain dicts today, per the module's own public.py signatures, so no new serialization logic is needed beyond FastAPI's automatic JSON handling).

- [ ] **Step 1: Move the directories, preserving git history**

```bash
mkdir -p v2/services/prediction_ml_service/{domain,application,infrastructure}
git mv v2/modules/prediction_ml/domain/*.py v2/services/prediction_ml_service/domain/
git mv v2/modules/prediction_ml/application/*.py v2/services/prediction_ml_service/application/
git mv v2/modules/prediction_ml/infrastructure/*.py v2/services/prediction_ml_service/infrastructure/
git mv v2/modules/prediction_ml/schemas.py v2/services/prediction_ml_service/schemas.py
git mv v2/modules/prediction_ml/events.py v2/services/prediction_ml_service/events.py
mkdir -p v2/services/prediction_ml_service/tests
git mv app/tests/unit/test_ml/*.py v2/services/prediction_ml_service/tests/
```

- [ ] **Step 2: Update internal import paths in every moved file**

```bash
grep -rl "v2\.modules\.prediction_ml\.\(domain\|application\|infrastructure\|schemas\|events\)" v2/services/prediction_ml_service/ | \
  xargs sed -i 's/v2\.modules\.prediction_ml\./prediction_ml_service./g'
```

(This assumes the new service's package root is importable as `prediction_ml_service` — set via the service's own `PYTHONPATH=/app` in its Dockerfile, matching how the main backend's Dockerfile sets `PYTHONPATH=/app` for `v2`/`app` roots. Do NOT rewrite imports of OTHER v2 modules like `v2.modules.fleet.public` — those stay pointed at the main backend's package, since this new service still needs network/DB access to fleet/driver/etc. data. **This is the single largest open risk in this task**: the moved code currently imports `v2.modules.fleet.public`, `v2.modules.driver.public`, `v2.modules.analytics_executive.public`, `v2.modules.ai_assistant.public` DIRECTLY as in-process Python imports — those modules physically live in the MAIN backend's codebase, not the new service's. Task 5b below resolves this.)

- [x] **Step 2b: Cross-module data access — RESOLVED, Option B (HTTP to main backend), user decision 2026-08-04**

The new service cannot import `v2.modules.fleet.public`/`v2.modules.driver.public`/`v2.modules.analytics_executive.public`/`v2.modules.ai_assistant.public` directly (those packages physically live in the main backend's codebase). User chose Option B over the plan's original Option A recommendation: the new service reaches this data over HTTP against new internal endpoints on the MAIN backend, matching the `X-Internal-Token`/`INTERNAL_API_SECRET` pattern already used by the telegram bot services (`admin_platform/api/internal_routes.py`).

**⚠️ CORRECTION (2026-08-04, mid-Task-5 re-audit): the original "6 operations, 3 files" table above was wrong — verified directly against the moved code, not the module's CLAUDE.md prose.** The real cross-module surface is 3 categories, discovered by grepping every `from v2.modules.<X>.public/schemas/infrastructure` import inside the already-moved `domain/application/infrastructure` tree:

**Category 1 — `platform_infra` + `shared_kernel` (12 + several refs): VENDOR, not HTTP.** These are the project's own "freely shared, never import business modules back" infra layer (`get_logger`, `get_cache_manager`, `AsyncSessionLocal`, `get_container`, `UnitOfWork`, `log_audit_event`, etc. — used throughout `ensemble_service.py`, `ml_service.py`, `model_warmup.py`, `physics_handler.py`, `trainer.py`, `time_series_service.py`). User decision: copy `v2/modules/platform_infra/` and `v2/modules/shared_kernel/` source into the new service's Docker image too (build context becomes the repo root, not the service subdir — see Task 9 revision below), keeping their original `v2.modules.platform_infra.*`/`v2.modules.shared_kernel.*` import paths unchanged in the moved code (no sed rewrite needed for these two). Two physical copies of the same source, no network hop, no behavior change — acceptable because neither package ever imports a business module back (verified in their own CLAUDE.md).

**Category 2 — pure/deterministic helper: vendor the function, not the module.** `route_simulation.public.get_weather_service().get_seasonal_factor(date)` (`ensemble_service.py:365,606`) is a pure date→float calendar calculation with zero DB/HTTP dependency (verified by reading `WeatherService.get_seasonal_factor`) — copying the whole `route_simulation` module (which also has heavy Mapbox/Redis-dependent code) would be wrong. Instead: copy just this one function into `v2/services/prediction_ml_service/domain/seasonal_factor.py`, call sites updated to import it locally.

**Category 3 — genuine business-module data access: Option B (HTTP), extended table.** The real operations (re-verified line-by-line, `get_model_params`/`classify_route` from the stale CLAUDE.md are confirmed dead — zero callers):

| # | Current call | New internal endpoint (main backend) | Consumer in new service |
|---|---|---|---|
| 1 | `uow.arac_repo.get_by_id(arac_id)` (`ensemble_service.py:340,575`) | `GET /api/v1/internal/fleet/araclar/{arac_id}` (`v2/modules/fleet/api/internal_routes.py`) | `ensemble_service.py` (train_for_vehicle, predict_consumption) |
| 2 | `uow.dorse_repo.get_by_id(dorse_id)` (`ensemble_service.py:584,586`) | `GET /api/v1/internal/fleet/dorseler/{dorse_id}` (same file) | `ensemble_service.py` (predict_consumption) |
| 3 | `get_driver_stats(sofor_id=None\|int, include_elite_score=False)` (`ensemble_service.py:331,568`, `prediction_service.py:460`) | `GET /api/v1/internal/driver/stats?sofor_id=&include_elite_score=` (`v2/modules/driver/api/internal_routes.py`) | `ensemble_service.py`, `prediction_service.py` |
| 4 | `get_with_route_analysis(days=90, limit=200)` (`route_similarity.py:37`, **not in original table**) | `GET /api/v1/internal/driver/route-analysis-recent?days=&limit=` (same file) | `route_similarity.py::find_similar_trips` |
| 5 | `uow.sefer_repo.get_for_training(arac_id, limit=500)` (`ensemble_service.py:343`, **not in original table**) | `GET /api/v1/internal/trip/training-data/{arac_id}?limit=` (`v2/modules/trip/api/internal_routes.py`, new file) | `ensemble_service.py::train_for_vehicle` |
| 6 | `uow.sefer_repo.get_all_for_training(limit=2000)` (`ensemble_service.py:462`, **not in original table**) | `GET /api/v1/internal/trip/training-data-all?limit=` (same file) | `ensemble_service.py::train_general_model` |
| 7 | `analiz_repo.save_model_params(arac_id, result)` (`ensemble_service.py:425`, write, best-effort) | `POST /api/v1/internal/analytics/model-params` body `{"arac_id": int, "result": dict}` (`v2/modules/analytics_executive/api/internal_routes.py`) | `ensemble_service.py` |
| 8 | `uow.analiz_repo.get_daily_summary_for_ml(days, arac_id=None)` (`time_series_service.py:85`) | `GET /api/v1/internal/analytics/daily-summary?days=&arac_id=` (same file) | `time_series_service.py` |
| 9 | `get_smart_ai().teach(msg, category="tahmin_izleme")` (`prediction_service.py:431`, fire-and-forget) | `POST /api/v1/internal/ai/teach` body `{"msg": str, "category": str}` (`v2/modules/ai_assistant/api/internal_routes.py`) | `prediction_service.py` |
| 10 | `get_llm_client().chat(...)` (`infrastructure/prediction_tasks.py:27`, **not in original table** — unrelated RAG/LLM Celery task `prediction.generate`, invoked by task NAME from `v2/modules/prediction_ml/api/predictions.py:73` via `celery_app.send_task(...)`, no direct import coupling on that side) | `POST /api/v1/internal/ai/chat` body `{"messages": [...], "system_prompt": str, "max_tokens": int, "temperature": float}` (same file) | `infrastructure/prediction_tasks.py` |

**Genuinely OUT of scope for this task — moved elsewhere instead of into the new service, user decision 2026-08-04**: `application/prediction_backfill_service.py` + `infrastructure/prediction_backfill_tasks.py` call `v2.modules.trip.public.get_sefer_fuel_estimator()` — trip's OWN full sefer-estimation pipeline (Mapbox + route_simulation + this very prediction_ml service, once `PREDICTION_ML_REMOTE=true`). Wrapping that in an HTTP endpoint here would mean a nonsensical double hop (main → prediction_ml_service → main → prediction_ml_service). These two files are moved to `v2/modules/trip/application/` and `v2/modules/trip/infrastructure/` instead (trip already owns the estimator they orchestrate) — NOT part of this task's `git mv` list, handled as a separate correction before Step 3 below.

**`training_ws_manager` (admin_platform) — also not in the original audit.** `ml_service.py` pushes live training-progress updates directly to `v2.modules.admin_platform.public.training_ws_manager`, a WebSocket connection registry that only exists in the main backend's process (WS connections terminate there). User decision: convert to an HTTP callback — `ml_service.py` (in the new service) POSTs progress to a new `POST /api/v1/internal/admin/training-progress` endpoint (`v2/modules/admin_platform/api/internal_routes.py`, added to the existing file), which then calls `training_ws_manager` locally on the main backend exactly as today.

**Sub-step 3a — add the internal endpoint files on the MAIN backend** (each mirrors `admin_platform/api/internal_routes.py`'s existing `X-Internal-Token` dependency — import and reuse that same check function, do not reimplement it):
- `v2/modules/fleet/api/internal_routes.py` — endpoints #1, #2.
- `v2/modules/driver/api/internal_routes.py` — endpoints #3, #4.
- `v2/modules/trip/api/internal_routes.py` (new file) — endpoints #5, #6.
- `v2/modules/analytics_executive/api/internal_routes.py` — endpoints #7, #8.
- `v2/modules/ai_assistant/api/internal_routes.py` — endpoints #9, #10.
- `v2/modules/admin_platform/api/internal_routes.py` (existing file, add one route) — training-progress callback.

All six registered in `v2/modules/platform_infra/api_router.py` alongside each module's other routers.

Each endpoint's response model: return the SAME dict/list shape the underlying repo/function already returns today (these already return plain dicts or simple dataclasses — FastAPI serializes them automatically; do not introduce new Pydantic schemas unless a field isn't JSON-serializable as-is, e.g. a `datetime` needs `.isoformat()`).

**Sub-step 3b — new service's HTTP client**: `v2/services/prediction_ml_service/infrastructure/cross_module_client.py` — one async function per operation in the table above (`get_vehicle(arac_id)`, `get_trailer(dorse_id)`, `get_driver_stats(sofor_id=None, include_elite_score=False)`, `get_route_analysis_recent(days=90, limit=200)`, `get_training_data(arac_id, limit=500)`, `get_all_training_data(limit=2000)`, `save_model_params(arac_id, result)`, `get_daily_summary_for_ml(days, arac_id=None)`, `teach(msg, category)`, `ai_chat(messages, system_prompt, max_tokens, temperature)`, `post_training_progress(...)`), each a plain `httpx.AsyncClient` call against `settings`-configured `MAIN_BACKEND_INTERNAL_URL` (new env var, default `http://backend:8000`) with the `X-Internal-Token` header, wrapped in the same `with_async_retry` pattern used elsewhere (see Task 6 Step 3 for the exact import path once resolved there — if Task 6 hasn't run yet when this task executes, resolve the same `with_async_retry` import question here first, it's the same open question, don't guess twice). Timeouts: short (2-3s) for the read endpoints (#1-3,4,5,6,8); #7/#9/#10/training-progress are best-effort writes that already tolerate failure in the original code (wrap in try/except that logs and continues, exactly like today — do not make training fail if these are unreachable).

**Sub-step 3c — update the moved `domain`/`application` files** to call `cross_module_client.*` instead of `v2.modules.fleet.public.get_arac_repo()` etc. — replace each of the 10 call sites listed in the table above. This is the ONE place where Task 5's "mechanical move, no behavior change" framing has a real, intentional exception: these call sites necessarily change from in-process calls to HTTP calls, because that is the entire point of Option B. Every OTHER line of the moved code must still move unchanged (platform_infra/shared_kernel calls stay in-process via the vendored copy; the seasonal-factor call becomes a local import per Category 2 above).

- [ ] **Step 3: Write the FastAPI routers on the new service (as originally planned) + verify the new internal endpoints end-to-end**

(Router code as originally planned, e.g. `v2/services/prediction_ml_service/routers/predict_routes.py`:)

```python
from fastapi import APIRouter, Depends

from application.prediction_service import get_prediction_service
from main import check_internal_auth

router = APIRouter(dependencies=[Depends(check_internal_auth)])


@router.post("/predict")
async def predict(payload: dict) -> dict:
    service = get_prediction_service()
    return await service.predict_consumption(**payload)
```

(Repeat for `/predict/explain`, `/predict/batch`, `/train/{arac_id}`, `/train/general`, `/route-similarity` — each a thin pass-through to the existing application-layer function, matching its existing kwargs.)

- [ ] **Step 4: Register routers in `main.py`**

```python
from routers import predict_routes, train_routes, route_similarity_routes

app.include_router(predict_routes.router)
app.include_router(train_routes.router)
app.include_router(route_similarity_routes.router)
```

- [ ] **Step 5: Fix moved test files' import paths**

```bash
sed -i 's/from v2\.modules\.prediction_ml\./from prediction_ml_service./g; s/v2\.modules\.prediction_ml\./prediction_ml_service./g' v2/services/prediction_ml_service/tests/*.py
```

- [ ] **Step 6: Run the new service's test suite inside its own container**

```bash
docker build -t prediction-ml-service v2/services/prediction_ml_service/
docker run --rm -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" --network lojinext_lojinext_network prediction-ml-service python -m pytest tests/ -q  # pragma: allowlist secret
```

Expected: same pass count as the original `app/tests/unit/test_ml/` suite had before the move (record this number in Step 0 of this task, before moving anything, as the baseline to match).

- [ ] **Step 6b: Verify the 4 new internal endpoints on the MAIN backend directly, before testing the new service against them**

```bash
docker cp v2/modules/fleet/. lojinext-backend-1:/app/v2/modules/fleet/
docker cp v2/modules/driver/. lojinext-backend-1:/app/v2/modules/driver/
docker cp v2/modules/analytics_executive/. lojinext-backend-1:/app/v2/modules/analytics_executive/
docker cp v2/modules/ai_assistant/. lojinext-backend-1:/app/v2/modules/ai_assistant/
docker restart lojinext-backend-1
sleep 5
docker exec lojinext-backend-1 curl -sf http://localhost:8000/api/v1/internal/fleet/araclar/1 -H "X-Internal-Token: $INTERNAL_API_SECRET"
docker exec lojinext-backend-1 curl -sf "http://localhost:8000/api/v1/internal/driver/stats?include_elite_score=false" -H "X-Internal-Token: $INTERNAL_API_SECRET"
docker exec lojinext-backend-1 curl -sf "http://localhost:8000/api/v1/internal/analytics/daily-summary?days=30" -H "X-Internal-Token: $INTERNAL_API_SECRET"
docker exec lojinext-backend-1 curl -sf -X POST http://localhost:8000/api/v1/internal/ai/teach -H "Content-Type: application/json" -H "X-Internal-Token: $INTERNAL_API_SECRET" -d '{"msg": "test", "category": "tahmin_izleme"}'
```

(`$INTERNAL_API_SECRET` — read the real value from the container: `docker exec lojinext-backend-1 printenv INTERNAL_API_SECRET`; if empty, auth is disabled in this dev environment and the header can be omitted.) Expected: all 4 real HTTP responses (not 404/500) proving these endpoints are correctly wired into `api_router.py` and reach the real repos before the new service's own tests depend on them.

- [ ] **Step 7: Verify the built image starts and serves real predictions**

```bash
docker run --rm -d --name pml-integration-test -p 8002:8002 --network lojinext_lojinext_network \
  -e DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_db" \  # pragma: allowlist secret
  prediction-ml-service
sleep 5
curl -sf -X POST http://localhost:8002/predict -H "Content-Type: application/json" \
  -d '{"arac_id": 1, "mesafe_km": 200.0, "ton": 15.0}'
docker stop pml-integration-test
```

Expected: a real JSON prediction response (matching the shape `PredictionService.predict_consumption` already returns today), not a 500.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(prediction-ml-service): move domain/application/infrastructure code

Mechanical move -- v2/modules/prediction_ml's domain/application/
infrastructure now live in v2/services/prediction_ml_service/. Cross-
module data access to fleet/driver/analytics_executive/ai_assistant
resolved via [Option A/B per Step 2b]. New service exposes /predict,
/predict/explain, /predict/batch, /train/{arac_id}, /train/general,
/route-similarity, all behind X-Internal-Token auth."
```

---

### Task 6: Thin HTTP client in the old `public.py` location, feature-flagged

**Files:**
- Modify: `v2/modules/prediction_ml/public.py` (replace direct imports with an HTTP client; keep every existing function name/signature/return type identical)
- Create: `v2/modules/prediction_ml/infrastructure_client/http_client.py` (new home for the actual httpx logic, since the old `infrastructure/` moved away in Task 5)
- Modify: `app/config.py` (add `PREDICTION_ML_REMOTE: bool = False` and `PREDICTION_ML_SERVICE_URL: str = "http://prediction-ml-service:8002"`)

**Interfaces:**
- Consumes: `v2.modules.platform_infra.public.with_async_retry` (wait — confirm exact export path; `with_async_retry` currently lives in `route_simulation/infrastructure/retry.py`, not yet in `platform_infra.public` — verify via `grep -n "with_async_retry" v2/modules/platform_infra/public.py` before writing this import; if it is not exported there, import directly from `v2.modules.route_simulation.infrastructure.retry` as the existing 0-mock work in this session already did for other clients, OR copy the retry helper locally to avoid a `prediction_ml -> route_simulation` cross-module dependency that the import-linter's `public-surface-only-*` contracts would likely flag — **resolve this exact import path before writing Step 3, it is a concrete unknown, not a style choice**), `v2.modules.platform_infra.resilience.circuit_breaker.CircuitBreakerRegistry`.
- Produces: `public.py`'s existing signatures, e.g. `PredictionService.predict_consumption(arac_id, mesafe_km, ton=0.0, ...) -> dict` — behaviorally: when `settings.PREDICTION_ML_REMOTE` is `False`, delegates to nothing (old in-process code path is GONE after Task 5's move — see the note in Step 1 below, this is why the flag's `False` state needs its own fallback plan) — **this is a second concrete open design question**: since Task 5 physically moves the implementation out of this package, `PREDICTION_ML_REMOTE=False` cannot mean "run in-process" anymore unless Task 5's move is deferred until the flag defaults to `True` and is proven. Resolve by REORDERING: do not delete/move the old in-process code in Task 5; instead COPY it (temporary duplication) so both code paths exist side-by-side until Task 9 flips the default and a later cleanup task deletes the in-process copy. Update Task 5's `git mv` calls to `cp -r` instead, keeping the old files as the `False`-path fallback until Task 9 completes.

- [ ] **Step 1: Add config settings**

In `app/config.py`, near the `OCR_SERVICE_URL` block:

```python
    # prediction_ml service (internal Docker network) -- feature-flagged
    # extraction, see docs/superpowers/plans/2026-07-31-prediction-ml-
    # service-extraction.md. False = in-process (legacy path, still
    # present until this flag defaults True and is proven in CI).
    PREDICTION_ML_REMOTE: bool = False
    PREDICTION_ML_SERVICE_URL: str = "http://prediction-ml-service:8002"
```

- [ ] **Step 2: Write the failing test for the client wrapper**

```python
# app/tests/unit/test_ml/test_prediction_ml_client_flag.py
import pytest

from app.config import settings

pytestmark = pytest.mark.unit


async def test_predict_consumption_uses_inprocess_path_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "PREDICTION_ML_REMOTE", False)
    from v2.modules.prediction_ml.public import get_prediction_service

    service = get_prediction_service()
    # In-process path: no HTTP call, same object type as today
    assert type(service).__module__.startswith("v2.modules.prediction_ml")
```

- [ ] **Step 3: Verify the correct `with_async_retry` import path** (per the open question above)

```bash
grep -n "with_async_retry" v2/modules/platform_infra/public.py
```

If this returns nothing, use:
```python
from v2.modules.route_simulation.infrastructure.retry import with_async_retry
```
and check `.importlinter` for whether `prediction_ml -> route_simulation` needs an `ignore_imports` line added to `public-surface-only-route_simulation` (it should already allow this, since `retry.py` is infrastructure the whole codebase treats as a shared utility per this session's earlier `role_grants.py` investigation showing similar cross-module infra reuse) — run `lint-imports --config .importlinter` after adding the import to confirm.

- [ ] **Step 4: Implement the HTTP client wrapper in `public.py`**

```python
async def _call_prediction_ml_service(path: str, payload: dict) -> dict:
    import httpx

    from app.config import settings
    from v2.modules.platform_infra.resilience.circuit_breaker import (
        CircuitBreakerRegistry,
    )

    breaker = await CircuitBreakerRegistry.get("prediction_ml_service")

    async def _post():
        headers = {}
        if settings.INTERNAL_API_SECRET:
            headers["X-Internal-Token"] = settings.INTERNAL_API_SECRET
        async with httpx.AsyncClient(
            base_url=settings.PREDICTION_ML_SERVICE_URL, timeout=2.0
        ) as client:
            resp = await client.post(path, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    return await breaker.call(_post)
```

Wire `PredictionService.predict_consumption` (and the other public functions) to branch on `settings.PREDICTION_ML_REMOTE`:

```python
async def predict_consumption(self, arac_id: int, mesafe_km: float, **kwargs) -> dict:
    from app.config import settings

    if settings.PREDICTION_ML_REMOTE:
        try:
            return await _call_prediction_ml_service(
                "/predict", {"arac_id": arac_id, "mesafe_km": mesafe_km, **kwargs}
            )
        except Exception:
            # Same fallback as Mapbox/Open-Meteo timeouts today -- caller
            # already handles a missing prediction gracefully (tahmini_
            # tuketim=NULL path documented in root CLAUDE.md).
            return {"tahmini_tuketim": None, "source": "fallback_network_error"}
    # Legacy in-process path (kept until Task 9 flips the default) --
    # unchanged from before this task.
    ...
```

- [ ] **Step 5: Run the flag-off test**

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_prediction_ml_client_flag.py -v"  # pragma: allowlist secret
```

- [ ] **Step 6: Write and run the flag-on integration test** (requires the built `prediction-ml-service` image running)

```bash
docker compose up -d prediction-ml-service
```

```python
async def test_predict_consumption_uses_remote_service_when_flag_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "PREDICTION_ML_REMOTE", True)
    monkeypatch.setattr(
        settings, "PREDICTION_ML_SERVICE_URL", "http://prediction-ml-service:8002"
    )
    from v2.modules.prediction_ml.public import get_prediction_service

    service = get_prediction_service()
    result = await service.predict_consumption(arac_id=1, mesafe_km=200.0, ton=15.0)
    assert "tahmini_tuketim" in result or "error" in result
```

```bash
docker exec -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest app/tests/unit/test_ml/test_prediction_ml_client_flag.py -v"  # pragma: allowlist secret
```

- [ ] **Step 7: Commit**

```bash
git add app/config.py v2/modules/prediction_ml/public.py app/tests/unit/test_ml/test_prediction_ml_client_flag.py
git commit -m "feat(prediction_ml): PREDICTION_ML_REMOTE feature flag + HTTP client

public.py now branches on the flag: false (default) keeps the legacy
in-process path (temporarily duplicated, not yet deleted -- see Task 5
step 2b note), true routes through the new prediction-ml-service via
httpx + CircuitBreakerRegistry, falling back to the existing
'save without a prediction' pattern on any failure."
```

---

### Task 7: Repeat for every remaining `public.py` function

**Files:**
- Modify: `v2/modules/prediction_ml/public.py` (`explain_consumption`, `train_xgboost_model`, `EnsemblePredictorService.train_for_vehicle`/`train_general_model`/`predict_batch`, `find_similar_trips`)

- [ ] **Step 1-N: For each remaining public function**, repeat Task 6's Steps 2, 4-6 pattern (write flag-off + flag-on test, wire the branch, verify both pass). Each function gets its own commit, following Task 6's exact template — do not batch multiple functions into one commit, since a reviewer must be able to reject one function's conversion independently of another's.

(Note for the plan executor: this task is intentionally a repeating pattern rather than N fully-spelled-out sub-tasks, to keep this document a manageable size — apply Task 6's steps verbatim per function, substituting the function name/route/payload shape from the module's own `CLAUDE.md` "Public API" listing.)

---

### Task 8: Move Celery training tasks to the new service's own worker

**Files:**
- Modify (move logic, not files — files already moved in Task 5): the new service needs its own `celery_app.py` + beat schedule entries for `scheduler_task.py`/`prediction_backfill_tasks.py`'s tasks
- Modify: `v2/modules/platform_infra/background/celery_app.py` (remove the `import v2.modules.prediction_ml.infrastructure.*_tasks` lines and the corresponding beat schedule entries — but ONLY once Task 9's flag is proven `True` in CI, per this task's own dependency on Task 9 being sequenced correctly; if the plan executor reaches this task before Task 9's CI proof, STOP and flag to the user rather than removing task registration from the main backend prematurely)
- Create: `v2/services/prediction_ml_service/celery_app.py`

**Interfaces:**
- Produces: a Celery app instance inside the new service, using the SAME `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` Redis instance as the main backend (shared broker, separate worker process — this is the standard Celery multi-service pattern, no new infra needed).

- [ ] **Step 1: Create the new service's `celery_app.py`**

```python
from celery import Celery

celery_app = Celery(
    "prediction_ml_service",
    broker=None,  # set via CELERY_BROKER_URL env at worker startup
    backend=None,
)
celery_app.config_from_object("celeryconfig")

import infrastructure.scheduler_task  # noqa: E402,F401
import infrastructure.prediction_backfill_tasks  # noqa: E402,F401
```

(Exact broker/backend wiring must mirror `v2/modules/platform_infra/background/celery_app.py`'s existing `broker_url`/`result_backend` config reads from env vars — copy that file's config block, not just the skeleton above.)

- [ ] **Step 2: Add a Dockerfile CMD variant or a separate compose service for the worker**

The new service's container image is reused for both the FastAPI app AND its Celery worker (same pattern as the main backend/`worker` service split in `docker-compose.yml` — same image, different `command:`).

- [ ] **Step 3: Verify the new worker starts and can run one task manually**

```bash
docker compose run --rm prediction-ml-service celery -A celery_app worker -l info --concurrency=1 &
sleep 5
docker compose exec prediction-ml-service celery -A celery_app call ml.weekly_retrain_all_vehicles
```

Expected: task accepted, no import errors.

- [ ] **Step 4: Remove the old task registration from the main backend's `celery_app.py`** (ONLY after Task 9 confirms `PREDICTION_ML_REMOTE=true` is green in CI)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(prediction-ml-service): own Celery worker + beat schedule

Training/backfill/retrain tasks now run in the new service's own
worker process against the same Redis broker. Main backend's
celery_app.py no longer registers these tasks (removed once
PREDICTION_ML_REMOTE=true was proven green in CI, see Task 9)."
```

---

### Task 9: docker-compose wiring + CI profile + flag rollout

**Files:**
- Modify: `docker-compose.yml` (new `prediction-ml-service` + `prediction-ml-worker` services, matching `ocr-service`'s block shape: no host port, internal network, healthcheck)
- Modify: `.github/workflows/ci.yml` (new step starting the `prediction-ml-service` container before the integration test steps, matching the existing `api-stub` `--profile test` pattern)
- Modify: `.env.example` (document `PREDICTION_ML_REMOTE`/`PREDICTION_ML_SERVICE_URL`)

**Interfaces:**
- Produces: a CI environment where `PREDICTION_ML_REMOTE=true` can be set for the full test suite run, proving the 18 call sites still work end-to-end against the real new service in CI (not mocked).

- [ ] **Step 1: Add the docker-compose service block**

**⚠️ CORRECTION (2026-08-04, Task 5 vendoring decision)**: `build.context` must be the REPO ROOT (`.`), not `v2/services/prediction_ml_service` — the Dockerfile now also `COPY`s `v2/modules/platform_infra/` and `v2/modules/shared_kernel/` into the image (Category 1 of Task 5 Step 2b's corrected audit), which are outside the service subdirectory and therefore unreachable from a narrower build context. `dockerfile:` points at the service's own Dockerfile path.

```yaml
  prediction-ml-service:
    build:
      context: .
      dockerfile: v2/services/prediction_ml_service/Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-lojinext_user}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}@db:5432/${POSTGRES_DB:-lojinext_db}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - INTERNAL_API_SECRET=${INTERNAL_API_SECRET:-}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    networks:
      - lojinext_network
```

- [ ] **Step 2: Add the CI step** (before the existing "Start backend" step, matching `api-stub`'s pattern)

```yaml
      - name: Start prediction-ml-service
        run: |
          docker compose build prediction-ml-service
          docker compose up -d prediction-ml-service
          for i in $(seq 1 15); do
            curl -sf http://localhost:8002/health && echo "prediction-ml-service ready" && break
            sleep 2
          done
```

- [ ] **Step 3: Run the full CI-equivalent test suite locally with the flag on**

```bash
docker exec -e PREDICTION_ML_REMOTE=true -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" lojinext-backend-1 sh -c "cd /app && python -m pytest -m 'unit or not integration' -q"  # pragma: allowlist secret
```

Expected: same pass count as the flag-off baseline (record this number before flipping the flag, to compare).

- [ ] **Step 4: Push a branch and confirm the new CI step is green**

```bash
git push origin <branch>
gh run watch
```

- [ ] **Step 5: Only once confirmed green, flip the default**

```python
    PREDICTION_ML_REMOTE: bool = True
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .github/workflows/ci.yml .env.example app/config.py
git commit -m "feat(prediction-ml-service): docker-compose + CI wiring, flip default to remote"
```

---

## Self-Review Notes (for the plan author, already applied above)

- Two genuine open design questions were surfaced rather than papered over: (1) how the new service reaches fleet/driver/analytics_executive/ai_assistant data (Task 5 Step 2b — needs the user's Option A/B choice before proceeding), and (2) the exact `with_async_retry` import path (Task 6 Step 3 — a concrete `grep` check, not a guess). Both are flagged as blocking checkpoints, not silently assumed.
- Task 5's original "move" was corrected to "copy" mid-plan once the flag's `false`-path requirement was noticed (public.py needs somewhere to delegate to when the flag is off, and the naive plan would have deleted that code in the same task that introduces the flag) — the old in-process code is only deleted in a future cleanup task, explicitly out of this plan's scope.
- Every task ends with a real command-based verification step (pytest, curl, docker) — no task claims success without one.

## Session log — Task 5 execution, 2026-08-04 (WIP, NOT complete — see checklist below)

Resumed Task 5 mid-execution (Tasks 1-4 were already committed in a prior
session on `worktree-prediction-ml-service-extraction`; Task 5's directory
move was already partially staged). This session's real-code investigation
surfaced THREE rounds of scope corrections beyond what the plan (and its
own Step 2b "correction") had captured — each one found by grepping the
ACTUAL moved code, not assumed from prose. Recorded here so the next
session doesn't have to rediscover them.

### Round 1 (done) — Step 2b's "6 ops / 3 files" table was itself incomplete

Already corrected in-place above (Category 1/2/3 table, 10 operations,
6 new internal-endpoint files). Implemented and code-complete:
`v2/modules/{fleet,driver,trip,analytics_executive,ai_assistant}/api/
internal_routes.py` (5 new files) + `admin_platform/api/internal_routes.py`
(1 new endpoint, `training-progress` callback for `training_ws_manager`,
since that WS connection registry only exists in the main backend's
process). All 6 registered in `api_router.py` with each module's own
`require_module_role(...)` dependency (matching every other router's
pattern — FAZ2 DB role scoping, unrelated to auth). `v2/services/
prediction_ml_service/infrastructure/cross_module_client.py` created:
one async httpx function per operation, small local retry helper (NOT an
import of route_simulation's `with_async_retry` — that module isn't
vendored and its own docstring says it's not general-purpose infra).
`prediction_backfill_service.py`/`prediction_backfill_tasks.py` moved to
`v2/modules/trip/{application,infrastructure}/` instead of the new
service (user decision) — they orchestrate trip's OWN SeferFuelEstimator
(Mapbox+route_simulation+prediction_ml combined), wrapping that in an
HTTP endpoint on this side would be a nonsensical double-hop.
`v2/modules/platform_infra/background/celery_app.py` updated: removed
`prediction.drain_dlq`/`ml.weekly_retrain_all_vehicles` imports+beat
entries (moved to a NEW `v2/services/prediction_ml_service/celery_app.py`
— own Celery app/beat, same Redis broker); `prediction.backfill_missing`
import repointed to `v2.modules.trip.infrastructure.prediction_backfill_tasks`.
`app/main.py`'s ML predictor warm-up call removed (moved to the new
service's own lifespan — not yet wired, see checklist).
`ensemble_service.py`/`ensemble_orchestration.py`/`route_similarity.py`
(moved `domain/`→`application/`, was doing I/O)/`model_warmup.py` fully
rewired to `cross_module_client.*` + two new pure-logic vendor files
(`domain/seasonal_factor.py`, `domain/vehicle_age.py` — copied byte-
faithfully from `route_simulation.WeatherService.get_seasonal_factor`/
`fleet.Arac`'s `yas`/`yas_faktoru`/`euro_sinifi` computed fields, verified
against the real source, not guessed).

### Round 2 (found, NOT yet fixed) — `shared_kernel.UnitOfWork` cannot be vendored as-is

`v2/modules/shared_kernel/infrastructure/unit_of_work.py` imports 13
business modules' repository classes at module level (`fleet.
infrastructure.vehicle_repository.AracRepository`, `trip.infrastructure.
repository.SeferRepository`, `driver...SoforRepository`,
`analytics_executive...AnalizRepository`, etc. — the whole point of
`UnitOfWork` is exposing every module's repo as a property). Vendoring
this file into the new service (as planned under "Category 1: vendor
platform_infra + shared_kernel") is a hard ImportError the moment it's
imported — none of those 13 packages exist in the new service's Docker
image. **User decision (2026-08-04): do NOT vendor `shared_kernel.
UnitOfWork` into the new service.** Fix, not yet implemented:

1. **Main-backend regression**: `unit_of_work.py` ALSO imports `v2.modules.
   prediction_ml.infrastructure.{ml_training_repo,model_versiyon_repo}`
   for its own `ml_training_repo`/`model_versiyon_repo` properties — both
   files physically moved to the new service in this same session, so
   the MAIN BACKEND's `shared_kernel.UnitOfWork` is currently ALSO
   broken (ImportError on import, not just the new service). Fix: remove
   those 2 `_Lazy(...)` property lines + their imports from `unit_of_work.py`
   — nothing on the main backend needs them anymore (prediction_ml no
   longer runs in-process there). Re-grep after removing to confirm zero
   remaining `uow.ml_training_repo`/`uow.model_versiyon_repo` callers
   outside the new service (a first pass found `v2/modules/prediction_ml/
   api/admin_ml.py` — see Round 3 below, that file needs its own fix
   regardless of this one).
2. **New service**: needs a lightweight LOCAL replacement — NOT
   `shared_kernel.UnitOfWork`, just a small session-scope helper over the
   already-vendored `platform_infra.database.connection.AsyncSessionLocal`
   (clean dependency-wise, verified — only imports platform_infra
   internals), exposing `.session`/`.commit()` plus this service's OWN
   `ml_training_repo`/`model_versiyon_repo` (using the repo classes that
   already live in this service's own `infrastructure/
   {ml_training_repo,model_versiyon_repo}.py` post-move). Every
   `async with UnitOfWork() as uow:` call site inside the moved code that
   only touches `uow.session`/`uow.commit()`/`uow.ml_training_repo`/
   `uow.model_versiyon_repo` can switch to this local class with no
   further change. Call sites still reading `uow.arac_repo`/`uow.
   sofor_repo`/`uow.dorse_repo`/`uow.sefer_repo` need their OWN fix —
   see the full list below.
3. **Every remaining `UnitOfWork`-consuming call site in the moved code**
   (found via `grep -rn "UnitOfWork\|uow\."`, not yet fully re-audited
   after Round 1's fixes — this list is what was visible before Round 1's
   edits and needs re-verification, not blind trust):
   - `ensemble_service.py::_register_model_version` — `uow.
     model_versiyon_repo.get_latest_version` (own table, fix per #2 above).
   - `ml_service.py` (`MLService` class) — constructor takes a `uow`,
     used for `egitim_kuyrugu`/`model_versiyonlar` (own tables, fix per
     #2) — re-check for any fleet/driver read mixed in.
   - `physics_handler.py` (`PhysicsRecalculationHandler`, subscribes to
     `SEFER_UPDATED`) — `uow.sefer_repo.get_by_id`/`uow.arac_repo.
     get_by_id`/`uow.dorse_repo.get_by_id`/`uow.sefer_repo.update` — ALL
     4 are cross-module, need `cross_module_client` equivalents (get_
     trailer/get_vehicle already exist; sefer read/update do NOT — trip's
     `internal_routes.py` only has the 2 training-data GETs today, needs
     a `GET /internal/trip/seferler/{id}` + `PATCH` or a dedicated
     recalibration-write endpoint added).
   - `prediction_service.py::explain_consumption` — `uow.arac_repo.
     get_by_id`/`uow.sofor_repo.get_by_id`/`uow.dorse_repo.get_by_id`
     (fallback path when `_arac_obj`/`_sofor_obj`/`_dorse_obj` aren't
     pre-fetched by the caller — that pre-fetch optimization itself is
     now moot once this only runs remotely, since a caller in a different
     process can't hand over a live ORM object; needs its own look) +
     `fetch_health_input(uow, arac_id)` (`vehicle_health_adjustment.py`)
     — this one is FINE as-is, it's raw `uow.session.execute(text(...))`
     SQL against `arac_bakimlari`, no repo-class import, works with any
     working DB session (this service already has its own `DATABASE_URL`
     per the Task 9 docker-compose plan, and `m_prediction_ml`'s DB role
     already has cross-schema SELECT grants there per the design doc's
     earlier investigation) — no `cross_module_client` needed for this
     one, just needs the local UnitOfWork-replacement from #2.
   - `time_series_service.py` — `uow.analiz_repo.get_daily_summary_for_ml`
     — this is operation #8 in the corrected Category 3 table above,
     was already scheduled for `cross_module_client.get_daily_summary_for_ml`,
     not yet implemented (Round 1 didn't reach this file).
   - `trainer.py`, `scheduler_task.py` — not yet re-checked for
     `UnitOfWork`/repo usage after Round 1 (scheduler_task.py's own
     `_run_async` does `uow.session.execute(text(...))` directly against
     `araclar` — same "raw SQL, fine" category as `fetch_health_input`,
     needs the local UnitOfWork-replacement but no cross_module_client
     call).

### Round 3 (found, NOT yet fixed) — `v2/modules/prediction_ml/api/*.py` (stays on main backend) directly imports moved classes

`api/` was deliberately excluded from Task 5's `git mv` list (it stays on
the main backend, calling through `public.py` — see the module's own
Global Constraint). But two of its four files bypass `public.py` and
import moved application-layer classes DIRECTLY:

- `api/admin_ml.py` — `from v2.modules.prediction_ml.application.
  ml_service import MLService` + `UnitOfWork().model_versiyon_repo` (3
  endpoints: `POST /train/{arac_id}`, `GET /queue`, `GET /versions/
  {arac_id}`) — all three now reference a class/repo that physically
  lives in the new service's container. Needs conversion to HTTP calls
  against the new service (the new service already needs `/train/
  {arac_id}` per Task 5's original router list — `GET /queue`/`GET
  /versions/{arac_id}` need adding as new routes there too, then this
  file becomes a thin httpx proxy, same shape as `cross_module_client.py`
  but in the reverse direction, using `settings.PREDICTION_ML_SERVICE_URL`
  + `X-Internal-Token`).
- `api/predictions.py` — uses `MLService`/`EnsemblePredictorService`/
  `PredictionService`/`Trainer` per an earlier grep; NOT YET individually
  re-read/audited this session — needs the same treatment as `admin_ml.py`
  before Task 5 can be called done. (`api/admin_pilot.py` was grepped and
  does NOT hit this pattern — likely already going through `public.py`
  correctly, but not individually re-verified line-by-line either.)

This is very likely why the plan's original "18 consumer files, zero
call-site changes required" framing (Global Constraints, top of this
document) undercounted the real blast radius — `api/admin_ml.py`/
`api/predictions.py` are the MODULE'S OWN api layer, not one of the 18
external consumers, so they were never in that count, but they still
break the moment the application layer physically leaves the container.

### Honest status checklist (2026-08-04 end of session)

**Code-complete and internally consistent** (not yet docker-built/tested):
internal endpoints (6 files) + `api_router.py` registration, `cross_module_
client.py`, `celery_app.py` split, `ensemble_service.py`/`ensemble_
orchestration.py`/`route_similarity.py`/`model_warmup.py` cross-module
rewiring, `seasonal_factor.py`/`vehicle_age.py` vendored pure logic,
Dockerfile vendoring (`platform_infra`+`shared_kernel`+`app/config.py`),
`app/config.py` new settings (`MAIN_BACKEND_INTERNAL_URL`+Task 6's flag
settings, pulled forward since `cross_module_client.py` needs the URL
setting now), `prediction_backfill_service.py`/`tasks.py` relocated to
`trip`, `main.py`/`Dockerfile` package-layout fix (`prediction_ml_service`
importable as its own top-level package under `PYTHONPATH=/app`).

**NOT done, blocking a real Task-5-complete claim**:
1. `shared_kernel/unit_of_work.py` fix (remove 2 dead properties on the
   main-backend side) — Round 2 item 1.
2. New service's local UnitOfWork-replacement class — Round 2 item 2.
3. Rewire `ml_service.py`/`physics_handler.py`/`prediction_service.py`/
   `time_series_service.py`/`trainer.py`/`scheduler_task.py` — Round 2
   item 3 (physics_handler.py needs 2 NEW `trip` internal endpoints —
   sefer read + a write/update path — that don't exist yet).
4. `api/admin_ml.py` + `api/predictions.py` HTTP conversion — Round 3.
5. `main.py` router registration (Task 5 Step 3/4 — routers directory is
   still empty) + wiring `schedule_predictor_warmup()` into the new
   service's own lifespan.
6. `requirements.txt` version audit against `app/requirements.txt` (Task
   1 Step 1 was never actually diffed against the real file).
7. Fix moved test files' import paths (Task 5 Step 5 — not started;
   18 test files sitting in `v2/services/prediction_ml_service/tests/`
   still reference old import paths).
8. `docker build` + real test run + the 4 internal-endpoint curl checks
   (Task 5 Steps 6/6b/7) — ZERO real command output collected this
   session. Every claim above is "code review says this should work,"
   not "verified." Given this codebase's own explicit standard (no
   success claim without command output), Task 5 must not be reported
   as done until this step actually runs green.

**Recommended next-session entry point**: fix Round 2 items 1-2 first
(they unblock everything else — every remaining file in item 3 needs the
local UnitOfWork replacement to even import), then work through Round 2
item 3's file list top-to-bottom, then Round 3, then Steps 3-7, then the
real docker verification. Do not skip straight to `docker build` before
finishing the rewiring — it will fail on the very first import.
