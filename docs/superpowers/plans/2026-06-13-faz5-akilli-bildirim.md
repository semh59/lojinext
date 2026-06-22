# Faz 5 — Akıllı Bildirim Akışı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans veya subagent-driven-development. Checkbox (`- [ ]`) adımları.

**Goal:** Bildirim önceliklendirme (kullanıcı geçmiş okuma davranışına göre), sessiz saatler, ve haftalık "dikkat etmen gereken 3 şey" digest'i (Celery beat) + sessiz saat ayar UI'ı — Faz 4 push'unun üzerine, bildirim yorgunluğunu azaltır.

**Architecture:** (1) `NotificationPrioritizer` — `bildirim_gecmisi`'ndeki olay_tipi bazlı okuma oranından öncelik (high/normal/low). (2) Sessiz saatler — mevcut `/preferences` deposu (`KullaniciAyari`, modul="bildirim") + `is_within_quiet_hours` helper; `send_push_to_user`'a `respect_quiet_hours`. (3) Haftalık digest — `notifications.weekly_digest` Celery beat (Pazartesi), `aggregate_today_triage` top-3 → push (sessiz saate saygılı) + `bildirim_gecmisi` kaydı. (4) Frontend: sessiz saat ayar UI'ı (`/preferences` üzerinden).

**Tech Stack:** FastAPI, SQLAlchemy async, Celery beat, React + React Query, pytest, vitest. Yeni bağımlılık yok.

**Önkoşullar (kod doğrulandı 2026-06-13):**
- `PreferenceService.get_preferences(user_id, modul, ayar_tipi)` → `KullaniciAyari` listesi (her biri `.deger` JSONB). `save_preference(user_id, modul, ayar_tipi, deger, ad, is_default)`. Endpoint: `GET /preferences/{modul}`, `POST /preferences`. → Sessiz saat için **yeni storage endpoint gerekmez**.
- `BildirimGecmisi`: kullanici_id, olay_tipi, durum, `okundu_tarihi` (None=okunmadı), olusturma_tarihi → prioritizer sinyali (okuma oranı).
- `push_sender.send_push_to_user(user_id, *, title, body, url, uow)` ve `send_push_broadcast(...)` (Faz 4). VAPID ayarsızsa no-op.
- `triage_aggregator.aggregate_today_triage(...) -> TodayTriage` (items priority-sıralı) — digest top-3 kaynağı. Çağrı imzasını implementasyonda teyit et (uow/days param).
- Celery beat: `celery_app.py` `beat_schedule` + alt `import app.workers.tasks.<mod>`. Task pattern: `new_event_loop + run_until_complete`.
- Lokal faithful test: bkz [[local-test-db-execution]].

---

### Task 1: Faz 5 branch

- [ ] **Step 1:** `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -1; git checkout -b feat/faz5-akilli-bildirim main`

---

### Task 2: NotificationPrioritizer (okuma-oranı önceliklendirme)

**Files:** Create `app/core/services/notification_prioritizer.py`; Test `app/tests/unit/test_notification_prioritizer.py`.

- [ ] **Step 1: Failing test**

```python
"""NotificationPrioritizer testleri."""
import pytest
from app.core.services.notification_prioritizer import score_priority

pytestmark = pytest.mark.unit


def test_high_read_rate_is_high_priority():
    # 8/10 okunmuş bir olay tipi → önemli (high)
    assert score_priority(read=8, total=10) == "high"


def test_low_read_rate_is_low_priority():
    # 1/20 okunmuş → kullanıcı umursamıyor (low)
    assert score_priority(read=1, total=20) == "low"


def test_insufficient_history_is_normal():
    # az veri → normal (varsayılan)
    assert score_priority(read=0, total=2) == "normal"
    assert score_priority(read=0, total=0) == "normal"
```

- [ ] **Step 2:** Run → FAIL (ModuleNotFound). `python -m pytest app/tests/unit/test_notification_prioritizer.py -q`

- [ ] **Step 3: Implement**

