# Feature A — Şoför Koçluk Modülü (Mini-Plan v2 — Detaylı)

> **v1 vs v2:** v1 (`2026-05-22-feature-a-driver-coaching-mini-plan.md`) iskelet planıydı. v2 her alt-görev için somut SQL/kod/prompt/şema/test senaryoları içerir — direkt uygulamaya geçilebilir.

**Üst plan:** `2026-05-21-frontend-derinlik-ve-yeni-ozellikler.md` Faz 2 → Sprint 4 → Feature A.

---

## 0. Bağlam ve Veri Akışı

### 0.1 Mevcut altyapı sözleşmeleri

| Bileşen | Konum | Kullanılacak API |
|---------|-------|-----------------|
| Groq LLM (llama-3.1-70b-versatile) | `app/core/ai/groq_service.py:79` | `await groq.chat(user_message, system_prompt, temperature, max_tokens)` |
| RAG (FAISS, sentence-transformers all-MiniLM-L6-v2) | `app/core/ai/rag_engine.py:288` | `await rag.search(query, top_k=3)` |
| SmartAIService wrapper | `app/services/smart_ai_service.py:203` | `await smart_ai.ask(question, use_context=True)` |
| SoforService | `app/core/services/sofor_service.py` | `get_score_breakdown(id)` (T3.3), `get_route_profile(id)` (T3.4) |
| AnomalyDetector | `app/core/services/anomaly_detector.py:290` | `get_recent_anomalies(days, severity, status="open")` (T7) |
| Sofor.telegram_id | `app/database/models.py:233` | `Optional[str]` |
| Internal endpoints | `app/api/v1/endpoints/internal.py` | `X-Internal-Token` header zorunlu |
| Celery beat | `app/infrastructure/background/celery_app.py:34` | `beat_schedule={...}` dict'e ekleme |
| Frontend sidebar | `frontend/src/layouts/EliteLayout.tsx:131` | `navGroups[].items[]` — "Filo" grubunun altında |

### 0.2 Veri akış diyagramı (yüksek seviye)

```
Frontend /coaching → coaching-service.ts → GET /api/v1/coaching/{id}/insights
                                            ↓
                                    CoachingEndpoint (Redis cache var mı?)
                                            ↓ yoksa
                                    DriverCoachingEngine.generate_coaching(sofor_id)
                                            ↓
                          ┌─────────────┴─────────────┐
                          ↓             ↓             ↓
                  anomaly_detector  sofor_service.   sofor_service.
                  .get_recent_     get_score_       get_route_profile
                  anomalies(30d,    breakdown
                  status="open")
                          ↓
                  _categorize_anomalies (pure-py)
                          ↓
                  _build_prompt (Türkçe sistem prompt)
                          ↓
                  GroqService.chat(... temperature=0.4, max_tokens=1024)
                          ↓
                  _parse_response (JSON validation + fallback)
                          ↓
                  CoachingInsightsResponse (Pydantic)

User clicks "Gönder" → POST /coaching/{id}/send
                          ↓
                  Sofor.telegram_id varsa → Telegram Bot HTTP API direct
                  audit_log("coaching_sent", entity_id=sofor_id, new_value={msg})
                  CoachingDelivery INSERT (A.5'te)

Celery beat (Pazartesi 09:00) → coaching.weekly_digest
                          ↓
                  Aktif şoförler için sırayla generate_coaching
                  priority="high" olanları admin grup'una bildir
                  + her şoföre kendi insight'ını (telegram_id varsa)
```

### 0.3 Performans bütçesi

| İşlem | Hedef latency | Strateji |
|-------|---------------|----------|
| `GET /coaching/{id}/insights` (cache hit) | <50ms | Redis `coaching:insights:{id}` TTL 30dk |
| `GET /coaching/{id}/insights` (cache miss → LLM) | <8s | Groq llama-3.1-70b ortalama 3–5s, +veri toplama 0.5s |
| `POST /coaching/{id}/send` | <500ms | Telegram API + DB INSERT |
| Weekly digest (100 şoför) | <15dk | Sıralı çağrı (Groq rate limit) + retry |

### 0.4 Hata matrisi

| Hata | Frontend göstergesi | Backend davranışı |
|------|---------------------|-------------------|
| Groq API down/timeout | "Öneriler şu an üretilemiyor" + retry butonu | `_fallback_insights()` rule-based; 200 döner, `meta.source="fallback"` |
| Sofor bulunamadı | 404 modalında "Şoför kaydı yok" | `HTTPException(404, "Şoför bulunamadı")` |
| Sofor.telegram_id NULL (send) | Modal: "Bu şoför Telegram'a kayıtlı değil" | `HTTPException(409, "telegram_id missing")` |
| LLM JSON parse hatası | Aynı fallback | `logger.warning` + rule-based output |
| Cache backend down (Redis) | Cache miss davranışı, yavaş ama çalışır | `try/except` cache, fail silently |
| Telegram API 4xx (token bad/blocked) | Hata banner: detail mesajı | Audit log: `coaching_send_failed` |

### 0.5 Güvenlik kontrol listesi

- [ ] `/coaching/*` endpoint'leri admin yetki ister (`require_permissions("sofor:read")`).
- [ ] `/coaching/{id}/send` admin (`sofor:write`) ister.
- [ ] Telegram bot HTTP API çağrısı `settings.TELEGRAM_DRIVER_BOT_TOKEN.get_secret_value()` ile.
- [ ] Groq'a gönderilen PII: **plaka maskelenir** (e.g. `34 *** ***`), şoför ismi sadece ID olarak gider. (Plan'da risk olarak işaretliydi — burası uygulama.)
- [ ] Rate limit: `RateLimiterDependency("coaching_send", rate=10.0, period=60.0)` `POST /send` için.
- [ ] X-Internal-Token mevcut endpoint'lerle aynı pattern.

### 0.6 Rollback stratejisi

- A.1+A.2: feature flag `settings.COACHING_ENABLED = True`. False ise endpoint'ler 503 döner, UI gizlenir.
- A.5: Alembic `0013_coaching_delivery` migration `downgrade()` tablo siler.

---

## A.1 — Coaching Engine (3–4 saat)

### A.1.1 Dosyalar

- **Create:** `app/core/ai/driver_coaching_engine.py`
- **Create:** `app/schemas/coaching.py` (Pydantic models)
- **Create:** `app/tests/unit/test_driver_coaching_engine.py`

### A.1.2 Pre-conditions doğrulama (kod yazmadan önce çalıştır)

```bash
# Groq config var mı?
grep -n "GROQ_API_KEY\|GROQ_MODEL_NAME" app/config.py | head -3

# T3.3+T3.4+T7 metodları çalışıyor mu?
grep -n "def get_score_breakdown\|def get_route_profile" app/core/services/sofor_service.py
grep -n "status: Optional" app/core/services/anomaly_detector.py

# Sofor.telegram_id mevcut
grep -n "telegram_id" app/database/models.py
```

### A.1.3 Pydantic şemaları (`app/schemas/coaching.py`)

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

