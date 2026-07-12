# Modül Görevi: ai_assistant (dalga 12/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/ai_assistant/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** analytics-executive dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (15 dosya, 3.610 LOC)
```
app/api/v1/endpoints/ai.py
app/api/v1/endpoints/feedback.py
app/core/ai/__init__.py
app/core/ai/chatbot.py
app/core/ai/context_builder.py
app/core/ai/groq_service.py
app/core/ai/llm_client.py
app/core/ai/prompt_tuner.py
app/core/ai/rag_engine.py
app/core/ai/rag_sync_service.py
app/core/ai/recommendation_engine.py
app/core/ai/trip_planner.py
app/core/services/ai_service.py
app/schemas/trip_planner.py
app/services/smart_ai_service.py
```

## 2. Route envanteri (5 route)
`ai.py`(4) + `feedback.py`(1) = 5.

## 3. Tablo sahipliği
Yok — FAISS dosya-tabanlı indeks (`app/data/ai_kb/`), DB tablosu yok. Docker `app_data` named volume üzerinden persist ediyor (proje CLAUDE.md'sinde dokümante — çoklu-replica'da paylaşımlı).

## 4. Bağlaşıklık karnesi
- **out (en dolaşık 2. tüketici — 17 statement):** ai_assistant→fleet 3, ai_assistant→driver 3, ai_assistant→admin_platform 2, ai_assistant→prediction_ml 2, ai_assistant→trip 2, ai_assistant→notification 1, ai_assistant→reports 1, ai_assistant→fuel 1, ai_assistant→analytics_executive 1, ai_assistant→route_simulation 1
- **in (az — 7):** trip→ai_assistant 2, driver→ai_assistant 1, prediction_ml→ai_assistant 2 (`prediction_service.py`→`smart_ai_service.py`, `prediction_tasks.py`→`llm_client.py`), admin_platform→ai_assistant 1, anomaly→ai_assistant 1
- **Event subscriber (rag_sync_service.py, 6 site — MEMORY §3):** `_on_arac_changed`(ARAC_ADDED/UPDATED), `_on_sofor_changed`(SOFOR_ADDED/UPDATED), `_on_sefer_changed`(SEFER_ADDED/UPDATED) — bu 6 abonelik ASENKRON kalır (B.2 kararı: ai_assistant←CRUD event'leri), `events.py`'de DTO tipine bağlanır.
- `context_builder.py` fleet/trip/fuel/reports'a doğrudan repo erişimi (raw import, event değil) — bu senkron okuma yolu `public.py` çağrısına çevrilir (context oluşturma anlık ihtiyaç, event beklemez).

## 5. Taşıma adımları
1. İskelet oluştur.
2. `rag_engine.py`, `rag_sync_service.py` → `infrastructure/rag/` (FAISS indeks yönetimi, volume-paylaşımlı davranış korunur).
3. `groq_service.py`, `llm_client.py` → `infrastructure/llm_client.py` (dış API).
4. `context_builder.py` → `application/build_context.py`; 4 modüle (fleet/trip/fuel/reports) olan doğrudan repo erişimi public.py çağrılarına çevrilir.
5. `chatbot.py`, `recommendation_engine.py`, `prompt_tuner.py`, `trip_planner.py` → `application/`.
6. `ai_service.py`, `smart_ai_service.py` → orkestrasyon katmanı, `application/orchestrate_ai_response.py`.
7. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 15 dosya taşındı
- [ ] rag_sync_service'in 6 event aboneliği `events.py` DTO'larına bağlı, ORM sızıntısı testi yeşil
- [ ] context_builder'ın 4-modül doğrudan erişimi public.py'ye çevrildi
- [ ] FAISS volume-paylaşım davranışı REGRESYONSUZ (çoklu-replica testi varsa geçiyor)
