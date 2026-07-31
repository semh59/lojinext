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

- [ ] **Step 2b: Resolve the cross-repo-module import problem**

This is the crux of "real" service separation: `ensemble_service.py` alone imports `v2.modules.fleet.public`, `v2.modules.driver.public`, `v2.modules.analytics_executive.public` (per the module's own CLAUDE.md "Senkron konuştuğu modüller" section — 4 modules, in-process today). The new service cannot import these Python packages (they don't exist in its container). Two options, pick one WITH THE USER before proceeding (this is a real architectural fork this plan cannot resolve unilaterally):

  - **Option A**: Copy the specific consumed functions/repos (`get_arac_repo`, `get_dorse_repo`, `get_driver_stats`, `classify_route`, `get_analiz_repo`, `get_smart_ai().teach()`) into the new service too, each hitting the SAME Postgres database directly with the `m_prediction_ml` role (already has cross-schema SELECT grants on `fleet`/`driver`/`anomaly`/`platform`/`admin_platform` per `role_grants.py`'s `READER_SELECT_GRANTS["m_prediction_ml"]` entry — confirmed in this session's earlier investigation). This keeps DB access patterns identical, only duplicates a handful of read-only repo functions.
  - **Option B**: The new service calls the MAIN backend's HTTP API for this cross-module data (e.g. `GET /fleet/vehicles/{id}`), adding a second network hop inside training/prediction paths.

  Option A is recommended: it reuses the ALREADY-GRANTED `m_prediction_ml` DB role, avoids a second network hop, and is a smaller, mechanical duplication (a handful of read-only query functions, not business logic). **Do not proceed past this step without the user's explicit confirmation of which option to implement** — this determines the shape of every remaining step in this task.

- [ ] **Step 3: Once Option A/B is confirmed, implement the cross-module data access accordingly, then write the routers**

(Concrete router code depends on the Step 2b decision — write one router file per operation, e.g. `v2/services/prediction_ml_service/routers/predict_routes.py`:)

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

```yaml
  prediction-ml-service:
    build:
      context: v2/services/prediction_ml_service
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
