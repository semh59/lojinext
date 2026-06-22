# Faz 8 — Anomali Kümeleme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox (`- [ ]`) adımları.

**Goal:** Anomalileri DBSCAN ile kümeleyip tekrarlayan desenleri ("pattern") yüzeye çıkar; `GET /anomalies/clusters` + günlük Celery tarama + AlertsPage kümeler görünümü + (feature-flag arkasında) Groq cluster insight metni. Groq kesintisi pattern listesini bloklamaz.

**Architecture:** (1) `app/core/ml/anomaly_clustering.py` — saf `cluster_anomalies(rows)` fonksiyonu: feature vektörü (tip/kaynak_tip kodları, severity ordinal, ölçeklenmiş sapma_yüzde) → StandardScaler → DBSCAN → küme istatistikleri + kural-tabanlı etiket. DB/LLM gerektirmez (unit-testable). (2) `GET /anomalies/clusters` — son N gün anomalisini çek → kümele → döndür; `ANOMALY_CLUSTER_LLM_ENABLED` açıksa her kümeye Groq insight (best-effort; Groq fail → insight=None, liste yine döner). (3) Günlük Celery task `anomaly.cluster_scan` — tarar + özet/metric loglar. (4) Frontend: `anomalyService.getClusters` + `AnomalyClusters` bileşeni AlertsPage pattern alanına.

**Tech Stack:** scikit-learn DBSCAN (>=1.4 mevcut), FastAPI, Celery, React + React Query, pytest, vitest.

**Önkoşullar (kod doğrulandı 2026-06-13):**
- `Anomaly`: tip (tuketim/maliyet/sefer), kaynak_tip (arac/sofor/sefer/yakit), kaynak_id, deger, beklenen_deger, sapma_yuzde, severity (low/medium/high/critical), tarih, created_at.
- `get_anomaly_detector().get_recent_anomalies(days=30, severity=, status=, sofor_id=) -> List[Dict]` (anomalies endpoint:34 deseni). Dict anahtarları Anomaly alanlarıyla uyumlu (tip, kaynak_tip, kaynak_id, sapma_yuzde, severity, id...).
- `GroqService.chat(user_message, system_prompt=...) -> str` (async; `app/core/ai/groq_service.py`).
- anomalies router prefix `/anomalies` (api.py). Endpoint deps: `get_current_active_user`.
- Config: `app/config.py` BaseSettings.
- Frontend: AlertsPage `PatternList` (investigations — ayrı); yeni `AnomalyClusters` eklenir. `anomalyService` (`services/api/anomaly-service.ts`).
- Celery task pattern + beat: `celery_app.py`. Lokal faithful test: bkz [[local-test-db-execution]]. `docker exec pytest /app/...` MSYS-mangle → `bash -c "cd /app && pytest"`.

---

### Task 1: Branch
- [ ] `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -1; git checkout -b feat/faz8-anomali-kumeleme main`

---

### Task 2: `anomaly_clustering.py` (DBSCAN, saf fonksiyon)

**Files:** Create `app/core/ml/anomaly_clustering.py`; Test `app/tests/unit/test_anomaly_clustering.py`.

- [ ] **Step 1: Failing test**

```python
"""anomaly_clustering testleri."""
import pytest
from app.core.ml.anomaly_clustering import cluster_anomalies

pytestmark = pytest.mark.unit


def _a(id, tip, kaynak_tip, severity, sapma):
    return {
        "id": id, "tip": tip, "kaynak_tip": kaynak_tip,
        "kaynak_id": 1, "severity": severity, "sapma_yuzde": sapma,
    }


def test_groups_similar_anomalies_into_a_cluster():
    rows = [
        _a(1, "tuketim", "arac", "high", 25.0),
        _a(2, "tuketim", "arac", "high", 26.0),
        _a(3, "tuketim", "arac", "high", 24.5),
        _a(4, "maliyet", "sefer", "low", 3.0),  # tek başına → noise
    ]
    clusters = cluster_anomalies(rows, eps=0.6, min_samples=2)
    assert len(clusters) >= 1
    top = clusters[0]
    assert top["size"] == 3
    assert top["dominant_tip"] == "tuketim"
    assert set(top["member_ids"]) == {1, 2, 3}
    assert isinstance(top["label"], str) and top["label"]


def test_empty_input_returns_empty():
    assert cluster_anomalies([]) == []


def test_too_few_returns_no_clusters():
    # min_samples=2 altında küme oluşmaz (noise)
    assert cluster_anomalies([_a(1, "tuketim", "arac", "high", 25.0)]) == []
```