```python
"""Faz 5 — bildirim önceliklendirme: kullanıcı geçmiş okuma davranışı.

olay_tipi bazlı okuma oranı (okundu/toplam) → öncelik. Yeterli geçmiş yoksa
'normal'. Yüksek okuma oranı = kullanıcı umursuyor = high; düşük = low.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

# Anlamlı bir oran için minimum geçmiş örnek sayısı.
_MIN_HISTORY = 5
_HIGH_THRESHOLD = 0.6
_LOW_THRESHOLD = 0.2


def score_priority(*, read: int, total: int) -> str:
    """Okuma oranından öncelik döndürür: 'high' | 'normal' | 'low'."""
    if total < _MIN_HISTORY:
        return "normal"
    rate = read / total
    if rate >= _HIGH_THRESHOLD:
        return "high"
    if rate <= _LOW_THRESHOLD:
        return "low"
    return "normal"


class NotificationPrioritizer:
    """bildirim_gecmisi okuma oranından kullanıcı+olay_tipi önceliği."""

    def __init__(self, session) -> None:
        self.session = session

    async def priority_for(self, *, user_id: int, olay_tipi: Optional[str]) -> str:
        from app.database.models import BildirimGecmisi

        if not olay_tipi:
            return "normal"
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(BildirimGecmisi)
                .where(BildirimGecmisi.kullanici_id == user_id)
                .where(BildirimGecmisi.olay_tipi == olay_tipi)
            )
        ).scalar() or 0
        read = (
            await self.session.execute(
                select(func.count())
                .select_from(BildirimGecmisi)
                .where(BildirimGecmisi.kullanici_id == user_id)
                .where(BildirimGecmisi.olay_tipi == olay_tipi)
                .where(BildirimGecmisi.okundu_tarihi.isnot(None))
            )
        ).scalar() or 0
        return score_priority(read=int(read), total=int(total))
```

- [ ] **Step 4:** Run → 3 passed.
- [ ] **Step 5:** Commit: `feat(notif): NotificationPrioritizer (okuma-oranı önceliklendirme)`

---

### Task 3: Sessiz saatler helper + push entegrasyonu