CoachingCategory = Literal["yakit_yonetimi", "guzergah_tercihi", "sofor_pratigi", "diger"]
CoachingPriority = Literal["low", "medium", "high"]


class CoachingInsightItem(BaseModel):
    category: CoachingCategory
    pattern: str = Field(..., max_length=240, description="Tespit edilen davranış kalıbı")
    evidence: List[str] = Field(default_factory=list, max_length=5)
    suggestion: str = Field(..., max_length=480)
    impact_score: float = Field(0.0, ge=0, le=1, description="Önerilen aksiyon etkisi 0-1")


class CoachingInsightsResponse(BaseModel):
    sofor_id: int
    ad_soyad: str
    headline: str = Field(..., max_length=200)
    priority: CoachingPriority
    insights: List[CoachingInsightItem]
    generated_at: str  # ISO datetime
    source: Literal["llm", "fallback"]
    model_config = ConfigDict(from_attributes=True)


class SendCoachingRequest(BaseModel):
    message: str = Field(..., min_length=10, max_length=1000)
    channel: Literal["telegram"] = "telegram"
    insight_category: Optional[CoachingCategory] = None  # A.5'te telemetri için


class SendCoachingResponse(BaseModel):
    sent: bool
    delivery_id: Optional[int] = None
    channel: str
    sent_at: str
```

### A.1.4 Engine implementation iskeleti

```python
# app/core/ai/driver_coaching_engine.py
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.ai.groq_service import get_groq_service
from app.core.services.anomaly_detector import get_anomaly_detector
from app.database.unit_of_work import UnitOfWork
from app.schemas.coaching import (
    CoachingCategory,
    CoachingInsightItem,
    CoachingInsightsResponse,
    CoachingPriority,
)

logger = logging.getLogger(__name__)

# Türkçe sistem prompt
SYSTEM_PROMPT = """Sen LojiNext filo yönetim sisteminin uzman koçluk asistanısın.
Görevin: TIR şoförleri için yakıt verimliliği, güzergah seçimi ve sürüş alışkanlıkları
hakkında somut, eyleme dönüştürülebilir öneriler üretmek.

KURALLAR:
1. Yanıtın yalnızca geçerli JSON olsun (markdown code fence YOK).
2. Şema: {"headline": str, "priority": "low"|"medium"|"high", "insights": [{"category": str, "pattern": str, "evidence": [str], "suggestion": str, "impact_score": 0..1}]}
3. headline ≤ 200 karakter, suggestion ≤ 480 karakter.
4. category SADECE şu değerlerden biri: yakit_yonetimi, guzergah_tercihi, sofor_pratigi, diger.
5. priority: anomali sapma % toplamı >40 ise "high", >20 ise "medium", aksi "low".
6. Sayısal kanıtları evidence'a sayı + birim ile koy ("28.5 L/100km", "+%18 sapma").
7. Şoförü plaka veya isimle ANMA — sadece davranıştan bahset.
8. Türkçe, profesyonel, suçlayıcı olmayan ton.
9. Eğer veri yetersizse (anomali=0 ve sefer<5): insights boş array, headline="Şu an için iyileştirme önerisi yok".
"""


class DriverCoachingEngine:
    """Şoför × anomali + skor + rota → kategorize koçluk önerileri."""

    def __init__(self):
        self.groq = get_groq_service()
        self.detector = get_anomaly_detector()

    async def generate_coaching(self, sofor_id: int) -> CoachingInsightsResponse:
        """Ana giriş noktası. LLM başarısız olsa bile valid response döner."""
        async with UnitOfWork() as uow:
            sofor = await uow.sofor_repo.get_by_id(sofor_id)
            if not sofor:
                raise ValueError("Şoför bulunamadı")

        from app.core.container import get_container
        svc = get_container().sofor_service
        score = await svc.get_score_breakdown(sofor_id)
        route_profile = await svc.get_route_profile(sofor_id)
        anomalies = await self.detector.get_recent_anomalies(
            days=30, status="open"
        )
        # sadece bu şoföre ait — kaynak_id eşleşmesi (kaynak_tip="sefer" via JOIN, ama
        # get_recent_anomalies'in dönüşünde sofor_adi var; sofor_id direkt yok.
        # Bu yüzden anomaly_detector'a sofor_id filtresi eklenebilir veya post-filter
        # yapılır — MVP için tüm anomaliler kullanılır + LLM'e sofor_id input verilir).
        # (Genişleyebilir: A.2'de sofor_id filter ekle.)

        categorized = self._categorize_anomalies(anomalies, sofor_id=sofor_id)

        if not categorized and score.get("trip_count", 0) < 5:
            # Veri yetersiz
            return self._empty_response(sofor_id, sofor.get("ad_soyad", ""))

        prompt = self._build_prompt(sofor, score, route_profile, categorized)

        try:
            raw = await self.groq.chat(
                user_message=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=1024,
            )
            parsed = self._parse_response(raw)
            return CoachingInsightsResponse(
                sofor_id=sofor_id,
                ad_soyad=sofor.get("ad_soyad", ""),
                generated_at=datetime.now(timezone.utc).isoformat(),
                source="llm",
                **parsed,
            )
        except Exception as exc:
            logger.warning(f"Coaching LLM failed for sofor {sofor_id}: {exc}")
            return self._fallback_response(
                sofor_id, sofor.get("ad_soyad", ""), categorized, score
            )

    # ─── Pure-py yardımcılar ───────────────────────────────────────────────
    def _categorize_anomalies(
        self, anomalies: List[Dict], sofor_id: int
    ) -> Dict[str, List[Dict]]:
        """Tipe + sapma yönüne göre 4 kategoriye ayır."""
        buckets: Dict[str, List[Dict]] = {
            "yakit_yonetimi": [],
            "guzergah_tercihi": [],
            "sofor_pratigi": [],
            "diger": [],
        }
        for a in anomalies:
            tip = a.get("tip", "")
            # Bu şoföre ait mi? sofor_adi join'den geliyor; direkt id yok.
            # MVP'de bu post-filter atlanır.
            if tip == "tuketim":
                # Sapma >30% ise sofor_pratigi, aksi yakit_yonetimi
                if abs(a.get("sapma_yuzde", 0)) > 30:
                    buckets["sofor_pratigi"].append(a)
                else:
                    buckets["yakit_yonetimi"].append(a)
            elif tip == "maliyet":
                buckets["yakit_yonetimi"].append(a)
            elif tip == "sefer":
                buckets["guzergah_tercihi"].append(a)
            else:
                buckets["diger"].append(a)
        return buckets

    def _build_prompt(
        self,
        sofor: Dict,
        score: Dict,
        route_profile: Dict,
        categorized: Dict[str, List[Dict]],
    ) -> str:
        """LLM'e gönderilecek user message (Türkçe, anonim, kısa)."""
        # Şoför adı LLM'e GİTMEZ (anonim). Sadece davranış verisi.
        lines = [
            f"Şoför ID: {sofor['id']}",
            f"Hibrit Skor: {score['total']} (Manuel={score['manual']}, Otomatik={score['auto']})",
            f"Son 365 gün tamamlanmış sefer sayısı: {score['trip_count']}",
            f"Ortalama tüketim: {score['avg_consumption']} L/100km",
            "",
            "Güzergah Profili (4 tip):",
        ]
        for p in route_profile.get("profiles", []):
            if p["trip_count"] > 0:
                lines.append(
                    f"- {p['label']}: {p['trip_count']} sefer, sapma %{p['deviation_pct']:+.1f}"
                )
        best = route_profile.get("best_route_type")
        if best:
            lines.append(f"En güçlü olduğu tip: {best}")
        lines.append("")
        lines.append("Son 30 günün anomalileri (kategorize):")
        for cat, items in categorized.items():
            if items:
                lines.append(f"- {cat}: {len(items)} adet, ort. sapma %{sum(abs(i['sapma_yuzde']) for i in items)/len(items):.1f}")
        return "\n".join(lines) + "\n\nGörev: Yukarıdaki verilere bakarak JSON formatında 1-4 insight üret."

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """LLM çıktısını JSON'a parse + validate."""
        # Markdown fence varsa temizle (LLM bazen ignore eder kuralı)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        # Şema doğrulama Pydantic'ten
        insights = [CoachingInsightItem(**i) for i in data.get("insights", [])]
        return {
            "headline": str(data.get("headline", ""))[:200],
            "priority": data.get("priority", "low"),
            "insights": insights,
        }

    def _empty_response(self, sofor_id: int, ad_soyad: str) -> CoachingInsightsResponse:
        return CoachingInsightsResponse(
            sofor_id=sofor_id,
            ad_soyad=ad_soyad,
            headline="Yeterli veri yok — koçluk önerisi üretilemedi",
            priority="low",
            insights=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="fallback",
        )

    def _fallback_response(
        self,
        sofor_id: int,
        ad_soyad: str,
        categorized: Dict[str, List[Dict]],
        score: Dict,
    ) -> CoachingInsightsResponse:
        """Rule-based fallback — LLM yokken kullanılır."""
        insights: List[CoachingInsightItem] = []
        total_dev = sum(
            sum(abs(a["sapma_yuzde"]) for a in items)
            for items in categorized.values()
        )
        for cat, items in categorized.items():
            if not items:
                continue
            avg_dev = sum(abs(a["sapma_yuzde"]) for a in items) / len(items)
            insights.append(
                CoachingInsightItem(
                    category=cat,
                    pattern=f"{len(items)} adet anomali, ortalama %{avg_dev:.0f} sapma",
                    evidence=[f"{len(items)} olay", f"ort %{avg_dev:.0f} sapma"],
                    suggestion={
                        "yakit_yonetimi": "Rölantide bekleme süresini azaltın; soğuk-start sayısını düşürün.",
                        "guzergah_tercihi": "Otoyol ağırlıklı rotaları tercih edin; şehir içi mesafeyi minimize edin.",
                        "sofor_pratigi": "Hız sınırlarına uyum + vites geçişlerinde ekonomik bant.",
                    }.get(cat, "Sefer kayıtlarını gözden geçirin."),
                    impact_score=min(1.0, avg_dev / 50),
                )
            )

        priority: CoachingPriority = (
            "high" if total_dev > 40 else "medium" if total_dev > 20 else "low"
        )
        return CoachingInsightsResponse(
            sofor_id=sofor_id,
            ad_soyad=ad_soyad,
            headline=(
                f"Skor {score.get('total', 0):.2f} — {len(insights)} alanda iyileştirme önerisi"
                if insights
                else "Şu an için kritik anomali yok"
            ),
            priority=priority,
            insights=insights,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="fallback",
        )