- [ ] **Step 2:** Run → FAIL (ModuleNotFound).

- [ ] **Step 3: Implement**

```python
"""Faz 8 — anomali kümeleme (DBSCAN).

Tekrarlayan anomali desenlerini ('pattern') yüzeye çıkarır. Saf fonksiyon:
DB/LLM bağımlılığı yok; endpoint ve task çağırır.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_TIP_CODES = {"tuketim": 0, "maliyet": 1, "sefer": 2}
_KAYNAK_CODES = {"arac": 0, "sofor": 1, "sefer": 2, "yakit": 3}
_SEVERITY_ORD = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _feature_row(a: dict) -> list[float]:
    return [
        float(_TIP_CODES.get(str(a.get("tip")), 9)),
        float(_KAYNAK_CODES.get(str(a.get("kaynak_tip")), 9)),
        float(_SEVERITY_ORD.get(str(a.get("severity")), 0)),
        float(a.get("sapma_yuzde") or 0.0),
    ]


def _label(members: list[dict]) -> str:
    tip = Counter(str(m.get("tip")) for m in members).most_common(1)[0][0]
    sev = Counter(str(m.get("severity")) for m in members).most_common(1)[0][0]
    kaynak = Counter(str(m.get("kaynak_tip")) for m in members).most_common(1)[0][0]
    return f"{len(members)} adet {sev} {tip} anomalisi ({kaynak} kaynaklı)"


def cluster_anomalies(
    rows: list[dict], *, eps: float = 0.6, min_samples: int = 2
) -> list[dict[str, Any]]:
    """Anomali dict listesini DBSCAN ile kümeler.

    Returns: küme listesi (büyükten küçüğe). Her küme:
        {cluster_id, size, dominant_tip, dominant_kaynak_tip,
         severity_dagilim, member_ids, label}
    Noise (label=-1) atılır; <min_samples gruplar küme sayılmaz.
    """
    if len(rows) < min_samples:
        return []
    import numpy as np
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler

    X = np.array([_feature_row(a) for a in rows], dtype=float)
    Xs = StandardScaler().fit_transform(X)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xs)

    groups: dict[int, list[dict]] = {}
    for a, lbl in zip(rows, labels):
        if lbl == -1:
            continue
        groups.setdefault(int(lbl), []).append(a)

    clusters: list[dict[str, Any]] = []
    for cid, members in groups.items():
        sev_dist = dict(Counter(str(m.get("severity")) for m in members))
        clusters.append(
            {
                "cluster_id": cid,
                "size": len(members),
                "dominant_tip": Counter(
                    str(m.get("tip")) for m in members
                ).most_common(1)[0][0],
                "dominant_kaynak_tip": Counter(
                    str(m.get("kaynak_tip")) for m in members
                ).most_common(1)[0][0],
                "severity_dagilim": sev_dist,
                "member_ids": [m.get("id") for m in members],
                "label": _label(members),
            }
        )
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters
```

- [ ] **Step 4:** Run → 3 passed.
- [ ] **Step 5:** Commit: `feat(anomaly): anomaly_clustering DBSCAN — tekrarlayan desen kümeleme`

---

### Task 3: `GET /anomalies/clusters` + config + LLM insight

**Files:** Modify `app/config.py`; Modify `app/api/v1/endpoints/anomalies.py`; Test `app/tests/api/test_anomaly_clusters.py`.

- [ ] **Step 1: Config** (`config.py`):
```python
    ANOMALY_CLUSTER_LLM_ENABLED: bool = False
```

- [ ] **Step 2: Failing test** (`app/tests/api/test_anomaly_clusters.py`):