**Files:** Create `app/core/services/quiet_hours.py`; Modify `app/core/services/push_sender.py` (send_push_to_user'a `respect_quiet_hours`); Test `app/tests/unit/test_quiet_hours.py`.

- [ ] **Step 1: Failing test**

```python
"""Sessiz saat helper testleri."""
from datetime import time
import pytest
from app.core.services.quiet_hours import is_within_quiet_hours

pytestmark = pytest.mark.unit


def _prefs(enabled, start, end):
    return {"enabled": enabled, "start": start, "end": end}


def test_disabled_never_quiet():
    assert is_within_quiet_hours(_prefs(False, "22:00", "07:00"), time(23, 0)) is False


def test_overnight_range_inside():
    p = _prefs(True, "22:00", "07:00")
    assert is_within_quiet_hours(p, time(23, 30)) is True
    assert is_within_quiet_hours(p, time(6, 0)) is True


def test_overnight_range_outside():
    p = _prefs(True, "22:00", "07:00")
    assert is_within_quiet_hours(p, time(12, 0)) is False


def test_same_day_range():
    p = _prefs(True, "09:00", "17:00")
    assert is_within_quiet_hours(p, time(10, 0)) is True
    assert is_within_quiet_hours(p, time(20, 0)) is False


def test_malformed_prefs_safe():
    assert is_within_quiet_hours({}, time(3, 0)) is False
    assert is_within_quiet_hours({"enabled": True, "start": "x"}, time(3, 0)) is False
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement quiet_hours.py**

```python
"""Faz 5 — sessiz saatler. /preferences (modul='bildirim', ayar_tipi=
'quiet_hours', deger={enabled, start 'HH:MM', end 'HH:MM'}) ile saklanır.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Optional


def _parse(hhmm: Any) -> Optional[time]:
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return None
    try:
        h, m = hhmm.split(":", 1)
        return time(int(h), int(m))
    except (ValueError, TypeError):
        return None


def is_within_quiet_hours(deger: dict, now_t: time) -> bool:
    """deger sözlüğüne göre now_t sessiz saat aralığında mı.

    Gece-aşırı aralıkları (22:00→07:00) doğru ele alır. Hatalı/eksik
    ayar → False (güvenli; sessiz değil).
    """
    if not isinstance(deger, dict) or not deger.get("enabled"):
        return False
    start = _parse(deger.get("start"))
    end = _parse(deger.get("end"))
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now_t <= end
    # gece-aşırı: start..gece yarısı veya gece yarısı..end
    return now_t >= start or now_t <= end


async def is_user_quiet_now(
    user_id: int, *, now: Optional[datetime] = None
) -> bool:
    """Kullanıcının /preferences sessiz saat ayarına göre şu an sessiz mi."""
    from app.core.services.preference_service import PreferenceService

    items = await PreferenceService().get_preferences(
        user_id, "bildirim", "quiet_hours"
    )
    if not items:
        return False
    deger = getattr(items[0], "deger", None) or (
        items[0].get("deger") if isinstance(items[0], dict) else None
    )
    if not isinstance(deger, dict):
        return False
    current = (now or datetime.now(timezone.utc)).time()
    return is_within_quiet_hours(deger, current)
```

- [ ] **Step 4:** Run → 6 passed.

- [ ] **Step 5: send_push_to_user'a respect_quiet_hours ekle**

`push_sender.send_push_to_user` imzasına `respect_quiet_hours: bool = False` ekle; True ise gönderimden önce:

```python
    if respect_quiet_hours:
        from app.core.services.quiet_hours import is_user_quiet_now

        if await is_user_quiet_now(user_id):
            logger.debug("Kullanıcı %s sessiz saatte; push atlandı", user_id)
            return PushSendResult(sent=0, expired=0, failed=0)
```
(VAPID kontrolünden hemen sonra, payload oluşturmadan önce.)

- [ ] **Step 6:** Run mevcut push testleri (regresyon): `python -m pytest app/tests/unit/test_push_sender.py app/tests/unit/test_push_broadcast.py -q` → pass.

- [ ] **Step 7:** Commit: `feat(notif): sessiz saatler helper + send_push_to_user respect_quiet_hours`

---

### Task 4: Haftalık digest Celery beat task

**Files:** Create `app/workers/tasks/notification_tasks.py`; Modify `celery_app.py` (beat + import); Test `app/tests/unit/test_weekly_digest_task.py`.

- [ ] **Step 1: Failing test**

```python
"""notifications.weekly_digest task testi."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

pytestmark = pytest.mark.unit


@asynccontextmanager
async def _fake_uow():
    yield MagicMock()


def test_weekly_digest_pushes_top3_to_subscribed_users():
    triage = SimpleNamespace(
        items=[
            SimpleNamespace(baslik="A", severity="high"),
            SimpleNamespace(baslik="B", severity="medium"),
            SimpleNamespace(baslik="C", severity="low"),
            SimpleNamespace(baslik="D", severity="low"),
        ]
    )
    with (
        patch("app.workers.tasks.notification_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.notification_tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[7, 8]),
        ),
        patch(
            "app.workers.tasks.notification_tasks.aggregate_today_triage",
            new=AsyncMock(return_value=triage),
        ),
        patch(
            "app.workers.tasks.notification_tasks.send_push_to_user",
            new=AsyncMock(),
        ) as mock_push,
    ):
        from app.workers.tasks.notification_tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 2
    assert mock_push.await_count == 2
    _, kwargs = mock_push.await_args
    assert "A" in kwargs["body"] and "C" in kwargs["body"] and "D" not in kwargs["body"]
    assert kwargs["respect_quiet_hours"] is True


def test_weekly_digest_no_subscribers():
    with (
        patch("app.workers.tasks.notification_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.notification_tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.workers.tasks.notification_tasks.send_push_to_user", new=AsyncMock()
        ) as mock_push,
    ):
        from app.workers.tasks.notification_tasks import weekly_digest

        result = weekly_digest.run()
    assert result["users"] == 0
    mock_push.assert_not_awaited()
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Implement notification_tasks.py**

```python
"""Faz 5 — haftalık 'dikkat etmen gereken 3 şey' digest (Celery beat)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.core.services.push_sender import send_push_to_user
from app.core.services.triage_aggregator import aggregate_today_triage
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _distinct_subscriber_ids(uow) -> list[int]:
    from app.database.models import PushSubscription

    rows = await uow.session.execute(
        select(PushSubscription.user_id).distinct()
    )
    return [int(r) for r in rows.scalars().all() if r is not None]


def _digest_body(triage) -> str:
    items = getattr(triage, "items", []) or []
    top3 = items[:3]
    if not top3:
        return "Bu hafta dikkat gerektiren acil bir konu görünmüyor."
    lines = [f"• {getattr(i, 'baslik', '—')}" for i in top3]
    return "Bu hafta dikkat etmen gereken 3 şey:\n" + "\n".join(lines)


async def _run_weekly_digest() -> dict[str, Any]:
    async with UnitOfWork() as uow:
        user_ids = await _distinct_subscriber_ids(uow)
        if not user_ids:
            return {"users": 0, "pushed": 0}
        triage = await aggregate_today_triage(uow=uow)
        body = _digest_body(triage)
        pushed = 0
        for uid in user_ids:
            res = await send_push_to_user(
                uid,
                title="Haftalık Özet",
                body=body,
                url="/today",
                uow=uow,
                respect_quiet_hours=True,
            )
            pushed += getattr(res, "sent", 0)
    return {"users": len(user_ids), "pushed": pushed}


@celery_app.task(
    bind=True, name="notifications.weekly_digest", max_retries=1, acks_late=True
)
def weekly_digest(self) -> dict[str, Any]:  # noqa: ARG001
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_weekly_digest())
    except Exception as exc:  # noqa: BLE001
        logger.error("weekly digest failed: %s", exc, exc_info=True)
        return {"users": 0, "pushed": 0, "error": str(exc)}
    finally:
        loop.close()
```

> Not: `aggregate_today_triage` imzasını teyit et (uow kwarg veya pozisyonel/days). Test'te mock'landığı için unit geçer; gerçek imza farklıysa `_run_weekly_digest`'teki çağrıyı imzaya uydur (Task 6 e2e'de doğrulanır).