```

### A.1.5 Unit testler (`app/tests/unit/test_driver_coaching_engine.py`)

```python
@pytest.mark.unit
class TestDriverCoachingEngine:

    async def test_empty_when_no_data(self, mock_uow):
        # mock_uow.sofor_repo.get_by_id returns sofor
        # get_score_breakdown returns trip_count=0
        # get_recent_anomalies returns []
        result = await engine.generate_coaching(1)
        assert result.source == "fallback"
        assert len(result.insights) == 0
        assert "yeterli veri yok" in result.headline.lower()

    async def test_llm_success_parses_json(self, mock_groq):
        mock_groq.chat.return_value = '{"headline":"Test","priority":"medium","insights":[{"category":"yakit_yonetimi","pattern":"X","evidence":["a"],"suggestion":"Y","impact_score":0.5}]}'
        result = await engine.generate_coaching(7)
        assert result.source == "llm"
        assert len(result.insights) == 1
        assert result.insights[0].category == "yakit_yonetimi"

    async def test_llm_markdown_fence_stripped(self, mock_groq):
        mock_groq.chat.return_value = '```json\n{"headline":"H","priority":"low","insights":[]}\n```'
        result = await engine.generate_coaching(1)
        assert result.headline == "H"

    async def test_llm_exception_uses_fallback(self, mock_groq):
        mock_groq.chat.side_effect = TimeoutError("groq timeout")
        result = await engine.generate_coaching(7)
        assert result.source == "fallback"

    async def test_llm_invalid_json_uses_fallback(self, mock_groq):
        mock_groq.chat.return_value = "This is not JSON"
        result = await engine.generate_coaching(7)
        assert result.source == "fallback"

    async def test_categorization_high_deviation_goes_to_practice(self):
        anomalies = [{"tip": "tuketim", "sapma_yuzde": 35}]
        engine = DriverCoachingEngine()
        buckets = engine._categorize_anomalies(anomalies, sofor_id=1)
        assert len(buckets["sofor_pratigi"]) == 1
        assert len(buckets["yakit_yonetimi"]) == 0

    async def test_categorization_low_deviation_stays_yakit_yonetimi(self):
        anomalies = [{"tip": "tuketim", "sapma_yuzde": 12}]
        engine = DriverCoachingEngine()
        buckets = engine._categorize_anomalies(anomalies, sofor_id=1)
        assert len(buckets["yakit_yonetimi"]) == 1