```python
"""GET /anomalies/clusters testleri."""
from unittest.mock import AsyncMock, patch
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_ROWS = [
    {"id": 1, "tip": "tuketim", "kaynak_tip": "arac", "kaynak_id": 1, "severity": "high", "sapma_yuzde": 25.0},
    {"id": 2, "tip": "tuketim", "kaynak_tip": "arac", "kaynak_id": 1, "severity": "high", "sapma_yuzde": 26.0},
    {"id": 3, "tip": "tuketim", "kaynak_tip": "arac", "kaynak_id": 2, "severity": "high", "sapma_yuzde": 24.0},
]


async def test_clusters_returns_patterns(async_client, normal_auth_headers):
    with patch(
        "app.api.v1.endpoints.anomalies.get_anomaly_detector"
    ) as mock_det:
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=_ROWS)
        resp = await async_client.get(
            "/api/v1/anomalies/clusters?days=30", headers=normal_auth_headers
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["clusters"][0]["size"] == 3
    assert body["clusters"][0]["dominant_tip"] == "tuketim"


async def test_clusters_requires_auth(async_client):
    resp = await async_client.get("/api/v1/anomalies/clusters")
    assert resp.status_code == 401


async def test_clusters_llm_failure_does_not_block(async_client, normal_auth_headers, monkeypatch):
    monkeypatch.setattr("app.config.settings.ANOMALY_CLUSTER_LLM_ENABLED", True)
    with (
        patch("app.api.v1.endpoints.anomalies.get_anomaly_detector") as mock_det,
        patch(
            "app.api.v1.endpoints.anomalies._cluster_insight",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ),
    ):
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=_ROWS)
        resp = await async_client.get(
            "/api/v1/anomalies/clusters", headers=normal_auth_headers
        )
    # Groq düşse de liste döner; insight None
    assert resp.status_code == 200
    assert resp.json()["clusters"][0]["insight"] is None
```

- [ ] **Step 3:** Run → FAIL (404).

- [ ] **Step 4: Endpoint** (`anomalies.py`). İmportlar:
```python
from app.config import settings
from app.core.ml.anomaly_clustering import cluster_anomalies
```
Endpoint + LLM helper:

```python
async def _cluster_insight(cluster: dict) -> str:
    """Groq ile küme için kısa Türkçe insight. Hata → caller yutar."""
    from app.core.ai.groq_service import GroqService

    prompt = (
        f"Filo anomali kümesi: {cluster['label']}. "
        f"Severity dağılımı: {cluster['severity_dagilim']}. "
        "Tek cümlede olası kök neden ve önerilen aksiyonu Türkçe yaz."
    )
    return await GroqService().chat(prompt, system_prompt="Sen bir filo analistisin.")


@router.get("/clusters", response_model=Dict[str, Any])
async def get_anomaly_clusters(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=180),
) -> Dict[str, Any]:
    """Son `days` gün anomalilerini kümeleyip pattern listesi döndürür.

    LLM insight yalnız ANOMALY_CLUSTER_LLM_ENABLED açıkken ve best-effort;
    Groq kesintisi pattern listesini bloklamaz (insight=None).
    """
    detector = get_anomaly_detector()
    rows = await detector.get_recent_anomalies(days=days)
    clusters = cluster_anomalies(rows)
    for c in clusters:
        c["insight"] = None
        if settings.ANOMALY_CLUSTER_LLM_ENABLED:
            try:
                c["insight"] = await _cluster_insight(c)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cluster insight (groq) başarısız: %s", exc)
    return {"clusters": clusters, "period_days": days}
```
> `Annotated`, `Query`, `Kullanici`, `get_current_active_user`, `get_anomaly_detector`, `logger`, `Dict`, `Any` import teyit (anomalies.py mevcut). Yeni route mevcut `/{anomaly_id}` parametreli route YOKSA sorun değil; `/clusters` statik, çakışma için POST `/{id}/...` route'larından önce/sonra fark etmez (farklı method/segment).