- [ ] **Step 4:** Beat + import. `celery_app.py` beat_schedule'a:

```python
            # Faz 5 — Pazartesi 08:00 UTC, haftalık "dikkat etmen gereken 3 şey".
            "notifications-weekly-digest-mondays": {
                "task": "notifications.weekly_digest",
                "schedule": crontab(day_of_week="mon", hour=8, minute=0),
            },
```
import bloğuna: `import app.workers.tasks.notification_tasks  # noqa: E402,F401`

- [ ] **Step 5:** Run → 2 passed. Registration: `python -c "from app.infrastructure.background.celery_app import celery_app as c; assert 'notifications.weekly_digest' in c.tasks; print('OK')"`
- [ ] **Step 6:** Commit: `feat(notif): haftalık digest Celery beat (top-3, sessiz saate saygılı)`

---

### Task 5: Frontend — sessiz saat ayar UI'ı

**Files:** Create `frontend/src/components/settings/QuietHoursSettings.tsx`; Modify `frontend/src/services/api/` (preference kullanımı — mevcut preference-service varsa onu kullan, yoksa axiosInstance ile `/preferences`); Test `frontend/src/components/settings/__tests__/QuietHoursSettings.test.tsx`.

- [ ] **Step 1: Mevcut preference frontend servisi var mı?**

Run: `ls frontend/src/services/api | grep -i pref; grep -rln "/preferences" frontend/src/services 2>/dev/null | head`
Expected: varsa onu kullan; yoksa QuietHoursSettings doğrudan `axiosInstance` ile `GET /preferences/bildirim?ayar_tipi=quiet_hours` + `POST /preferences` çağırır.

- [ ] **Step 2: Failing test**

`QuietHoursSettings.test.tsx`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../services/api/axios-instance", () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: { items: [{ deger: { enabled: true, start: "22:00", end: "07:00" } }] },
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

