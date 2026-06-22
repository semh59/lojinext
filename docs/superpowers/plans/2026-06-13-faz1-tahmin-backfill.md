# Faz 1 — Tahmin Backfill Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sefer create'teki 2.5s timeout nedeniyle `tahmini_tuketim=NULL` kalan seferleri bulan ve `SeferFuelEstimator`'ı timeout'suz çalıştırıp dolduran bir Celery beat task'i + manuel admin tetikleyici.

**Architecture:** Üç katman. (1) `SeferRepository.get_ids_missing_prediction(limit)` — tahminisiz sefer id'lerini çeker. (2) `PredictionBackfillService.backfill(...)` (core/services) — her id için sefer yükle → `SeferFuelInput` kur → `estimator.predict(persist=True)` **timeout'suz** çağır → başarılıysa sefer satırını `tahmini_tuketim` + `route_simulation_id` + `tahmin_meta` ile güncelle; Open-Meteo'ya nazik olmak için seferler arası throttle. (3) Celery task `prediction.backfill_missing` (gece beat + `POST /admin/predictions/backfill` manuel tetik) servisi ince sarmalar.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Celery (beat + task), pytest. Yeni bağımlılık yok. Mevcut `SeferFuelEstimator` (Phase 4-5) ve `route_simulations` tablosu kullanılır.