```

### A.1.6 Acceptance Criteria

- [ ] `pytest app/tests/unit/test_driver_coaching_engine.py -v` 7/7 yeşil
- [ ] mypy temiz (yeni hata yok)
- [ ] Plaka/şoför ismi LLM prompt'unda **GİTMİYOR** (test edilebilir: prompt string'i içinde plaka regex yok)

### A.1.7 Verification

```bash
pytest app/tests/unit/test_driver_coaching_engine.py -v
mypy app/core/ai/driver_coaching_engine.py app/schemas/coaching.py --ignore-missing-imports
ruff check app/core/ai/driver_coaching_engine.py app/schemas/coaching.py --select E,F,W,I --ignore=E501
```

---

## A.2 — Backend Endpoints + Celery Task (2–3 saat)

### A.2.1 Dosyalar

- **Create:** `app/api/v1/endpoints/coaching.py`
- **Create:** `app/workers/tasks/coaching_tasks.py`
- **Modify:** `app/api/v1/api.py` (router include + tag)
- **Modify:** `app/infrastructure/background/celery_app.py` (beat_schedule)
- **Create:** `app/tests/integration/test_coaching_endpoints.py`

### A.2.2 Endpoint kodu (`app/api/v1/endpoints/coaching.py`)

```python
import json
import logging
from datetime import datetime, timezone
from typing import Annotated

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_user, require_permissions
from app.config import settings
from app.core.ai.driver_coaching_engine import DriverCoachingEngine
from app.database.models import Kullanici, Sofor
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from app.schemas.coaching import (
    CoachingInsightsResponse,
    SendCoachingRequest,
    SendCoachingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_engine = DriverCoachingEngine()

# Cache TTL: 30 dakika
CACHE_TTL_SECONDS = 30 * 60


@router.get("/{sofor_id}/insights", response_model=CoachingInsightsResponse)
async def get_coaching_insights(
    sofor_id: int,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """30 dk Redis cache'li koçluk önerileri."""
    if not settings.COACHING_ENABLED:
        raise HTTPException(status_code=503, detail="Koçluk modülü devre dışı")

    cache_key = f"coaching:insights:{sofor_id}"
    redis_client = aioredis.from_url(str(settings.REDIS_URL))

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return CoachingInsightsResponse(**json.loads(cached))
    except Exception as e:
        logger.warning(f"Coaching cache read failed: {e}")

    # Sofor var mı?
    sofor = await db.get(Sofor, sofor_id)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")

    try:
        result = await _engine.generate_coaching(sofor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Cache'e yaz
    try:
        await redis_client.setex(
            cache_key, CACHE_TTL_SECONDS, result.model_dump_json()
        )
    except Exception as e:
        logger.warning(f"Coaching cache write failed: {e}")

    return result


@router.post(
    "/{sofor_id}/send",
    response_model=SendCoachingResponse,
    dependencies=[
        Depends(RateLimiterDependency("coaching_send", rate=10.0, period=60.0))
    ],
)
async def send_coaching(
    sofor_id: int,
    payload: SendCoachingRequest,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sofor:write"))],
):
    """Telegram üzerinden manuel koçluk mesajı gönder."""
    sofor = await db.get(Sofor, sofor_id)
    if not sofor:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    if not sofor.telegram_id:
        raise HTTPException(
            status_code=409,
            detail="Bu şoför Telegram'a kayıtlı değil; mesaj gönderilemez",
        )

    bot_token = settings.TELEGRAM_DRIVER_BOT_TOKEN.get_secret_value()
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot config eksik")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": sofor.telegram_id,
                    "text": f"🧭 *Koçluk Önerisi*\n\n{payload.message}",
                    "parse_mode": "Markdown",
                },
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(f"Telegram send failed for sofor {sofor_id}: {exc}")
        raise HTTPException(
            status_code=502, detail=f"Telegram gönderimi başarısız: {exc}"
        ) from exc

    sent_at = datetime.now(timezone.utc)
    # A.5'te CoachingDelivery INSERT eklenir; şimdilik audit_log
    await log_audit_event(
        action="coaching_sent",
        module="coaching",
        entity_id=str(sofor_id),
        new_value={
            "message_excerpt": payload.message[:200],
            "channel": payload.channel,
            "category": payload.insight_category,
        },
    )

    return SendCoachingResponse(
        sent=True,
        delivery_id=None,  # A.5'te doldurulur
        channel=payload.channel,
        sent_at=sent_at.isoformat(),
    )
```

### A.2.3 Celery weekly digest (`app/workers/tasks/coaching_tasks.py`)

```python
import asyncio
import logging

from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="coaching.weekly_digest",
    max_retries=2,
    acks_late=True,
)
def weekly_coaching_digest(self):
    """Her aktif şoför için generate_coaching çağır; high-priority olanlara
    Telegram üzerinden otomatik mesaj at."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        from app.core.ai.driver_coaching_engine import DriverCoachingEngine
        from app.database.unit_of_work import UnitOfWork

        engine = DriverCoachingEngine()
        async with UnitOfWork() as uow:
            soforler = await uow.sofor_repo.get_all(
                sadece_aktif=True, limit=500
            )

        results = {"processed": 0, "high_priority": 0, "errors": 0, "sent": 0}
        for s in soforler:
            try:
                insights = await engine.generate_coaching(int(s["id"]))
                results["processed"] += 1
                if insights.priority == "high" and s.get("telegram_id"):
                    # Bu noktada send_coaching endpoint'ine yapılacak iç çağrı
                    # veya doğrudan Telegram API. MVP'de doğrudan.
                    # Detay A.4'te.
                    results["high_priority"] += 1
                    # (Telegram gönderimi A.4'teki helper'a delege)
            except Exception as exc:
                logger.error(f"Coaching digest failed for sofor {s['id']}: {exc}")
                results["errors"] += 1
        return results

    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
```

### A.2.4 Beat schedule güncelleme (`app/infrastructure/background/celery_app.py`)

```python
beat_schedule={
    # ... mevcut girdiler ...
    "coaching-weekly-digest-mondays": {
        "task": "coaching.weekly_digest",
        "schedule": crontab(day_of_week="mon", hour=9, minute=0),  # Pazartesi 09:00 UTC
    },
},
```

> **Not:** `crontab` import edilmemiş olabilir; üstte `from celery.schedules import crontab` ekle.

### A.2.5 Router include (`app/api/v1/api.py`)

```python
from app.api.v1.endpoints import coaching
api_router.include_router(coaching.router, prefix="/coaching", tags=["coaching"])
```

### A.2.6 Config (`app/config.py`)

```python
COACHING_ENABLED: bool = True  # Feature flag
TELEGRAM_DRIVER_BOT_TOKEN: SecretStr | None = None  # zaten varsa skip
```

### A.2.7 Integration testleri

```python
@pytest.mark.integration
@pytest.mark.asyncio
class TestCoachingEndpoints:

    async def _create_sofor(self, async_client, headers) -> int: ...

    async def test_get_insights_returns_200(self, async_client, admin_auth_headers):
        sid = await self._create_sofor(async_client, admin_auth_headers)
        resp = await async_client.get(f"/api/v1/coaching/{sid}/insights", headers=admin_auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["sofor_id"] == sid
        assert body["source"] in ("llm", "fallback")
        assert isinstance(body["insights"], list)

    async def test_get_insights_404_unknown(self, async_client, admin_auth_headers):
        resp = await async_client.get("/api/v1/coaching/99999/insights", headers=admin_auth_headers)
        assert resp.status_code == 404

    async def test_send_409_when_telegram_id_missing(self, async_client, admin_auth_headers):
        sid = await self._create_sofor(async_client, admin_auth_headers)
        # telegram_id default NULL
        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "Test mesajı yeterli uzunlukta."},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 409
        assert "Telegram" in resp.json()["detail"]

    async def test_send_mocked_telegram_success(self, async_client, admin_auth_headers, db_session, respx_mock):
        sid = await self._create_sofor(async_client, admin_auth_headers)
        # telegram_id set
        from sqlalchemy import update; from app.database.models import Sofor
        await db_session.execute(update(Sofor).where(Sofor.id == sid).values(telegram_id="12345"))
        await db_session.commit()

        respx_mock.post(re.compile(r"https://api\.telegram\.org/bot.*/sendMessage")).respond(200, json={"ok": True})

        resp = await async_client.post(
            f"/api/v1/coaching/{sid}/send",
            json={"message": "Bu hafta tüketiminiz hedefin %5 üstünde."},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["sent"] is True

    async def test_send_503_when_feature_flag_off(self, async_client, admin_auth_headers, monkeypatch):
        monkeypatch.setattr("app.config.settings.COACHING_ENABLED", False)
        resp = await async_client.get("/api/v1/coaching/1/insights", headers=admin_auth_headers)
        assert resp.status_code == 503

    async def test_send_rate_limited(self, async_client, admin_auth_headers):
        # 10/dk üst sınır — 11. istekte 429 beklenir.
        # Bu test EAGER modda atlanabilir.
        ...
```

### A.2.8 Acceptance Criteria

- [ ] `GET /coaching/{id}/insights` 200 + cached on second call (Redis hit < 50ms)
- [ ] `POST /coaching/{id}/send` 200 with mocked Telegram; 409 without telegram_id
- [ ] `celery_app.conf.beat_schedule["coaching-weekly-digest-mondays"]` mevcut
- [ ] 6/6 integration test passed

---

## A.3 — Frontend `/coaching` Sayfası (3–4 saat)

### A.3.1 Dosyalar

- **Create:** `frontend/src/pages/CoachingPage.tsx`
- **Create:** `frontend/src/components/coaching/CoachingDriverList.tsx`
- **Create:** `frontend/src/components/coaching/CoachingInsightsPanel.tsx`
- **Create:** `frontend/src/components/coaching/SendCoachingDialog.tsx`
- **Create:** `frontend/src/services/api/coaching-service.ts`
- **Create:** `frontend/src/resources/tr/coaching.ts`
- **Modify:** `frontend/src/App.tsx` (route `/coaching`)
- **Modify:** `frontend/src/layouts/EliteLayout.tsx` (Analitik grubuna ekle)
- **Create:** 3 test dosyası

### A.3.2 coaching-service.ts

```typescript
import axiosInstance from './axios-instance'

export type CoachingCategory = 'yakit_yonetimi' | 'guzergah_tercihi' | 'sofor_pratigi' | 'diger'
export type CoachingPriority = 'low' | 'medium' | 'high'

export interface CoachingInsight {
    category: CoachingCategory
    pattern: string
    evidence: string[]
    suggestion: string
    impact_score: number
}

export interface CoachingInsightsResponse {
    sofor_id: number
    ad_soyad: string
    headline: string
    priority: CoachingPriority
    insights: CoachingInsight[]
    generated_at: string
    source: 'llm' | 'fallback'
}

export const coachingService = {
    getInsights: async (soforId: number): Promise<CoachingInsightsResponse> => {
        const r = await axiosInstance.get<CoachingInsightsResponse>(`/coaching/${soforId}/insights`)
        return r.data
    },

    send: async (soforId: number, message: string, category?: CoachingCategory): Promise<{ sent: boolean; sent_at: string }> => {
        const r = await axiosInstance.post(`/coaching/${soforId}/send`, {
            message,
            channel: 'telegram',
            insight_category: category,
        })
        return r.data
    },
}
```

### A.3.3 Sayfa düzeni

```
┌─────────────────────────────────────────────────────────┐
│ Koçluk Modülü                                            │
│ Şoför × yakıt verimliliği × öneriler                    │
├─────────────────────────────────────────────────────────┤
│ ┌─ Sol panel (320px) ─┐  ┌─ Sağ panel (kalan) ─────────┐│
│ │ Şoför listesi       │  │ Seçili şoför için           ││
│ │ - Ali Veli  (1.13)  │  │ CoachingInsightsPanel        ││
│ │ - Ahmet Ç.  (0.82) │  │  - headline                  ││
│ │ - Mehmet O. (1.45) │  │  - priority badge            ││
│ │ ...                 │  │  - 0..4 insight kartı        ││
│ │                     │  │     each: category badge,    ││
│ │                     │  │     pattern, evidence chips, ││
│ │                     │  │     suggestion, [Gönder]     ││
│ └─────────────────────┘  └──────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### A.3.4 EliteLayout güncellemesi

```typescript
// EliteLayout.tsx navGroups[Analitik].items'a ekle:
{ icon: GraduationCap, label: 'Koçluk', path: '/coaching' },
```

(`GraduationCap` lucide-react'tan import edilmiş olmalı.)

### A.3.5 Resource strings (`frontend/src/resources/tr/coaching.ts`)

```typescript
export const coachingPageText = {
    heading: 'Koçluk Modülü',
    description: 'AI destekli şoför davranış analizi ve öneriler.',
    emptyDriverList: 'Aktif şoför bulunamadı.',
    selectDriverHint: 'Detay görmek için bir şoför seçin.',
} as const

export const coachingCategoryLabels = {
    yakit_yonetimi: 'Yakıt Yönetimi',
    guzergah_tercihi: 'Güzergah Tercihi',
    sofor_pratigi: 'Sürüş Pratiği',
    diger: 'Diğer',
} as const

export const coachingPriorityLabels = {
    low: 'Düşük',
    medium: 'Orta',
    high: 'Yüksek',
} as const

export const coachingSourceLabels = {
    llm: 'AI tarafından üretildi',
    fallback: 'Kural tabanlı (LLM yedeği)',
} as const

export const sendCoachingDialogText = {
    title: 'Telegram ile Koçluk Gönder',
    messageLabel: 'Mesaj',
    messagePlaceholder: 'Önerinizi düzenleyin...',
    sendButton: 'Telegram\'a Gönder',
    cancel: 'İptal',
    successToast: 'Mesaj iletildi.',
    errorToast: 'Mesaj gönderilemedi.',
    noTelegramHint: 'Bu şoför Telegram\'a kayıtlı değil — gönderim devre dışı.',
} as const
```

### A.3.6 CoachingInsightsPanel prop tipleri

```typescript
interface CoachingInsightsPanelProps {
    soforId: number | null
    onSendClick?: (insight: CoachingInsight) => void
}
```

İç davranış:
- `soforId == null` → "Detay görmek için bir şoför seçin."
- `useQuery(['coaching', soforId], () => coachingService.getInsights(soforId!), { enabled: soforId != null, staleTime: 30*60*1000 })`
- `isLoading` → spinner
- `isError` → kırmızı banner
- `data.insights.length === 0` → "Yeterli veri yok" + headline
- Her insight için: kategori badge (renk: yakit_yonetimi=info, guzergah=accent, sofor_pratigi=warning), priority bandı, evidence chip listesi, "Gönder" butonu (SendCoachingDialog'u açar)

### A.3.7 Test senaryoları (3 dosya, 8 senaryo)

```typescript
// CoachingDriverList.test.tsx
- liste render edilir
- aktif şoför yoksa empty state
- şoför tıklanınca onSelect çağrılır

// CoachingInsightsPanel.test.tsx
- soforId=null → "seçin" hint
- query loading → spinner
- query success boş insights → "yeterli veri yok"
- query success 2 insight → 2 kart render
- query error → kırmızı banner

// SendCoachingDialog.test.tsx
- mesaj boş ise Gönder disabled
- başarılı gönderim → onClose çağrılır
- 409 error → "Telegram'a kayıtlı değil" mesajı
```

### A.3.8 Acceptance Criteria

- [ ] `/coaching` rotasına navigasyon EliteLayout sidebar üzerinden çalışır
- [ ] Şoför seç → insights yüklenir → Gönder dialog'u açılır
- [ ] vitest 8/8 yeşil
- [ ] tsc + vite build temiz

---

## A.4 — Telegram Bot Komutları (2–3 saat)

### A.4.1 Dosyalar

- **Modify:** `telegram_bot/driver_bot.py` (yeni komutlar)
- **Modify:** `app/api/v1/endpoints/internal.py` (yeni endpoint)
- **Modify:** `app/core/services/internal_service.py` (yardımcı method)
- **Modify:** `app/workers/tasks/coaching_tasks.py` (high-priority Telegram broadcast)
- **Create:** `app/tests/integration/test_internal_coaching.py`

### A.4.2 Internal endpoint (`/internal/sofor-coaching/{telegram_id}`)

```python
# internal.py'ye ekle
@router.get("/sofor-coaching/{telegram_id}")
async def sofor_coaching_snapshot(
    telegram_id: str,
    svc: InternalService = Depends(get_internal_service),
):
    """Bot için: skor + son hafta özeti + top suggestion (özetlenmiş)."""
    snapshot = await svc.get_coaching_snapshot(telegram_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Şoför bulunamadı")
    return snapshot
```

### A.4.3 InternalService extension

```python
async def get_coaching_snapshot(self, telegram_id: str) -> dict | None:
    sofor = await self.get_sofor_by_telegram_id(telegram_id)
    if not sofor:
        return None
    from app.core.ai.driver_coaching_engine import DriverCoachingEngine
    from app.core.container import get_container
    svc = get_container().sofor_service
    score = await svc.get_score_breakdown(sofor["id"])
    insights = await DriverCoachingEngine().generate_coaching(sofor["id"])
    top = insights.insights[0] if insights.insights else None
    return {
        "ad_soyad": sofor["ad_soyad"],
        "skor": score["total"],
        "headline": insights.headline,
        "top_suggestion": top.suggestion if top else None,
        "priority": insights.priority,
    }
```

### A.4.4 Bot komutları (`telegram_bot/driver_bot.py`)

```python
async def _cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BACKEND_URL}/api/v1/internal/sofor-coaching/{telegram_id}",
            headers={"X-Internal-Token": INTERNAL_TOKEN},
            timeout=15,
        )
    if r.status_code != 200:
        await update.message.reply_text("Skorun bulunamadı. Yönetici ile iletişime geç.")
        return
    data = r.json()
    txt = (
        f"📊 *Skor*: {data['skor']}\n"
        f"📰 *Bu hafta*: {data['headline']}\n"
    )
    if data.get("top_suggestion"):
        txt += f"\n💡 *Öneri*: {data['top_suggestion']}"
    await update.message.reply_text(txt, parse_mode="Markdown")


# Application'da kaydet:
app.add_handler(CommandHandler("score", _cmd_score))
app.add_handler(CommandHandler("oneriler", _cmd_oneriler))  # Benzer ama tüm insight listesi
```

### A.4.5 Türkçe mesaj template örneği

```
📊 Skor: 1.13
📰 Bu hafta: Skor 1.13 — 2 alanda iyileştirme önerisi

💡 Öneri: Rölantide bekleme süresini azaltın; soğuk-start sayısını düşürün.

ℹ️ Detay için /oneriler yazın.
```

### A.4.6 Weekly digest broadcasting

A.2.3'teki `weekly_coaching_digest` görevinde high-priority'lerin Telegram'a iletilmesi:

```python
# coaching_tasks.py içinde, high_priority dalında
import httpx
async with httpx.AsyncClient() as client:
    await client.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_DRIVER_BOT_TOKEN.get_secret_value()}/sendMessage",
        json={
            "chat_id": s["telegram_id"],
            "text": f"📢 Haftalık Koçluk\n\n{insights.headline}\n\n💡 {insights.insights[0].suggestion if insights.insights else ''}",
            "parse_mode": "Markdown",
        },
        timeout=10,
    )
results["sent"] += 1
```

### A.4.7 Test (`test_internal_coaching.py`)

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_coaching_snapshot_404_unknown(async_client):
    r = await async_client.get(
        "/api/v1/internal/sofor-coaching/000000",
        headers={"X-Internal-Token": settings.INTERNAL_API_SECRET},
    )
    assert r.status_code == 404


async def test_coaching_snapshot_unauthorized(async_client):
    r = await async_client.get("/api/v1/internal/sofor-coaching/123")
    assert r.status_code == 401


# happy path: gerçek sofor seed + telegram_id, snapshot döner.
```

### A.4.8 Acceptance Criteria

- [ ] Bot `/score` ile özetli yanıt alır
- [ ] Bot `/oneriler` ile insight listesini görür
- [ ] Haftalık digest task EAGER modda çalıştırıldığında high-priority'lere mesaj atar (mock client ile doğrulanır)
- [ ] Internal endpoint 401/404 doğru döner

---

## A.5 — A/B Test / Etki Ölçümü (2 saat)

### A.5.1 Dosyalar

- **Modify:** `app/database/models.py` (yeni model `CoachingDelivery`)
- **Create:** `alembic/versions/0013_coaching_delivery.py`
- **Modify:** `app/api/v1/endpoints/coaching.py` (`POST send` → CoachingDelivery INSERT, yeni endpoint `GET /effectiveness`)
- **Create:** `app/workers/tasks/coaching_tasks.py` ek task: `coaching.evaluate_pending` (günlük)
- **Modify:** `app/infrastructure/background/celery_app.py` (beat: günlük 02:00)
- **Modify:** `frontend/src/pages/CoachingPage.tsx` (etkinlik kartı)
- **Create:** `app/tests/integration/test_coaching_effectiveness.py`

### A.5.2 Model

```python
class CoachingDelivery(Base):
    __tablename__ = "coaching_deliveries"
    __table_args__ = (
        Index("ix_coaching_deliveries_sofor_id_sent_at", "sofor_id", "sent_at"),
        Index("ix_coaching_deliveries_evaluated_at", "evaluated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sofor_id: Mapped[int] = mapped_column(Integer, ForeignKey("soforler.id"), index=True)
    score_before: Mapped[float] = mapped_column(Float)
    score_after_2w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_delta_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="telegram")
    insight_category: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    message_excerpt: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sent_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

### A.5.3 Alembic migration (`0013_coaching_delivery.py`)

```python
"""coaching_delivery

Revision ID: 0013_coaching_delivery
Revises: 0012_anomaly_action
Create Date: 2026-05-22 21:00:00.000000
"""
revision = "0013_coaching_delivery"
down_revision = "0012_anomaly_action"

def upgrade():
    op.create_table(
        "coaching_deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sofor_id", sa.Integer, sa.ForeignKey("soforler.id"), nullable=False, index=True),
        sa.Column("score_before", sa.Float, nullable=False),
        sa.Column("score_after_2w", sa.Float, nullable=True),
        sa.Column("score_delta_pct", sa.Float, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="telegram"),
        sa.Column("insight_category", sa.String(40), nullable=True),
        sa.Column("message_excerpt", sa.String(500), nullable=True),
        sa.Column("sent_by_user_id", sa.Integer, nullable=True),
    )
    op.create_index("ix_coaching_deliveries_sofor_id_sent_at", "coaching_deliveries", ["sofor_id", "sent_at"])
    op.create_index("ix_coaching_deliveries_evaluated_at", "coaching_deliveries", ["evaluated_at"])

def downgrade():
    op.drop_index("ix_coaching_deliveries_evaluated_at", table_name="coaching_deliveries")
    op.drop_index("ix_coaching_deliveries_sofor_id_sent_at", table_name="coaching_deliveries")
    op.drop_table("coaching_deliveries")
```

### A.5.4 Send endpoint güncelleme (CoachingDelivery INSERT)

```python
# coaching.py POST send içinde:
from app.database.models import CoachingDelivery

# Telegram başarılıysa:
async with UnitOfWork(session=db) as uow:
    svc = get_container().sofor_service
    score = await svc.get_score_breakdown(sofor_id)
    delivery = CoachingDelivery(
        sofor_id=sofor_id,
        score_before=score["total"],
        message_excerpt=payload.message[:500],
        channel=payload.channel,
        insight_category=payload.insight_category,
        sent_by_user_id=current_admin.id,
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)

return SendCoachingResponse(sent=True, delivery_id=delivery.id, channel=payload.channel, sent_at=...)
```

### A.5.5 Evaluation Celery task

```python
@celery_app.task(bind=True, name="coaching.evaluate_pending", max_retries=2)
def evaluate_pending_deliveries(self):
    """Her gün: gönderim tarihi >=14g önce, evaluated_at NULL olanları işle."""
    async def _run():
        from sqlalchemy import select, update
        from datetime import datetime, timedelta, timezone
        from app.database.models import CoachingDelivery
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        async with UnitOfWork() as uow:
            stmt = select(CoachingDelivery).where(
                CoachingDelivery.sent_at < cutoff,
                CoachingDelivery.evaluated_at.is_(None),
            )
            rows = (await uow.session.execute(stmt)).scalars().all()
            results = {"evaluated": 0}

            from app.core.container import get_container
            svc = get_container().sofor_service
            for d in rows:
                score = await svc.get_score_breakdown(d.sofor_id)
                delta = (
                    (score["total"] - d.score_before) / d.score_before * 100
                    if d.score_before > 0 else 0
                )
                await uow.session.execute(
                    update(CoachingDelivery)
                    .where(CoachingDelivery.id == d.id)
                    .values(
                        score_after_2w=score["total"],
                        score_delta_pct=round(delta, 2),
                        evaluated_at=datetime.now(timezone.utc),
                    )
                )
                results["evaluated"] += 1
            await uow.commit()
            return results
    ...
```

### A.5.6 `/effectiveness` endpoint

```python
@router.get("/effectiveness", response_model=Dict[str, Any])
async def get_effectiveness(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(require_permissions("sofor:read"))],
    days: int = Query(30, ge=7, le=180),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = text("""
        SELECT
            COUNT(*) AS total_sent,
            COUNT(*) FILTER (WHERE evaluated_at IS NOT NULL) AS total_evaluated,
            AVG(score_delta_pct) FILTER (WHERE evaluated_at IS NOT NULL) AS avg_delta,
            COUNT(*) FILTER (WHERE score_delta_pct > 0) AS improved,
            COUNT(*) FILTER (WHERE score_delta_pct < 0) AS worsened
        FROM coaching_deliveries
        WHERE sent_at >= :cutoff
    """)
    row = (await db.execute(stmt, {"cutoff": cutoff})).mappings().one()
    total_ev = row["total_evaluated"] or 0
    return {
        "window_days": days,
        "total_sent": row["total_sent"],
        "total_evaluated": total_ev,
        "improved": row["improved"] or 0,
        "worsened": row["worsened"] or 0,
        "improve_rate": (row["improved"] / total_ev) if total_ev else None,
        "avg_score_delta_pct": float(row["avg_delta"]) if row["avg_delta"] is not None else None,
        # Statistical caveat (frontend display)
        "caveat": (
            "Bu metrik istatistiksel kanıt değil, yalnız gözlemdir. "
            "Skor değişiminde mevsimsellik, güzergah ve operasyonel faktörler de etkilidir."
        ),
    }
```

### A.5.7 Frontend etkinlik kartı

CoachingPage başlık altına:

```typescript
const { data: effectiveness } = useQuery({
    queryKey: ['coaching-effectiveness'],
    queryFn: () => coachingService.getEffectiveness(),
    staleTime: 60 * 60 * 1000,
})

// Render: 3 mini-stat: gönderilen, ort. delta, iyileşme oranı
// Alt-yazıda effectiveness.caveat görünür.
```

### A.5.8 İstatistiksel notlar (önemli)

**Bias kaynakları (UI'da belirt):**
1. **Confounder:** Skor değişimi yalnızca koçluğa atfedilemez (güzergah profili, mevsim, yük değişimi etkili).
2. **Self-selection:** Yöneticinin hangi şoföre mesaj attığı rastgele değil — düşük skor olanlar daha çok mesaj alır, regresyon-ortalamaya nedeniyle iyileşme bias'ı.
3. **Çift sayım:** Aynı şoföre 14 gün içinde birden fazla mesaj atılırsa delta'lar üst üste binebilir.

**Çözüm (MVP'de UI uyarısı):** `caveat` alanı + "Bu rakamlar yalnızca gözlemdir, kontrollü A/B değildir." Detaylı analiz `effectiveness?segmentation=baseline_score` gibi parametrelerle ileride.

### A.5.9 Acceptance Criteria

- [ ] `alembic check` 0 drift; tek head `0013_coaching_delivery`
- [ ] `POST /send` sonrası `CoachingDelivery` satırı oluşur (test'le doğrula)
- [ ] Manuel olarak 15 gün geriye `sent_at` UPDATE edilerek `evaluate_pending` task'i çağrılır → `score_after_2w` ve `score_delta_pct` dolar
- [ ] `GET /effectiveness?days=30` valid JSON, `caveat` alanı dolu
- [ ] Frontend CoachingPage'de etkinlik kartı görünür

---

## Bağımlılık & Çalıştırma Sırası

```
A.1 ─→ A.2 ─→ A.3
       │
       ↘ A.4 (A.1+A.2'ye bağımlı, A.3 ile paralel)
       │
       ↘ A.5 (A.2+A.3 tamamlanınca)
```

**Önerilen 5 commit:**

1. `feat(coaching): A.1 — engine + Pydantic schemas + 7 unit test`
2. `feat(coaching): A.2 — endpoints + Celery weekly_digest + Redis cache`
3. `feat(coaching): A.3 — /coaching page + 3 component + sidebar link`
4. `feat(coaching): A.4 — Telegram /score, /oneriler + internal endpoint + auto-broadcast`
5. `feat(coaching): A.5 — CoachingDelivery + migration + evaluate task + /effectiveness`

## Genel Kabul Kriterleri (tüm A için)

- [ ] `pytest -m "unit or integration"` geçer (A.1-A.5 yeni testler dahil)
- [ ] `pytest app/tests/unit/test_driver_coaching_engine.py` ≥7 senaryo passed
- [ ] `pytest app/tests/integration/test_coaching_endpoints.py` ≥6 senaryo passed
- [ ] `npx vitest --run src/components/coaching src/pages/__tests__` ≥8 senaryo passed
- [ ] `npx tsc --noEmit` 0 hata
- [ ] `npx vite build` başarılı
- [ ] `ruff check app/core/ai/driver_coaching_engine.py app/api/v1/endpoints/coaching.py app/workers/tasks/coaching_tasks.py app/schemas/coaching.py --ignore=E501` 0 hata
- [ ] `mypy app/core/ai/driver_coaching_engine.py app/api/v1/endpoints/coaching.py app/schemas/coaching.py --ignore-missing-imports` yeni hata yok
- [ ] `alembic` single head (`0013_coaching_delivery`)
- [ ] CLAUDE.md → "Coaching modülü" bölümü eklendi
- [ ] PII: LLM prompt'unda plaka/şoför ismi YOK (regex kontrollü test)
- [ ] Feature flag `COACHING_ENABLED=False` iken endpoint'ler 503 döner

## Tahmini Toplam Süre

| Adım | Tahmin | Risk |
|------|--------|------|
| A.1 | 3–4 saat | LLM prompt iterasyonu uzayabilir |
| A.2 | 2–3 saat | Redis async client kurulum riski |
| A.3 | 3–4 saat | Sidebar permission check varsa+1h |
| A.4 | 2–3 saat | Telegram bot env hazır değilse +1h |
| A.5 | 2 saat | Test için zaman manipülasyonu gerekir |
| **Toplam** | **12–16 saat** | |

## Karara Bağlanmış Sorular (2026-05-22)

### Q1 — Groq PII politikası → **Anonim-tam**

LLM'e gönderilen prompt'ta **plaka, ad-soyad, telegram_id, sofor_id YOK**. Sadece anonim ölçümler (skor, sapma %, sefer sayısı, güzergah tipi). Gerekçe: Groq Terms data retention belirsiz, KVKK/GDPR şoför ad-soyad PII; öneri kalıp odaklı olduğu için kişiselleştirme gerekmez.

**A.1 uygulama farkı:** `_build_prompt`'ta `Şoför ID: {sofor['id']}` satırı **kaldırılır**. Yerine sadece sayısal başlık (`"Filo Şoför Profili:"`). User message regex testi:

```python
def test_prompt_contains_no_pii(self):
    engine = DriverCoachingEngine()
    sofor = {"id": 7, "ad_soyad": "Ali Veli"}
    prompt = engine._build_prompt(sofor, score_mock, route_mock, cats_mock)
    assert "Ali" not in prompt
    assert "Veli" not in prompt
    assert "telegram" not in prompt.lower()
    # plaka formatı ([A-Z]{2,3}\s\d{2,4}) ile eşleşme yok
    import re
    assert not re.search(r'\d{2}\s+[A-Z]{2,3}\s+\d{2,4}', prompt)
```

### Q2 — Telegram mesaj format → **HTML + html.escape()**

`parse_mode="HTML"`. Gönderim öncesi `html.escape(text)` zorunlu.

**A.2 ve A.4 kod örneği güncelleme:**

```python
import html

safe_message = html.escape(payload.message)
text = (
    f"🧭 <b>Koçluk Önerisi</b>\n\n{safe_message}"
)
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": sofor.telegram_id, "text": text, "parse_mode": "HTML"},
    )
```

**A.4 `/score` komut yanıtı HTML formatında:**

```python
import html

skor = html.escape(str(data['skor']))
headline = html.escape(data['headline'])
top = html.escape(data.get('top_suggestion') or '')

txt = (
    f"📊 <b>Skor</b>: {skor}\n"
    f"📰 <b>Bu hafta</b>: {headline}\n"
)
if top:
    txt += f"\n💡 <b>Öneri</b>: {top}"
await update.message.reply_text(txt, parse_mode="HTML")
```

### Q3 — Feature flag scope → **Global `settings.COACHING_ENABLED`**

CLAUDE.md tek-tenant; per-tenant flag bu epic dışında.

**A.2 uygulama:** `app/config.py`'a `COACHING_ENABLED: bool = True` ekle. Endpoint başında:

```python
if not settings.COACHING_ENABLED:
    raise HTTPException(status_code=503, detail="Koçluk modülü devre dışı")
```

Multi-tenant epic'i sonrası `tenant_settings.coaching_enabled` ile katmanlama yapılır — şu an scope dışı.

### Q4 — Effectiveness konumu → **MVP'de `/coaching` üst başlığa kompakt kart**

Ayrı `/coaching/effectiveness` route MVP'de **YOK**. Backend endpoint (`GET /coaching/effectiveness`) zaten ayrı; UI ileride detay sayfasına genişletilebilir.

**A.3+A.5 uygulama:** CoachingPage başlık altına 1 satırlık üçlü mini-stat:

```typescript
// CoachingPage.tsx başlığın altında
<EffectivenessMiniCard />

// EffectivenessMiniCard.tsx
const { data } = useQuery({
    queryKey: ['coaching', 'effectiveness', 30],
    queryFn: () => coachingService.getEffectiveness(30),
    staleTime: 60 * 60 * 1000,
})

// Layout: 3 stat yan yana — Gönderilen / İyileşme % / Ort. Delta —
// + footnote: data.caveat (italic, küçük punto)
```

Roadmap notu: ileride `/coaching/effectiveness` route'una `EffectivenessDetail.tsx` sayfası eklenecek. Segmentation (baseline_score < 1.0 → yüksek delta beklenir, vs.), time-series chart, kategori bazlı breakdown. Bu MVP scope dışı.

---

## Karar Sonrası Etki (özet)

| Karar | Hangi alt-görev | Ek iş |
|-------|----------------|-------|
| Anonim-tam PII | A.1 (+test) | ~10dk |
| HTML format | A.2 + A.4 | ~20dk |
| Global flag | A.2 | ~5dk |
| Kompakt etkinlik kartı | A.3 + A.5 | ~30dk |
| **Toplam ek süre** | | **~1 saat** |

Yeni toplam: **13–17 saat** (eskisi 12–16h).

Tüm 4 karar derlendi — A.1'den koda başlamaya hazır.