describe("QuietHoursSettings", () => {
  it("loads and shows the saved quiet hours", async () => {
    const { default: QuietHoursSettings } = await import("../QuietHoursSettings");
    render(<QuietHoursSettings />);
    expect(await screen.findByDisplayValue("22:00")).toBeInTheDocument();
    expect(screen.getByDisplayValue("07:00")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3:** Run → FAIL: `cd frontend && npx vitest --run src/components/settings/__tests__/QuietHoursSettings.test.tsx`

- [ ] **Step 4: Implement QuietHoursSettings.tsx**

```typescript
import { useEffect, useState } from "react";
import axiosInstance from "../../services/api/axios-instance";

interface QuietHours {
  enabled: boolean;
  start: string;
  end: string;
}

const DEFAULT: QuietHours = { enabled: false, start: "22:00", end: "07:00" };

export default function QuietHoursSettings() {
  const [qh, setQh] = useState<QuietHours>(DEFAULT);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    axiosInstance
      .get("/preferences/bildirim", { params: { ayar_tipi: "quiet_hours" } })
      .then((r) => {
        const item = r.data?.items?.[0];
        if (item?.deger) setQh({ ...DEFAULT, ...item.deger });
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    await axiosInstance.post("/preferences", {
      modul: "bildirim",
      ayar_tipi: "quiet_hours",
      deger: qh,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="rounded-modal border border-border bg-surface p-4 space-y-3">
      <h3 className="text-sm font-semibold text-secondary">Sessiz Saatler</h3>
      <label className="flex items-center gap-2 text-sm text-primary">
        <input
          type="checkbox"
          checked={qh.enabled}
          onChange={(e) => setQh({ ...qh, enabled: e.target.checked })}
        />
        Sessiz saatlerde bildirim gönderme
      </label>
      <div className="flex items-center gap-3">
        <label className="text-sm text-tertiary">
          Başlangıç
          <input
            type="time"
            value={qh.start}
            onChange={(e) => setQh({ ...qh, start: e.target.value })}
            className="ml-2 rounded-card border border-border bg-elevated px-2 py-1"
          />
        </label>
        <label className="text-sm text-tertiary">
          Bitiş
          <input
            type="time"
            value={qh.end}
            onChange={(e) => setQh({ ...qh, end: e.target.value })}
            className="ml-2 rounded-card border border-border bg-elevated px-2 py-1"
          />
        </label>
      </div>
      <button
        onClick={save}
        className="rounded-card bg-elevated px-3 py-1 text-sm text-primary"
      >
        {saved ? "Kaydedildi ✓" : "Kaydet"}
      </button>
    </div>
  );
}
```

- [ ] **Step 5:** Run → 1 passed.
- [ ] **Step 6: ProfilePage'e (veya ayarlar) ekle** — `frontend/src/pages/ProfilePage.tsx`'e `<QuietHoursSettings />` import + render (mevcut bir ayarlar bölümünün yanına). ProfilePage testini koş → regresyon yok.
- [ ] **Step 7:** Commit: `feat(notif): sessiz saat ayar UI'ı (QuietHoursSettings)`

---

### Task 6: Gate'ler + e2e + merge

- [ ] **Step 1:** Backend ruff + mypy → temiz.
- [ ] **Step 2:** Backend yeni testler: prioritizer + quiet_hours + weekly_digest + push regresyon → pass.
- [ ] **Step 3:** Frontend lint + QuietHoursSettings test + build → pass.
- [ ] **Step 4: e2e (faithful):** `_run_weekly_digest` gerçek imzayla koşar mı — `aggregate_today_triage(uow=...)` imzasını teyit; gerekirse düzelt + test güncelle. NotificationPrioritizer'ı gerçek DB'de bir-iki BildirimGecmisi satırıyla doğrula (opsiyonel).
- [ ] **Step 5:** main'e ff-merge + push.

---

## Self-Review

- **Spec kapsaması:** prioritizer (Task 2), sessiz saatler (Task 3 + push entegrasyonu), haftalık digest beat (Task 4), ayar UI (Task 5). Kabul "önceliklendirme + sessiz saat çalışır; digest beat ile üretilir" → Task 2/3/4. "gerçek tarayıcı push teslimi" Faz 4 ile aynı manuel VAPID kaydı gerektirir (dürüstçe işaretlenir).
- **Placeholder:** Yok. İki teyit notu (aggregate_today_triage imzası Task 4/6; frontend preference servisi Task 5 Step 1).
- **İsim tutarlılığı:** `score_priority(read,total)` + `NotificationPrioritizer.priority_for`; `is_within_quiet_hours(deger,now_t)` + `is_user_quiet_now(user_id)`; `weekly_digest` task; `send_push_to_user(..., respect_quiet_hours=)`.
- **best-effort:** quiet-hours okuma hatası → False (sessiz değil, güvenli); digest push hataları kullanıcı bazında izole.