**Önkoşul bilgiler (kod doğrulandı, 2026-06-13):**
- `estimator = get_sefer_fuel_estimator()`; `await estimator.predict(inp, persist=True)` → `SeferFuelEstimate | None`. `predict` route'u `inp.lokasyon_id`'den kendisi çözer (`_resolve_route`), `persist=True` ise `route_simulations` + `route_segments` insert + commit eder ve `estimate.simulation_id` döner. `SeferFuelInput` alanları: `arac_id, sofor_id, dorse_id, ton, target_date, bos_sefer, lokasyon_id, cikis_lat/lon, varis_lat/lon` (coords None → lokasyon_id'den çözülür).
- `SeferFuelEstimate.tahmini_tuketim` (L/100km, sefer.tahmini_tuketim'e yazılır), `.simulation_id`, `.to_legacy_prediction_dict()`.
- Sefer modeli kolonları (`app/database/models.py`): `tahmini_tuketim: Optional[float]` (567), `route_simulation_id: Optional[int]` (516), `tahmin_meta: Optional[dict]` JSONB (570).
- `BaseRepository.update(id, **data) -> bool` (base_repository.py:276) — `uow.sefer_repo.update(sid, tahmini_tuketim=.., route_simulation_id=.., tahmin_meta=..)`.
- `coverage_pct` (`admin_fuel_accuracy.py`): `sample_size / total_completed * 100`; `sample_size` = `tahmini_tuketim IS NOT NULL AND > 0` olan tamamlanmış seferler. NULL doldurmak coverage'ı artırır → kabul kriteri gözlemlenebilir.
- Celery task pattern (`theft_tasks.py:93`): `@celery_app.task(bind=True, name="...", max_retries=..., acks_late=True)` + `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(_run())`. Beat schedule: `app/infrastructure/background/celery_app.py` `beat_schedule={...}` + task modülü `import`'u (dosyanın altında `import app.workers.tasks.<mod>  # noqa`).
- `CELERY_EAGER=True` test ortamında task'i inline koşar (`app/config.py`).
- Test DB lokal koşma reçetesi: bkz memory `local-test-db-execution` (Py3.12 container + throwaway testdb + full-repo mount + `--ignore=tests/integration --ignore=app/tests/integration` unit gate; integration testleri kendi step'inde).

---

### Task 1: Faz 1 çalışma branch'ini aç

**Files:** Yok (git).

- [ ] **Step 1: main güncel mi doğrula**

Run: `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -3 || git log main -1 --oneline`
Expected: main `fc1cc746` (Faz 0 kapanışı) veya sonrası; çalışma ağacı temiz.

- [ ] **Step 2: Branch aç**

Run: `git checkout -b feat/faz1-tahmin-backfill main`
Expected: `Switched to a new branch 'feat/faz1-tahmin-backfill'`

---

### Task 2: `SeferRepository.get_ids_missing_prediction`

Tahminisiz (silinmemiş) sefer id'lerini en eskiden yeniye çeker.

**Files:**
- Modify: `app/database/repositories/sefer_repo.py`
- Test: `app/tests/integration/test_sefer_backfill_repo.py` (create)

- [ ] **Step 1: Failing integration test yaz**

`app/tests/integration/test_sefer_backfill_repo.py`:

```python
"""SeferRepository.get_ids_missing_prediction integration testi."""

import pytest

from app.database.models import Arac, Lokasyon, Sefer, Sofor
from app.database.repositories.sefer_repo import SeferRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _seed_min(db):
    arac = Arac(plaka="34ABC12", marka="M", model="A", yil=2022, tank_kapasitesi=600,
                hedef_tuketim=30.0, aktif=True, bos_agirlik_kg=8000)
    sofor = Sofor(ad_soyad="S1", aktif=True)
    lok = Lokasyon(cikis_yeri="Istanbul", varis_yeri="Ankara", mesafe_km=450.0)
    db.add_all([arac, sofor, lok])
    await db.commit()
    await db.refresh(arac); await db.refresh(sofor); await db.refresh(lok)
    return arac, sofor, lok


async def test_returns_only_null_prediction_non_deleted(db_session):
    arac, sofor, lok = await _seed_min(db_session)
    base = dict(tarih=__import__("datetime").date(2026, 6, 1), arac_id=arac.id,
                sofor_id=sofor.id, guzergah_id=lok.id, cikis_yeri="Istanbul",
                varis_yeri="Ankara", mesafe_km=450.0, bos_agirlik_kg=8000,
                dolu_agirlik_kg=23000, net_kg=15000, durum="Planned")
    s_null = Sefer(**base)
    s_has = Sefer(**base, tahmini_tuketim=31.2)
    s_deleted = Sefer(**base, is_deleted=True)
    db_session.add_all([s_null, s_has, s_deleted])
    await db_session.commit()
    await db_session.refresh(s_null)

    repo = SeferRepository(db_session)
    ids = await repo.get_ids_missing_prediction(limit=100)

    assert s_null.id in ids
    assert s_has.id not in ids
    assert s_deleted.id not in ids


async def test_respects_limit(db_session):
    arac, sofor, lok = await _seed_min(db_session)
    base = dict(tarih=__import__("datetime").date(2026, 6, 1), arac_id=arac.id,
                sofor_id=sofor.id, guzergah_id=lok.id, cikis_yeri="Istanbul",
                varis_yeri="Ankara", mesafe_km=450.0, bos_agirlik_kg=8000,
                dolu_agirlik_kg=23000, net_kg=15000, durum="Planned")
    db_session.add_all([Sefer(**base) for _ in range(5)])
    await db_session.commit()

    repo = SeferRepository(db_session)
    ids = await repo.get_ids_missing_prediction(limit=3)
    assert len(ids) == 3
```

- [ ] **Step 2: Testin FAIL ettiğini doğrula**

Run (bkz [[local-test-db-execution]] reçetesi; kısaca container içinde):
`python -m pytest app/tests/integration/test_sefer_backfill_repo.py -m integration -q`
Expected: FAIL — `AttributeError: 'SeferRepository' object has no attribute 'get_ids_missing_prediction'`.

- [ ] **Step 3: Metodu implemente et**

`app/database/repositories/sefer_repo.py` — sınıfa ekle (importlar zaten `select`, `Sefer` içeriyor; değilse dosyanın mevcut importlarına bak):

```python
    async def get_ids_missing_prediction(self, limit: int = 50) -> list[int]:
        """tahmini_tuketim NULL olan, silinmemiş seferlerin id'leri (eski→yeni).

        Sefer create yolundaki 2.5s timeout fallback'i bu satırları NULL
        bırakıyor (bkz CLAUDE.md SeferFuelEstimator). Backfill job bunları
        timeout'suz estimator ile doldurur.
        """
        from sqlalchemy import select

        from app.database.models import Sefer

        stmt = (
            select(Sefer.id)
            .where(Sefer.tahmini_tuketim.is_(None))
            .where(Sefer.is_deleted.is_(False))
            .order_by(Sefer.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [int(r) for r in result.scalars().all()]
```

- [ ] **Step 4: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/integration/test_sefer_backfill_repo.py -m integration -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/database/repositories/sefer_repo.py app/tests/integration/test_sefer_backfill_repo.py
git commit -m "feat(backfill): SeferRepository.get_ids_missing_prediction"
```

---

### Task 3: `PredictionBackfillService.backfill`

Tahminisiz seferleri estimator ile dolduran orkestrasyon servisi. Estimator + UoW mock'lanarak unit test edilir (DB/ağ gerektirmez).

**Files:**
- Create: `app/core/services/prediction_backfill_service.py`
- Test: `app/tests/unit/test_services/test_prediction_backfill_service.py` (create)

- [ ] **Step 1: Failing unit test yaz**

`app/tests/unit/test_services/test_prediction_backfill_service.py`:

```python
"""PredictionBackfillService unit testleri (estimator + uow mock'lu)."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.services.prediction_backfill_service import PredictionBackfillService

pytestmark = pytest.mark.unit


def _sefer_dict(sid: int) -> dict:
    return {
        "id": sid, "arac_id": 1, "sofor_id": 2, "dorse_id": None,
        "ton": 15.0, "net_kg": 15000, "tarih": date(2026, 6, 1),
        "bos_sefer": False, "guzergah_id": 7,
    }


def _make_uow(ids, sefer_lookup):
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_ids_missing_prediction = AsyncMock(return_value=ids)
    uow.sefer_repo.get_by_id = AsyncMock(side_effect=lambda sid: sefer_lookup.get(sid))
    uow.sefer_repo.update = AsyncMock(return_value=True)
    uow.commit = AsyncMock()
    return uow


async def test_backfill_fills_predictions():
    uow = _make_uow([10], {10: _sefer_dict(10)})
    estimate = SimpleNamespace(
        tahmini_tuketim=32.5, simulation_id=99,
        to_legacy_prediction_dict=lambda: {"tahmini_tuketim": 32.5, "simulation_id": 99},
    )
    estimator = MagicMock()
    estimator.predict = AsyncMock(return_value=estimate)

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 1, "filled": 1, "failed": 0, "skipped": 0}
    uow.sefer_repo.update.assert_awaited_once()
    _, kwargs = uow.sefer_repo.update.await_args
    assert kwargs["tahmini_tuketim"] == 32.5
    assert kwargs["route_simulation_id"] == 99


async def test_backfill_skips_when_estimator_returns_none():
    uow = _make_uow([10], {10: _sefer_dict(10)})
    estimator = MagicMock()
    estimator.predict = AsyncMock(return_value=None)  # Mapbox çözememe vs.

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 1, "filled": 0, "failed": 0, "skipped": 1}
    uow.sefer_repo.update.assert_not_awaited()


async def test_backfill_counts_failure_without_aborting_batch():
    uow = _make_uow([10, 11], {10: _sefer_dict(10), 11: _sefer_dict(11)})
    estimate = SimpleNamespace(
        tahmini_tuketim=30.0, simulation_id=1,
        to_legacy_prediction_dict=lambda: {"tahmini_tuketim": 30.0},
    )
    estimator = MagicMock()
    # İlk sefer patlar, ikinci başarılı → batch devam eder.
    estimator.predict = AsyncMock(side_effect=[RuntimeError("boom"), estimate])

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 2, "filled": 1, "failed": 1, "skipped": 0}
```

- [ ] **Step 2: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_services/test_prediction_backfill_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.services.prediction_backfill_service'`.

- [ ] **Step 3: Servisi implemente et**

`app/core/services/prediction_backfill_service.py`:

```python
"""Faz 1 — Tahminisiz seferleri SeferFuelEstimator ile dolduran backfill servisi.

Sefer create yolundaki 2.5s timeout (bkz CLAUDE.md) cold cache'de tahminisiz
sefer bırakır. Bu servis o seferleri **timeout'suz** estimator ile doldurur;
gece Celery beat task'i (prediction.backfill_missing) ya da admin tetik çağırır.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PredictionBackfillService:
    """tahmini_tuketim=NULL seferleri estimator ile doldurur.

    estimator ve uow opsiyonel inject edilir (test edilebilirlik). Üretimde
    None geçilirse lazy default'lar kullanılır.
    """

    def __init__(
        self,
        *,
        uow: Optional[Any] = None,
        estimator: Optional[Any] = None,
        throttle_s: float = 0.5,
    ) -> None:
        self._uow = uow
        self._estimator = estimator
        self._throttle_s = throttle_s

    def _get_uow(self) -> Any:
        if self._uow is not None:
            return self._uow
        from app.database.unit_of_work import UnitOfWork

        return UnitOfWork()

    def _get_estimator(self) -> Any:
        if self._estimator is not None:
            return self._estimator
        from app.core.services.sefer_fuel_estimator import get_sefer_fuel_estimator

        return get_sefer_fuel_estimator()

    async def backfill(
        self, *, limit: int = 50, sefer_ids: Optional[list[int]] = None
    ) -> dict[str, int]:
        """Tahminisiz seferleri doldur. {processed, filled, failed, skipped} döner.

        - estimator None döndürürse (Mapbox/route çözememe) → skipped.
        - estimator exception atarsa → failed (batch devam eder).
        - Başarılı → sefer.tahmini_tuketim + route_simulation_id + tahmin_meta yazılır.
        """
        from app.core.services.sefer_fuel_estimator import SeferFuelInput

        estimator = self._get_estimator()
        processed = filled = failed = skipped = 0

        async with self._get_uow() as uow:
            ids = sefer_ids or await uow.sefer_repo.get_ids_missing_prediction(
                limit=limit
            )
            for sid in ids:
                processed += 1
                try:
                    sefer = await uow.sefer_repo.get_by_id(sid)
                    if not sefer:
                        skipped += 1
                        continue
                    ton = float(
                        sefer.get("ton")
                        or (sefer.get("net_kg") or 0) / 1000.0
                    )
                    inp = SeferFuelInput(
                        arac_id=sefer["arac_id"],
                        sofor_id=sefer.get("sofor_id"),
                        dorse_id=sefer.get("dorse_id"),
                        ton=ton,
                        target_date=sefer["tarih"],
                        bos_sefer=bool(sefer.get("bos_sefer")),
                        lokasyon_id=sefer.get("guzergah_id"),
                    )
                    # NOT: timeout YOK — create yolundaki 2.5s sınırı burada
                    # kasıtlı uygulanmaz; job gece + düşük tempo koşar.
                    estimate = await estimator.predict(inp, persist=True)
                    if estimate is None:
                        skipped += 1
                        continue
                    await uow.sefer_repo.update(
                        sid,
                        tahmini_tuketim=estimate.tahmini_tuketim,
                        route_simulation_id=estimate.simulation_id,
                        tahmin_meta=estimate.to_legacy_prediction_dict(),
                    )
                    filled += 1
                except Exception as exc:  # noqa: BLE001 — batch'i bir sefer bozmasın
                    failed += 1
                    logger.warning("backfill sefer=%s başarısız: %s", sid, exc)
                if self._throttle_s:
                    await asyncio.sleep(self._throttle_s)
            await uow.commit()

        logger.info(
            "PredictionBackfill done: processed=%s filled=%s failed=%s skipped=%s",
            processed, filled, failed, skipped,
        )
        return {
            "processed": processed,
            "filled": filled,
            "failed": failed,
            "skipped": skipped,
        }
```

- [ ] **Step 4: Testlerin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_services/test_prediction_backfill_service.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/core/services/prediction_backfill_service.py app/tests/unit/test_services/test_prediction_backfill_service.py
git commit -m "feat(backfill): PredictionBackfillService.backfill (estimator timeout'suz)"
```

---

### Task 4: Celery task + beat schedule

**Files:**
- Create: `app/workers/tasks/prediction_backfill_tasks.py`
- Modify: `app/infrastructure/background/celery_app.py` (beat_schedule + import)
- Test: `app/tests/unit/test_prediction_backfill_task.py` (create)

- [ ] **Step 1: Failing test yaz**

`app/tests/unit/test_prediction_backfill_task.py`:

```python
"""prediction.backfill_missing Celery task wrapper testi (eager)."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_task_invokes_service_and_returns_summary():
    summary = {"processed": 2, "filled": 2, "failed": 0, "skipped": 0}
    with patch(
        "app.core.services.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(return_value=summary),
    ):
        from app.workers.tasks.prediction_backfill_tasks import backfill_missing

        result = backfill_missing.run(limit=10)

    assert result == summary
```

- [ ] **Step 2: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_prediction_backfill_task.py -q`
Expected: FAIL — `ModuleNotFoundError: ...prediction_backfill_tasks`.

- [ ] **Step 3: Task'i implemente et**

`app/workers/tasks/prediction_backfill_tasks.py`:

```python
"""Faz 1 — Tahmin backfill Celery task (gece beat + manuel tetik)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="prediction.backfill_missing",
    max_retries=1,
    acks_late=True,
)
def backfill_missing(self, limit: int = 50) -> dict[str, Any]:  # noqa: ARG001
    """tahmini_tuketim=NULL seferleri estimator ile doldur."""
    from app.core.services.prediction_backfill_service import (
        PredictionBackfillService,
    )

    async def _run() -> dict[str, Any]:
        return await PredictionBackfillService().backfill(limit=limit)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("prediction backfill task failed: %s", exc, exc_info=True)
        return {"processed": 0, "filled": 0, "failed": 0, "skipped": 0, "error": str(exc)}
    finally:
        loop.close()
```

- [ ] **Step 4: Beat schedule + import ekle**

`app/infrastructure/background/celery_app.py` — `beat_schedule={...}` içine son entry'den sonra ekle:

```python
            # Faz 1 — Her gün 01:00 UTC, tahminisiz seferleri doldur (gece/düşük tempo).
            "prediction-backfill-missing-nightly": {
                "task": "prediction.backfill_missing",
                "schedule": crontab(hour=1, minute=0),
            },
```

Aynı dosyada task modülü import bloğuna (diğer `import app.workers.tasks.*  # noqa` satırlarının yanına) ekle:

```python
import app.workers.tasks.prediction_backfill_tasks  # noqa: E402,F401
```

- [ ] **Step 5: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_prediction_backfill_task.py -q`
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add app/workers/tasks/prediction_backfill_tasks.py app/infrastructure/background/celery_app.py app/tests/unit/test_prediction_backfill_task.py
git commit -m "feat(backfill): prediction.backfill_missing Celery task + gece beat schedule"
```

---

### Task 5: Manuel tetik endpoint'i `POST /admin/predictions/backfill`

Admin gece beklemeden backfill tetikleyebilir. Eager modda inline koşar, prod'da task enqueue eder.

**Files:**
- Create: `app/api/v1/endpoints/admin_predictions.py`
- Modify: `app/api/v1/api.py` (router include)
- Test: `app/tests/api/test_admin_predictions.py` (create)

- [ ] **Step 1: api.py'de admin router include pattern'ini incele**

Run: `grep -nE "admin_fuel_accuracy|include_router|prefix=.*admin" app/api/v1/api.py | head`
Expected: `admin_fuel_accuracy` router'ının nasıl include edildiğini gör (prefix/tags). Yeni endpoint aynı kalıbı izleyecek.

- [ ] **Step 2: Failing test yaz**

`app/tests/api/test_admin_predictions.py`:

```python
"""POST /admin/predictions/backfill endpoint testi."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_backfill_trigger_returns_summary(
    async_client, async_admin_user_token_headers
):
    summary = {"processed": 3, "filled": 3, "failed": 0, "skipped": 0}
    with patch(
        "app.core.services.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(return_value=summary),
    ):
        resp = await async_client.post(
            "/api/v1/admin/predictions/backfill?limit=10",
            headers=async_admin_user_token_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["filled"] == 3


async def test_backfill_trigger_requires_admin(async_client, async_normal_user_token_headers):
    resp = await async_client.post(
        "/api/v1/admin/predictions/backfill",
        headers=async_normal_user_token_headers,
    )
    assert resp.status_code == 403
```

> Not: `async_admin_user_token_headers` / `async_normal_user_token_headers` fixture adlarını `app/tests/conftest.py`'de doğrula; farklıysa testte mevcut admin/normal fixture adıyla değiştir (Step 1'de görülen diğer admin endpoint testlerine bak).

- [ ] **Step 3: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/api/test_admin_predictions.py -m integration -q`
Expected: FAIL — 404 (route yok).

- [ ] **Step 4: Endpoint'i implemente et**

`app/api/v1/endpoints/admin_predictions.py`:

```python
"""Faz 1 — Admin tahmin backfill manuel tetik endpoint'i."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_active_admin
from app.core.services.prediction_backfill_service import PredictionBackfillService

router = APIRouter()


@router.post("/predictions/backfill")
async def trigger_prediction_backfill(
    limit: int = Query(50, ge=1, le=500),
    _admin=Depends(get_current_active_admin),
) -> dict:
    """tahmini_tuketim=NULL seferleri estimator ile doldurur (inline çalışır).

    Gece beat task'i (prediction.backfill_missing) ile aynı servisi kullanır;
    bu endpoint admin'in beklemeden tetiklemesi içindir.
    """
    return await PredictionBackfillService().backfill(limit=limit)
```

- [ ] **Step 5: Router'ı api.py'ye ekle**

`app/api/v1/api.py` — Step 1'de gördüğün `admin_fuel_accuracy` include satırının hemen yanına, aynı prefix kalıbıyla ekle (admin endpoint'leri `/admin` prefix + admin tag kullanıyor):

```python
from app.api.v1.endpoints import admin_predictions  # mevcut import bloğuna

api_router.include_router(
    admin_predictions.router, prefix="/admin", tags=["admin"]
)
```

> `admin_fuel_accuracy` router'ı hangi prefix/tag ile include edildiyse onu birebir uygula (Step 1 çıktısı). Endpoint yolu `/api/v1/admin/predictions/backfill` olmalı.

- [ ] **Step 6: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/api/test_admin_predictions.py -m integration -q`
Expected: `2 passed`. (403 testi de geçmeli — admin guard.)

- [ ] **Step 7: Commit**

```bash
git add app/api/v1/endpoints/admin_predictions.py app/api/v1/api.py app/tests/api/test_admin_predictions.py
git commit -m "feat(backfill): POST /admin/predictions/backfill manuel tetik endpoint"
```

---

### Task 6: Gate'ler + uçtan uca kabul doğrulaması

**Files:** Yok (doğrulama + merge).

- [ ] **Step 1: ruff + mypy**

Run: `ruff check app --select E,F,W,I && mypy app --ignore-missing-imports --no-strict-optional 2>&1 | tail -2`
Expected: ruff `All checks passed!`; mypy `Success: no issues found`.

- [ ] **Step 2: Yeni testleri + ilgili suite'i koş (faithful Py3.12, bkz [[local-test-db-execution]])**

Run (container reçetesiyle): `python -m pytest app/tests/unit/test_services/test_prediction_backfill_service.py app/tests/unit/test_prediction_backfill_task.py app/tests/integration/test_sefer_backfill_repo.py app/tests/api/test_admin_predictions.py -q`
Expected: hepsi pass (6 test).

- [ ] **Step 3: Uçtan uca kabul (canlı stack)**

Önkoşul: stack healthy (`docker compose ps` → backend healthy), test DB değil **dev** stack. Tahminisiz bir sefer üret (örn. `USE_SEFER_FUEL_ESTIMATOR=false` iken sefer create → `tahmini_tuketim=NULL`), sonra:

Run: `docker compose exec backend curl -s -X POST "http://localhost:8000/api/v1/admin/predictions/backfill?limit=10" -H "Authorization: Bearer <admin_token>"`
(veya beat'i beklemeden: `docker compose exec backend python -c "from app.workers.tasks.prediction_backfill_tasks import backfill_missing; print(backfill_missing.run(limit=10))"`)
Expected: `{"processed": N, "filled": >=1, ...}`; ardından ilgili sefer satırında `tahmini_tuketim` ve `route_simulation_id` DOLU; `GET /api/v1/admin/fuel-accuracy` `coverage_pct` artmış. Open-Meteo 429 görülürse estimator içi retry devreye girer (CLAUDE.md gotcha); job düşük tempo + throttle ile koşar.

- [ ] **Step 4: main'e merge + push**

```bash
git checkout main
git merge --ff-only feat/faz1-tahmin-backfill
git push neworigin main
```

Expected: `Fast-forward` + push başarı. Faz 1 TAMAM — yol haritasında sıradaki: Faz 2 (Audit DB wiring).

---

## Self-Review Notu (2026-06-13)

- **Spec kapsaması:** Faz 1 spec maddesi — "2.5s timeout nedeniyle NULL kalan seferleri gece bulan + estimator'ı timeout'suz çalıştıran Celery beat task'i": Task 2 (NULL sorgusu) + Task 3 (estimator timeout'suz) + Task 4 (gece beat). Kabul kriteri "tahmini_tuketim + route_simulation_id dolu; coverage_pct artışı; Open-Meteo 429 retry": Task 3 (update fields) + Task 6 Step 3. "(veya manuel tetik)": Task 5.
- **Placeholder taraması:** Yok — her adımda tam kod/komut. İki yerde doğrulama notu var (fixture adları Task 5 Step 2; admin router prefix Task 5 Step 1/5) — bunlar codebase'e göre teyit gerektiren noktalar, placeholder değil; doğrulama komutu verildi.
- **Tip/isim tutarlılığı:** `get_ids_missing_prediction(limit)` Task 2'de tanımlandı, Task 3'te çağrıldı. `PredictionBackfillService(uow=, estimator=, throttle_s=).backfill(limit=, sefer_ids=)` Task 3'te tanımlı, Task 4/5'te `PredictionBackfillService().backfill(limit=)` ile çağrılıyor (default args uyumlu). `backfill_missing` task adı Task 4'te tanımlı, Task 5 Step 3 ve Task 6 Step 3'te aynı. Dönüş sözleşmesi `{processed, filled, failed, skipped}` her yerde tutarlı.
- **Sıra bağımlılığı:** Task 2 (repo) → Task 3 (servis, repo'yu çağırır) → Task 4 (task, servisi sarar) → Task 5 (endpoint, servisi çağırır) → Task 6 (entegrasyon). Her task kendi başına test edilebilir/commit'lenebilir.
- **Estimator yan etkisi:** `predict(persist=True)` route_simulations'a kendi session'ında commit eder; backfill ayrı uow'da sefer satırını günceller — iki commit, kasıtlı (estimator sözleşmesi korunur).
