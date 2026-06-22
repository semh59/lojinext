# Feature A — Şoför Koçluk Modülü (Mini-Plan)

> **Bağlam:** `docs/superpowers/plans/2026-05-21-frontend-derinlik-ve-yeni-ozellikler.md` Faz 2'deki en yüksek değerli özellik (12–15 saat tahmini). Bu mini-plan o üst-plan'ı uygulanabilir alt-görevlere böler.

**İş Problemi:** Şoförler anomali yapıyor, skorları düşüyor; ama "neyi yanlış yaptım, nasıl düzelteyim?" sorusuna yapısal bir cevap alamıyorlar. Filo yöneticisi bunu manuel iletmek zorunda.

**Çözüm Tezi:** Mevcut anomali geçmişini + route-profile + skor-breakdown verilerini RAG/LLM ile yorumlayan koçluk önerileri üret. Manuel onaylı Telegram bildirimi ile şoföre ulaştır. Sonuçları (2 hafta sonra skor delta) ölçerek geri besleme.

**Pre-existing altyapı (kullanılacak):**
- `app/core/ai/rag_engine.py` (FAISS + sentence-transformers/all-MiniLM-L6-v2, 384-dim)
- `app/core/ai/groq_service.py` (`llama-3.1-70b-versatile`, chat + chat_stream)
- `app/services/smart_ai_service.py` (RAG + LLM orchestration)
- `app/core/services/sofor_service.get_score_breakdown()` (T3.3'te eklendi)
- `app/core/services/sofor_service.get_route_profile()` (T3.4'te eklendi)
- `app/core/services/anomaly_detector.get_recent_anomalies(sofor_id, status, days)` (T7'de status alanı eklendi)
- `app/infrastructure/background/celery_app.py` (beat_schedule pattern hazır)
- `telegram_bot/driver_bot.py` (TELEGRAM_DRIVER_BOT_TOKEN env var + `_get_sofor(telegram_id)` helper var)
- `app/api/v1/endpoints/internal.py` (driver_bot ile backend arası köprü endpoint'leri)

**Toplam tahmini süre:** 12–15 saat → 5 alt-görev

---

## A.1 — Coaching Engine (Core Logic) [3–4 saat]

**Files:**
- Create: `app/core/ai/driver_coaching_engine.py`
- Create: `app/tests/unit/test_driver_coaching_engine.py`

**Pre-conditions:**
- `app.services.smart_ai_service.SmartAIService.ask(question, context)` çalışıyor (verify).
- `app.core.ai.groq_service.GroqService.chat(messages, temperature, system_prompt)` çalışıyor.
- `settings.GROQ_API_KEY` config'de mevcut.

**Implementation:**
- [ ] Adım 1: `DriverCoachingEngine` sınıfı — input: `sofor_id`. Şu verileri toplar:
  - Son 30 günün anomalileri (`get_recent_anomalies(days=30, status="open")`)
  - Skor kırılımı (`get_score_breakdown(sofor_id)`)
  - Güzergah profili (`get_route_profile(sofor_id)`)
- [ ] Adım 2: `_categorize_anomalies(anomalies)`: anomalileri tipe + sapma yüzdesine göre 3 kategoriye ayır (`yakıt_yönetimi`, `güzergah_tercihi`, `şoför_pratiği`). Pure-Python; LLM yok.
- [ ] Adım 3: `_build_prompt(sofor_metadata, categorized_anomalies, route_profile)`: Türkçe sistem prompt'u. Maks 1500 token context. `temperature=0.4`. Output JSON schema (LLM'ye instruct):
  ```json
  {
    "insights": [
      {"category": "yakıt_yönetimi", "pattern": "...", "evidence": ["...", "..."], "suggestion": "..."}
    ],
    "headline": "Bu hafta...",
    "priority": "low|medium|high"
  }
  ```
- [ ] Adım 4: `generate_coaching(sofor_id)` → `Groq.chat` → parse + validate JSON → fallback (LLM hatası varsa rule-based özet).
- [ ] Adım 5: 3 unit test:
  - Veri yokken `{"insights": [], "headline": "yeterli veri yok", "priority": "low"}` döner
  - Mock Groq response → parse + validate
  - Groq exception → fallback metni döner

**Acceptance Criteria:**
- `DriverCoachingEngine(uow).generate_coaching(sofor_id=N)` async coroutine, valid JSON döner.
- LLM çağrısı başarısız olsa bile fonksiyon exception fırlatmaz.

**Verification:**
```bash
pytest app/tests/unit/test_driver_coaching_engine.py -v
mypy app/core/ai/driver_coaching_engine.py --ignore-missing-imports
```

---

## A.2 — Backend Endpoints + Celery Task [2–3 saat]

**Files:**
- Create: `app/api/v1/endpoints/coaching.py`
- Modify: `app/api/v1/api.py` (router include)
- Modify: `app/schemas/sofor.py` (CoachingInsight + CoachingResponse schemas)
- Create: `app/workers/tasks/coaching_tasks.py`
- Modify: `app/infrastructure/background/celery_app.py` (beat schedule)
- Create: `app/tests/integration/test_coaching_endpoints.py`

**Pre-conditions:**
- A.1 tamamlanmış olmalı.
- Beat schedule'a yeni job ekleme paterni: mevcut `"drain-prediction-dlq-every-60s"` örneği (line 35–38).

**Implementation:**
- [ ] Adım 1: `GET /api/v1/coaching/{sofor_id}/insights` — `DriverCoachingEngine.generate_coaching()` çağırır, 30 dk cache (`functools.lru_cache` veya Redis). Response model `CoachingResponse`.
- [ ] Adım 2: `POST /api/v1/coaching/{sofor_id}/send` — body `{message: str, channel: "telegram"}`. Şoförün `telegram_id`'sini DB'den çek, `httpx` ile telegram bot HTTP'sine (veya doğrudan `telegram.Bot.send_message`) ilet. `CoachingDelivery` audit kaydı (yeni tablo değil, mevcut `audit_logs` üzerine `action="coaching_sent"`).
- [ ] Adım 3: Celery task `coaching.weekly_digest`: tüm aktif şoförler için `generate_coaching` çalıştır, `priority="high"` olanları admin Telegram grup'una bildir. Beat schedule `"weekly-coaching-digest"`: `schedule=604800.0` (haftalık) veya cron Pazartesi 09:00.
- [ ] Adım 4: 3 integration test:
  - `GET /coaching/{id}/insights` 200 + valid response shape
  - `POST /coaching/{id}/send` 200 + Telegram mock çağrısı yapıldı
  - `GET` bilinmeyen sofor_id → 404

**Acceptance Criteria:**
- 2 endpoint çalışır, response_model'lere uyumlu.
- Celery beat schedule listesi `alembic check` benzeri smoke: `celery_app.conf.beat_schedule` içinde `"weekly-coaching-digest"` var.
- TEST_DATABASE_URL gerektirmeyen unit testler hızlı.

---

## A.3 — Frontend `/coaching` Sayfası [3–4 saat]

**Files:**
- Create: `frontend/src/pages/CoachingPage.tsx`
- Create: `frontend/src/components/coaching/CoachingDriverList.tsx`
- Create: `frontend/src/components/coaching/CoachingInsightsPanel.tsx`
- Create: `frontend/src/components/coaching/SendCoachingDialog.tsx`
- Create: `frontend/src/services/api/coaching-service.ts`
- Modify: `frontend/src/App.tsx` (route ekle: `/coaching`)
- Modify: `frontend/src/components/layout/Sidebar.tsx` (link ekle)
- Modify: `frontend/src/resources/tr/coaching.ts` (yeni dosya)

**Pre-conditions:**
- A.2 endpoint'leri çalışır.
- Mevcut sidebar pattern — `frontend/src/components/layout/Sidebar.tsx` içinde her menu item paterni var (verify).

**Implementation:**
- [ ] Adım 1: `coaching-service.ts`: `getInsights(soforId)`, `sendCoaching(soforId, message)`.
- [ ] Adım 2: `CoachingDriverList.tsx`: aktif şoförleri listele (driverService.getAll), her satırda son skor + skor trendi (`stats.trends` değil; her şoför için skor delta hesaplanmalı — backend `score_breakdown.total` + DB'deki önceki skor karşılaştırmasından). MVP için sadece mevcut skoru göster.
- [ ] Adım 3: `CoachingInsightsPanel.tsx`: seçili şoför için `coachingService.getInsights(soforId)`. Her insight için kart: kategori badge + pattern + evidence (rozet listesi) + suggestion. Priority renk-kodlu.
- [ ] Adım 4: `SendCoachingDialog.tsx`: insight'ın `suggestion` metnini düzenlenebilir textarea'ya koy. "Telegram'dan Gönder" butonu → mutation → onSuccess "gönderildi" notif.
- [ ] Adım 5: Test: 3 vitest (driver listesi render, insights panel boş/dolu state, send dialog mutation).

**Acceptance Criteria:**
- `/coaching` rotasına giderek sayfayı görünür.
- Bir şoför seç → insights yüklenir → "Gönder" butonu çalışır.
- Sidebar'da yeni link görünür.

---

## A.4 — Telegram Bot Komutları [2–3 saat]

**Files:**
- Modify: `telegram_bot/driver_bot.py`
- Modify: `app/api/v1/endpoints/internal.py` (yeni endpoint: `/internal/sofor-coaching/{telegram_id}`)
- Create: `app/tests/integration/test_internal_coaching.py`

**Pre-conditions:**
- A.1 + A.2 hazır.
- `driver_bot.py` mevcut `_get_sofor(telegram_id)` helper'ı kullanır.

**Implementation:**
- [ ] Adım 1: `/score` komutu — telegram_id ile sofor'u bul, `coaching/{sofor_id}/insights` benzeri bir özet endpoint (`GET /internal/sofor-coaching/{telegram_id}` — auth: bot token; response: `{score, score_breakdown, headline, top_suggestion}`). Bot bunu Türkçe formatla cevaplar.
- [ ] Adım 2: `/oneriler` komutu — son koçluk insight'larının (priority=high|medium) listesi.
- [ ] Adım 3: Otomatik haftalık özet (Pazartesi 09:00) — A.2'deki Celery task `weekly_digest`'in her şoför için ürettiği özet, ilgili `telegram_id` varsa direkt mesajla gönderilir.
- [ ] Adım 4: 1 integration test: internal endpoint geçerli telegram_id ile valid response döner, geçersiz id ile 404.

**Acceptance Criteria:**
- Şoför `/score` yazınca skor + son hafta özetini Türkçe alır.
- Sistem haftalık otomatik olarak high-priority şoförlere mesaj gönderir.

---

## A.5 — A/B Test / Etki Ölçümü [2 saat]

**Files:**
- Modify: `app/database/models.py` (yeni tablo: `CoachingDelivery`)
- Migration: `alembic revision -m "coaching_delivery"`
- Modify: `app/api/v1/endpoints/coaching.py` (send sonrası kayıt)
- Create: `app/api/v1/endpoints/coaching.py:GET /coaching/effectiveness` (son 30 günde gönderilen mesajların 2 hafta sonra skor delta'sı)
- Modify: `frontend/src/pages/CoachingPage.tsx` (etkinlik istatistiği kartı)

**Pre-conditions:**
- A.1 + A.2 + A.3 tamamlanmış.

**Implementation:**
- [ ] Adım 1: `CoachingDelivery` tablosu:
  ```python
  class CoachingDelivery(Base):
      id, sofor_id, score_before, sent_at, channel, message_excerpt,
      score_after_2w, score_delta_pct, evaluated_at
  ```
- [ ] Adım 2: `POST /coaching/{id}/send` → `score_before = current` + DB INSERT (`score_after_2w=NULL`).
- [ ] Adım 3: Celery beat task `coaching.evaluate_pending`: günlük olarak gönderim tarihi >=14 gün önce + `evaluated_at IS NULL` kayıtları işle; mevcut skoru oku, delta hesapla, `evaluated_at = now()`.
- [ ] Adım 4: `GET /coaching/effectiveness` → toplam gönderim, ortalama delta, ikincil oran (skoru artanlar / toplam).
- [ ] Adım 5: Frontend CoachingPage'de "Bu ayın etkinliği" mini-kartı.

**Acceptance Criteria:**
- Bir mesaj gönderildikten 14 gün sonra delta otomatik hesaplanır (test'te Celery EAGER + zaman manipülasyonu ile doğrulanmalı).
- `/coaching/effectiveness` endpoint admin için meaningful sayılar döner.

---

## Genel Kabul Kriterleri

Her alt-görev tamamlandığında:
- [ ] `pytest -m "unit or not integration"` geçer
- [ ] Yeni testler dahil
- [ ] `npx tsc --noEmit` 0 hata
- [ ] `npx vitest --run` geçer
- [ ] `ruff check app --select E,F,W,I --ignore=E501` 0 hata
- [ ] `mypy app --ignore-missing-imports` yeni hata yok
- [ ] `alembic` single head (A.5'te yeni migration eklendiğinde)
- [ ] `vite build` başarılı
- [ ] CLAUDE.md'ye yeni endpoint/pattern dökümante edildi

## Riskler & Notlar

1. **Groq API quota:** Haftalık ~N şoför × 1 çağrı = düşük yük. Ama A.2 endpoint'i her UI tıklamasında LLM çağrısı yapmamalı → 30 dk cache zorunlu.
2. **Telegram bot rate limit:** 30 mesaj/sn limiti. Haftalık digest 100+ şoförde batch + throttle.
3. **PII:** Coaching mesajlarında plaka/şoför ismi şirket dışına gitmiyor (LLM Groq'a gider — Groq Terms incelenmesi).
4. **A/B test bias:** Skor değişimi yalnız koçluğa atfedilemez (mevsimsel, güzergah değişimi). MVP'de "delta'ya işaret eden" gözlem, "kanıtlanmış etki" değil — UI bunu açıkça belirtmeli.

## Önerilen Uygulama Sırası

```
1. A.1 (engine + unit testler) — bağımsız çalışabilir
2. A.2 (endpoints + Celery) — A.1'e bağımlı
3. A.3 (frontend) — A.2'ye bağımlı
4. A.4 (Telegram) — A.1+A.2'ye bağımlı, A.3 ile paralel olabilir
5. A.5 (etkinlik ölçümü) — hepsi tamamlandıktan sonra
```

Her adım kendi commit'i olur; A.1–A.5 toplam ~5 commit.
