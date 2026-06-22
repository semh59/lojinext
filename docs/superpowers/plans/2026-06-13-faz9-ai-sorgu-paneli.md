# Faz 9 — AI Sorgulama Paneli Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox (`- [ ]`) adımları.

**Goal:** Mevcut `/ai/chat` üstüne sorgu kategorileri + otomatik grafik (≥1 kategori) + cevap içi aksiyon linkleri + Web Speech sesli komut.

**Architecture:** Backend `POST /ai/query` (kategori-farkında): `fuel_trend` kategorisi `yakit_alimlari`'ndan aylık toplam tutarı **deterministik** sorgulayıp chart spec üretir + LLM anlatı (best-effort) + aksiyon linki; `general` kategorisi LLM cevabı. (LLM'in chart JSON üretmesine güvenmek yerine grafiği gerçek veriden deterministik kuruyoruz — güvenilir + "hayali kod yok".) Frontend `AiQueryPanel`: kategori seçici → sorgu → recharts grafik + aksiyon linkleri + Web Speech sesli giriş.

**Tech Stack:** FastAPI, SQLAlchemy text, React + recharts + react-router, Web Speech API, pytest, vitest.

**Önkoşullar (kod doğrulandı 2026-06-13):**
- `POST /ai/chat`: `ChatRequest{message,history}` → `{response, timestamp}`; `get_ai_service().generate_response(user_input=) -> str`. `ChatRequest` ai.py içinde inline BaseModel.
- ai.py importlar: `Annotated`, `Depends`, `get_current_active_user`, `Kullanici`, `get_ai_service`, `datetime/timezone`, `BaseModel/Field`. Yeni: `SessionDep`, `text`.
- Frontend: `aiApi` (`services/api/ai-service.ts`, `chat` metodu var); `ChatAssistant.tsx`; recharts (FuelPage'de kullanılıyor — `LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer`).
- react-router `Link` (App BrowserRouter). Test wrapper `test/test-utils` MemoryRouter sağlar.
- yakit_alimlari kolonları: tarih (date), toplam_tutar, arac_id... (Task 2'de `is_deleted` varlığı teyit).
- Lokal faithful test: bkz [[local-test-db-execution]]. `docker exec pytest /app/...` → `bash -c "cd /app && pytest"`.

---

### Task 1: Branch
- [ ] `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -1; git checkout -b feat/faz9-ai-sorgu-paneli main`

---

### Task 2: Backend `POST /ai/query` (kategori + chart + actions)

**Files:** Modify `app/api/v1/endpoints/ai.py`; Test `app/tests/api/test_ai_query.py`.

- [ ] **Step 0: yakit_alimlari is_deleted teyit**

Run: `docker exec faz9-runner bash -c "cd /app && python -c \"from app.database.models import YakitAlimi; print([c.name for c in YakitAlimi.__table__.columns])\""`
Expected: kolon listesi; `is_deleted` varsa sorguya `WHERE is_deleted=false` ekle, yoksa filtre koyma. `tarih` ve `toplam_tutar` mevcut olmalı.

- [ ] **Step 1: Failing test** (`app/tests/api/test_ai_query.py`):

```python
"""POST /ai/query testleri."""
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_general_category_returns_answer(async_client, normal_auth_headers):
    with patch("app.api.v1.endpoints.ai.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(return_value="Merhaba!")
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "selam", "category": "general"},
            headers=normal_auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Merhaba!"
    assert body["chart"] is None


async def test_fuel_trend_returns_chart_and_action(
    async_client, admin_auth_headers, db_session
):
    # iki farklı ay için yakıt kaydı (chart ≥1 nokta)
    from app.database.models import Arac
    arac = Arac(plaka="34AI001", marka="M", model="A", yil=2022,
                tank_kapasitesi=600, hedef_tuketim=30.0, aktif=True,
                bos_agirlik_kg=8000)
    db_session.add(arac)
    await db_session.commit()
    await db_session.refresh(arac)
    await db_session.execute(
        text("INSERT INTO yakit_alimlari (arac_id, tarih, litre, toplam_tutar, fiyat_tl, km_sayac) "
             "VALUES (:a, '2026-01-15', 100, 4000, 40, 1000), "
             "       (:a, '2026-02-15', 120, 5000, 41.6, 2000)"),
        {"a": arac.id},
    )
    await db_session.commit()

    with patch("app.api.v1.endpoints.ai.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(return_value="Trend yukarı.")
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "yakıt trendi", "category": "fuel_trend"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chart"] is not None
    assert body["chart"]["type"] == "line"
    assert len(body["chart"]["data"]) >= 2
    assert any(a["url"] == "/fuel" for a in body["actions"])


async def test_query_requires_auth(async_client):
    resp = await async_client.post("/api/v1/ai/query", json={"message": "x", "category": "general"})
    assert resp.status_code == 401


async def test_fuel_trend_llm_failure_still_returns_chart(
    async_client, admin_auth_headers
):
    with patch("app.api.v1.endpoints.ai.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(side_effect=RuntimeError("groq down"))
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "yakıt", "category": "fuel_trend"},
            headers=admin_auth_headers,
        )
    # LLM düşse de 200 + chart (boş olabilir) + actions döner
    assert resp.status_code == 200
    assert "actions" in resp.json()
```

- [ ] **Step 2:** Run → FAIL (404).

- [ ] **Step 3: Endpoint** (`ai.py`). İmport ekle: `from app.api.deps import SessionDep` (mevcut import satırına), `from sqlalchemy import text`. Şemalar + endpoint:

```python
class AiQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    category: str = Field("general", max_length=40)


async def _fuel_trend_chart(db) -> dict | None:
    """yakit_alimlari aylık toplam tutar → line chart spec (deterministik)."""
    rows = (
        await db.execute(
            text(
                "SELECT to_char(date_trunc('month', tarih), 'YYYY-MM') AS ay, "
                "COALESCE(SUM(toplam_tutar), 0) AS tutar "
                "FROM yakit_alimlari "
                "WHERE tarih >= now() - make_interval(months => 12) "
                "GROUP BY 1 ORDER BY 1"
            )
        )
    ).mappings().all()
    data = [{"ay": r["ay"], "tutar": float(r["tutar"])} for r in rows]
    if not data:
        return None
    return {
        "type": "line",
        "title": "Aylık Yakıt Maliyeti (TL)",
        "x_key": "ay",
        "series": [{"key": "tutar", "label": "Toplam Tutar"}],
        "data": data,
    }


@router.post("/query")
async def ai_query(
    request: AiQueryRequest,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> dict:
    """Kategori-farkında AI sorgu: fuel_trend → grafik+aksiyon, general → LLM."""
    chart = None
    actions: list[dict] = []
    if request.category == "fuel_trend":
        chart = await _fuel_trend_chart(db)
        actions = [{"label": "Yakıt sayfası", "url": "/fuel"}]

    try:
        prompt = request.message
        if request.category == "fuel_trend" and chart:
            prompt = (
                f"{request.message}\n\nAylık yakıt maliyeti verisi: "
                f"{chart['data'][-6:]}. Kısa Türkçe yorumla."
            )
        answer = await get_ai_service().generate_response(user_input=prompt)
    except Exception:  # noqa: BLE001 — LLM kesintisi grafiği/aksiyonu bloklamaz
        answer = (
            "Yapay zeka yorumu şu an üretilemedi; grafik ve veriler aşağıda."
            if chart
            else "Yapay zeka şu an yanıt veremiyor."
        )

    return {
        "category": request.category,
        "answer": answer,
        "chart": chart,
        "actions": actions,
    }
```
> `get_ai_service().generate_response` async mı senkron mu teyit (ai.py:46 `await ... generate_response` kullanıyor → async). `is_deleted` Step 0'da çıktıysa sorguya ekle.

- [ ] **Step 4:** Run → 4 passed.
- [ ] **Step 5:** ruff + mypy temiz.
- [ ] **Step 6:** Commit: `feat(ai): POST /ai/query — kategori-farkında AI sorgu (fuel_trend grafik + aksiyon)`

---

### Task 3: Frontend — AiQueryPanel (kategori + grafik + aksiyon + ses)

**Files:** Modify `frontend/src/services/api/ai-service.ts` (query); Create `frontend/src/components/ai/AiQueryPanel.tsx`; Test `frontend/src/components/ai/__tests__/AiQueryPanel.test.tsx`.

- [ ] **Step 1: ai-service'e query ekle**:
```typescript
export interface AiChartSpec {
  type: string;
  title: string;
  x_key: string;
  series: { key: string; label: string }[];
  data: Record<string, unknown>[];
}
export interface AiQueryResponse {
  category: string;
  answer: string;
  chart: AiChartSpec | null;
  actions: { label: string; url: string }[];
}
// aiApi nesnesine:
  query: async (message: string, category: string): Promise<AiQueryResponse> => {
    const res = await axiosInstance.post<AiQueryResponse>("/ai/query", { message, category });
    return res.data;
  },
```

- [ ] **Step 2: Failing test** (`AiQueryPanel.test.tsx`):
```typescript
import { describe, expect, it, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../services/api/ai-service", () => ({
  aiApi: {
    query: vi.fn().mockResolvedValue({
      category: "fuel_trend",
      answer: "Trend yukarı.",
      chart: { type: "line", title: "Aylık Yakıt Maliyeti (TL)", x_key: "ay",
        series: [{ key: "tutar", label: "Toplam Tutar" }],
        data: [{ ay: "2026-01", tutar: 4000 }, { ay: "2026-02", tutar: 5000 }] },
      actions: [{ label: "Yakıt sayfası", url: "/fuel" }],
    }),
  },
}));

describe("AiQueryPanel", () => {
  it("runs a query and renders answer, chart title and action link", async () => {
    const { AiQueryPanel } = await import("../AiQueryPanel");
    render(<AiQueryPanel />);
    fireEvent.change(screen.getByPlaceholderText(/sor/i), {
      target: { value: "yakıt trendi" },
    });
    fireEvent.click(screen.getByText("Sorgula"));
    expect(await screen.findByText("Trend yukarı.")).toBeInTheDocument();
    expect(screen.getByText(/Aylık Yakıt Maliyeti/)).toBeInTheDocument();
    const link = screen.getByText("Yakıt sayfası").closest("a");
    expect(link).toHaveAttribute("href", "/fuel");
  });
});
```

- [ ] **Step 3:** Run → FAIL.

- [ ] **Step 4: AiQueryPanel.tsx**:
```typescript
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { aiApi, type AiQueryResponse } from "../../services/api/ai-service";

const CATEGORIES = [
  { value: "general", label: "Genel" },
  { value: "fuel_trend", label: "Yakıt Trendi" },
];

// Web Speech API tipi (tarayıcı)
type SpeechRecognitionCtor = new () => {
  lang: string;
  onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void;
  start: () => void;
};

export function AiQueryPanel() {
  const [category, setCategory] = useState("general");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<AiQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      setResult(await aiApi.query(message, category));
    } finally {
      setLoading(false);
    }
  };

  const startVoice = () => {
    const w = window as unknown as {
      SpeechRecognition?: SpeechRecognitionCtor;
      webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = "tr-TR";
    rec.onresult = (e) => setMessage(e.results[0][0].transcript);
    rec.start();
  };

  return (
    <div className="rounded-modal border border-border bg-surface p-4 space-y-3">
      <div className="flex gap-2">
        <select
          aria-label="Sorgu kategorisi"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-card border border-border bg-elevated px-2 py-1 text-sm"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <input
          placeholder="Filo hakkında sor…"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="flex-1 rounded-card border border-border bg-elevated px-2 py-1 text-sm"
        />
        <button type="button" onClick={startVoice} aria-label="Sesli komut"
          className="rounded-card bg-elevated px-2 py-1 text-sm">🎤</button>
        <button type="button" onClick={run}
          className="rounded-card bg-elevated px-3 py-1 text-sm text-primary">
          {loading ? "…" : "Sorgula"}
        </button>
      </div>

      {result && (
        <div className="space-y-3">
          <p className="text-sm text-primary whitespace-pre-line">{result.answer}</p>
          {result.chart && (
            <div className="rounded-card border border-border bg-elevated p-3">
              <h4 className="mb-2 text-xs font-semibold text-secondary">
                {result.chart.title}
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={result.chart.data}>
                  <XAxis dataKey={result.chart.x_key} fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  {result.chart.series.map((s) => (
                    <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {result.actions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {result.actions.map((a) => (
                <Link key={a.url} to={a.url}
                  className="rounded-card bg-elevated px-3 py-1 text-sm text-accent">
                  {a.label} →
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AiQueryPanel;
```

- [ ] **Step 5:** Run → 1 passed.
- [ ] **Step 6: ChatAssistant'a entegre** — ChatAssistant panelinin içine `<AiQueryPanel />` ekle (mesaj listesinin üstüne veya bir sekme). ChatAssistant testini koş → regresyon yok.
- [ ] **Step 7:** Commit: `feat(ai): AiQueryPanel — kategori/grafik/aksiyon/sesli komut (ChatAssistant)`

---

### Task 4: Gate'ler + e2e + merge

- [ ] **Step 1:** Backend ruff + mypy temiz.
- [ ] **Step 2:** Backend `test_ai_query.py` + ai regresyon (test_ai*) pass.
- [ ] **Step 3:** Frontend lint + AiQueryPanel + ChatAssistant test + build pass.
- [ ] **Step 4: e2e (canlı):** backend rebuild; `POST /ai/query {category:"fuel_trend"}` → 200 + chart (dev'de yakıt verisi var, Faz 1/3'ten) + action `/fuel`. `general` → LLM cevabı (Groq erişimine bağlı; erişilemezse fallback metin, yine 200).
- [ ] **Step 5:** main'e ff-merge + push.

---

## Self-Review

- **Spec kapsaması:** sorgu kategorileri (Task 2 category + Task 3 selector), otomatik grafik ≥1 tip (Task 2 fuel_trend deterministik chart), aksiyon linkleri (Task 2 actions + Task 3 Link), Web Speech sesli komut (Task 3 startVoice). Kabul "kategori seçimiyle sorgu; ≥1 tipte grafik; aksiyon linki doğru sayfaya" → Task 2/3 testleri.
- **Placeholder:** Yok. Teyit: yakit_alimlari is_deleted (Task 2 Step 0), generate_response async (Task 2 Step 3), ChatAssistant entegrasyon (Task 3 Step 6).
- **İsim tutarlılığı:** `POST /ai/query` {message,category} → {category,answer,chart,actions}; `aiApi.query`/`AiQueryResponse`/`AiChartSpec`; `AiQueryPanel`.
- **best-effort:** LLM hatası → grafik+aksiyon yine döner (answer fallback); chart yoksa null. Grafik LLM'e değil gerçek DB verisine dayanır (hayali veri yok).