- [ ] **Step 5:** Run → 3 passed.
- [ ] **Step 6:** ruff + mypy temiz.
- [ ] **Step 7:** Commit: `feat(anomaly): GET /anomalies/clusters + ANOMALY_CLUSTER_LLM_ENABLED (Groq best-effort)`

---

### Task 4: Günlük Celery task `anomaly.cluster_scan`

**Files:** Create `app/workers/tasks/anomaly_cluster_tasks.py`; Modify `celery_app.py` (beat + import); Test `app/tests/unit/test_anomaly_cluster_task.py`.

- [ ] **Step 1: Failing test**:
```python
from unittest.mock import AsyncMock, patch
import pytest
pytestmark = pytest.mark.unit


def test_cluster_scan_returns_cluster_count():
    rows = [
        {"id": i, "tip": "tuketim", "kaynak_tip": "arac", "kaynak_id": 1,
         "severity": "high", "sapma_yuzde": 25.0 + i} for i in range(3)
    ]
    with patch(
        "app.workers.tasks.anomaly_cluster_tasks.get_anomaly_detector"
    ) as mock_det:
        mock_det.return_value.get_recent_anomalies = AsyncMock(return_value=rows)
        from app.workers.tasks.anomaly_cluster_tasks import cluster_scan
        result = cluster_scan.run()
    assert result["clusters"] >= 1
    assert result["anomalies"] == 3
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement** `anomaly_cluster_tasks.py`:
```python
"""Faz 8 — günlük anomali kümeleme taraması (Celery beat)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.ml.anomaly_clustering import cluster_anomalies
from app.core.services.anomaly_detector import get_anomaly_detector
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run() -> dict[str, Any]:
    detector = get_anomaly_detector()
    rows = await detector.get_recent_anomalies(days=30)
    clusters = cluster_anomalies(rows)
    logger.info(
        "Anomali kümeleme: %s anomali → %s küme", len(rows), len(clusters)
    )
    for c in clusters[:5]:
        logger.info("  küme: %s", c["label"])
    return {"anomalies": len(rows), "clusters": len(clusters)}


@celery_app.task(
    bind=True, name="anomaly.cluster_scan", max_retries=1, acks_late=True
)
def cluster_scan(self) -> dict[str, Any]:  # noqa: ARG001
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("anomaly cluster scan failed: %s", exc, exc_info=True)
        return {"anomalies": 0, "clusters": 0, "error": str(exc)}
    finally:
        loop.close()
```

- [ ] **Step 4: Beat + import** (`celery_app.py`):
```python
            # Faz 8 — Her gün 05:00 UTC, anomali kümeleme taraması.
            "anomaly-cluster-scan-daily": {
                "task": "anomaly.cluster_scan",
                "schedule": crontab(hour=5, minute=0),
            },
```
import: `import app.workers.tasks.anomaly_cluster_tasks  # noqa: E402,F401`

- [ ] **Step 5:** Run → 1 passed + registration kontrolü.
- [ ] **Step 6:** Commit: `feat(anomaly): günlük cluster_scan Celery beat (05:00)`

---

### Task 5: Frontend — AnomalyClusters görünümü

**Files:** Modify `frontend/src/services/api/anomaly-service.ts` (getClusters); Create `frontend/src/components/alerts/AnomalyClusters.tsx`; Modify `frontend/src/pages/AlertsPage.tsx` (pattern alanına ekle); Test `frontend/src/components/alerts/__tests__/AnomalyClusters.test.tsx`.

- [ ] **Step 1: anomaly-service'e getClusters ekle**:
```typescript
export interface AnomalyCluster {
  cluster_id: number;
  size: number;
  dominant_tip: string;
  dominant_kaynak_tip: string;
  severity_dagilim: Record<string, number>;
  member_ids: number[];
  label: string;
  insight: string | null;
}
// anomalyService nesnesine:
  getClusters: async (days = 30): Promise<{ clusters: AnomalyCluster[]; period_days: number }> => {
    const res = await axiosInstance.get("/anomalies/clusters", { params: { days } });
    return res.data;
  },
```

- [ ] **Step 2: Failing test** (`AnomalyClusters.test.tsx`):
```typescript
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../services/api/anomaly-service", () => ({
  anomalyService: {
    getClusters: vi.fn().mockResolvedValue({
      period_days: 30,
      clusters: [
        { cluster_id: 0, size: 3, dominant_tip: "tuketim", dominant_kaynak_tip: "arac",
          severity_dagilim: { high: 3 }, member_ids: [1, 2, 3],
          label: "3 adet high tuketim anomalisi (arac kaynaklı)", insight: null },
      ],
    }),
  },
}));

describe("AnomalyClusters", () => {
  it("renders cluster labels", async () => {
    const { AnomalyClusters } = await import("../AnomalyClusters");
    render(<AnomalyClusters />);
    expect(await screen.findByText(/3 adet high tuketim/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3:** Run → FAIL.

- [ ] **Step 4: AnomalyClusters.tsx**:
```typescript
import { useQuery } from "@tanstack/react-query";
import { anomalyService } from "../../services/api/anomaly-service";

export function AnomalyClusters() {
  const { data, isLoading } = useQuery({
    queryKey: ["anomalyClusters", 30],
    queryFn: () => anomalyService.getClusters(30),
  });

  if (isLoading)
    return <p className="text-sm text-tertiary">Kümeler hesaplanıyor…</p>;

  const clusters = data?.clusters ?? [];
  if (clusters.length === 0)
    return (
      <p className="text-sm text-tertiary">
        Son {data?.period_days ?? 30} günde anlamlı bir anomali deseni yok.
      </p>
    );

  return (
    <div className="space-y-3">
      {clusters.map((c) => (
        <div
          key={c.cluster_id}
          className="rounded-card border border-border bg-surface p-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-primary">{c.label}</span>
            <span className="text-xs text-tertiary">{c.size} anomali</span>
          </div>
          {c.insight && (
            <p className="mt-1 text-xs text-secondary">{c.insight}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default AnomalyClusters;
```

- [ ] **Step 5:** Run → 1 passed.
- [ ] **Step 6: AlertsPage entegrasyonu** — pattern sekmesinde (PatternList yanına/üstüne) `<AnomalyClusters />` render et. AlertsPage testini koş → regresyon yok.
- [ ] **Step 7:** Commit: `feat(anomaly): AnomalyClusters görünümü (AlertsPage pattern)`

---

### Task 6: Gate'ler + e2e + merge

- [ ] **Step 1:** Backend ruff + mypy temiz.
- [ ] **Step 2:** Backend yeni testler (clustering + clusters endpoint + task) + anomalies regresyon pass.
- [ ] **Step 3:** Frontend lint + AnomalyClusters + AlertsPage test + build pass.
- [ ] **Step 4: e2e:** `cluster_anomalies` gerçek anomali verisiyle (dev DB'de varsa) ≥1 küme; `GET /anomalies/clusters` 200. (Groq kapalı default; flag açık ve Groq erişilebilirse insight dolar.)
- [ ] **Step 5:** main'e ff-merge + push.

---

## Self-Review

- **Spec kapsaması:** anomaly_clustering.py DBSCAN (Task 2), günlük Celery task (Task 4), GET /anomalies/clusters (Task 3), AlertsPage pattern görünümü (Task 5), Groq insight feature-flag (Task 3 `ANOMALY_CLUSTER_LLM_ENABLED` + best-effort). Kabul "≥1 anlamlı cluster; LLM flag arkasında, Groq kesintisi bloklamaz" → Task 2 test + Task 3 (insight=None on fail).
- **Placeholder:** Yok. Teyit: anomalies.py importlar (Task 3), AlertsPage pattern entegrasyon noktası (Task 5).
- **İsim tutarlılığı:** `cluster_anomalies(rows, eps, min_samples)` → {cluster_id,size,dominant_tip,dominant_kaynak_tip,severity_dagilim,member_ids,label}; endpoint `insight` ekler. `anomalyService.getClusters`/`AnomalyCluster`/`AnomalyClusters`.
- **best-effort:** Groq insight try/except → None; task hata → {clusters:0,error}; sklearn import fonksiyon içinde (modül yükleme maliyeti yalnız çağrıda).
