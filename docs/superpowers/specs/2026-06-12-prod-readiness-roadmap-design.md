# Prod-Readiness Yol Haritası — Tasarım

**Tarih:** 2026-06-12
**Durum:** Onay bekliyor
**Kapsam:** LojiNext'in "tam hazır prod ürün" hedefine giden önceliklendirilmiş faz haritası. Her büyük faz kendi spec → plan → uygulama döngüsüyle yürür; bu doküman üst-seviye haritadır.

---

## 1. Hedef ve Alınan Kararlar

| Karar | Seçim |
|---|---|
| Başarı kriteri | Tüm eksen birlikte: özellik tamamlama + operasyonel sertleşme + pilot go-live |
| Müşteri modeli | Önce tek müşteriyle pilot; multi-tenant sonraki faz (pilotu bloklamaz) |
| Deploy hedefi | VPS + docker-compose (`docker-compose.prod.yml` mevcut) |
| Pilot durumu | Gerçek Excel geçmiş verisi + günlük kullanacak operatör/şoförler hazır bekliyor |
| Zaman | Tarih baskısı yok; kalite öncelikli |
| Sıralama stratejisi | **Feature-first**: önce özellik kalemleri lokalde biter, prod kurulumu sona |
| Go-live öncesi zorunlu özellikler | Reports/yönetim v2, route segment simulation, audit DB wiring, web push + Feature H/I/J(kalan)/L + 5 CTO önerisi |

Feature E (Strategic Cockpit) zaten tamamlanmış — kapsam dışı.

## 2. Faz Haritası

### Faz 0 — Temiz zemin *(küçük)*
- `chore/arch005-sefer-model-unify` (27 commit) → `main`'e merge; push engeli (billing) çözülür ya da lokal merge ile devam.
- `Dockerfile`'a `COPY scripts /app/scripts`.
- CLAUDE.md drift düzeltmeleri (8→15 servis, scripts notu güncelleme).
- **Kabul:** `main` güncel, CI yeşil, container'da `python -m scripts.e2e_pilot_smoke` docker cp'siz çalışıyor.

### Faz 1 — Tahmin backfill job *(küçük — CTO önerisi 1)*
- Sefer create'teki 2.5s timeout nedeniyle `tahmini_tuketim=NULL` kalan seferleri gece bulan ve estimator'ı timeout'suz çalıştırıp dolduran Celery beat task'i.
- **Gerekçe:** Ürünün ana vaadi yakıt tahmini; pilotta NULL tahmin "çalışmıyor" algısı yaratır.
- **Kabul:** Tahminisiz sefer oluştur → gece task'i (veya manuel tetik) sonrası `tahmini_tuketim` + `route_simulation_id` dolu; `GET /admin/fuel-accuracy` `coverage_pct` artışı gözlemlenir. Open-Meteo 429 retry pattern'ine uyulur (CLAUDE.md gotcha).

### Faz 2 — Audit DB wiring *(küçük)*
- `audit_logger` → `admin_audit_log` tablosuna insert (JSON dosya logu korunur, çift yazım). `@audit_log` decorator ve `log_audit_event` her ikisi de tabloya düşer.
- **Kabul:** Admin aksiyonu sonrası tabloda `istek_id` correlation ID ile eşleşen satır; audit yazımı ana işlemi asla bloklamaz (best-effort, `AuditLogError` sözleşmesi korunur).

### Faz 3 — Kullanım analitiği *(küçük — CTO önerisi 5)*
- Kendi DB'sinde page-view kaydı (route, user_id, timestamp); dış servis yok. Basit bir admin görünümü (en çok/az kullanılan sayfalar).
- **Gerekçe:** Erken kurulur ki Faz 10 (Reports v2) tasarımı gerçek kullanım verisiyle yapılsın.
- **Kabul:** Sayfa gezintisi kayıt üretiyor; admin ekranında sayfa bazlı sayım görünüyor; kayıt hacmi kontrollü (örn. günlük aggregate veya basit retention).

### Faz 4 — Web push *(küçük-orta)*
- VAPID key üretimi, `.env` set, `PUSH_NOTIFICATION_ENABLED=true`; subscribe → `push_subscriptions` upsert akışı; en az iki tetikleyici (kritik anomali, muayene yaklaşan) uçtan uca.
- **Kabul:** Gerçek tarayıcıda bildirim alınıyor; abonelik iptali ve süresi dolmuş endpoint temizliği çalışıyor.

### Faz 5 — Feature L: Akıllı bildirim akışı *(orta)*
- `notification_prioritizer` (kullanıcı geçmiş aksiyonlarına göre önemli/önemsiz), sessiz saatler/zamanlama, haftalık "dikkat etmen gereken 3 şey" digest'i, bildirim ayarları UI.
- **Gerekçe:** Push'un (Faz 4) hemen üstüne kurulur; bildirim yorgunluğunu go-live'dan önce çözer.
- **Kabul:** Önceliklendirme ve sessiz saat ayarı çalışır; digest Celery beat ile üretilir.

### Faz 6 — Feature J: OCR web entegrasyonu (kalan kısım) *(küçük-orta)*
- Mevcut: Telegram → OCR → `sefer_belgeler` akışı çalışıyor. Eksik: FuelPage "Belge Yükle" UI, OCR servisine REST bridge, OCR sonucundan kullanıcı onaylı yakıt kaydı oluşturma, belge arşivi görünümü.
- **Kabul:** Web'den fiş fotoğrafı yükle → OCR önizleme → onayla → `yakit_alimlari` kaydı oluşur.

### Faz 7 — Route segment simulation *(büyük — kendi spec/plan döngüsü)*
- 2026-05-28 kararı: Mapbox maxspeed per-segment veri; sefer-aggregate yetmez, derin+detaylı plan şart. Faz başında ayrı brainstorm + spec yapılır; bu doküman yalnız yer ayırır.
- **Kabul (üst-seviye):** `scripts/p51_real_world_validation.py` 5/5 GREEN veya bilinçli kabul edilmiş sapmalar; fuel-accuracy coverage düşmemiş.

### Faz 8 — Feature H: Anomali kümeleme *(orta)*
- `app/core/ml/anomaly_clustering.py` (DBSCAN/HDBSCAN), günlük Celery task, `GET /anomalies/clusters`, AlertsPage "Pattern" sekmesi, Groq ile cluster insight metni.
- **Kabul:** Pilot geçmiş verisiyle en az bir anlamlı cluster; LLM insight feature-flag arkasında (Groq kesintisi pattern listesini bloklamaz).

### Faz 9 — Feature I: AI sorgulama paneli *(orta)*
- Mevcut `ChatAssistant` + `POST /ai/chat` üstüne: sorgu kategorileri, otomatik grafik üretimi (LLM → chart JSON), Web Speech API sesli komut, cevap içi aksiyon linkleri.
- **Gerekçe:** Segment sim + cluster verilerinden sonra gelir ki otomatik grafikler bu verileri de kullanabilsin.
- **Kabul:** Kategori seçimiyle sorgu; en az bir sorgu tipinde otomatik grafik; aksiyon linki doğru sayfaya götürür.

### Faz 10 — Reports/yönetim v2 *(büyük — kendi spec/plan döngüsü + UX turu)*
- Yetersiz bulunan yönetim+rapor sayfalarının yeniden tasarımı. Faz 3'ün kullanım analitiği verisi tasarım girdisidir; segment sim, cluster, audit verileri rapor yüzeyine girer. Başında kullanıcıyla ayrı UX brainstorm'u yapılır.
- **Kabul (üst-seviye):** Kullanıcının "günlük operasyonu bu ekranlardan yönetirim" onayı.

### Faz 11 — Prod kurulum + operasyonel sertleşme *(orta)*
- VPS temin + `docker-compose.prod.yml` kurulum; domain + TLS (Caddy/Traefik kararı bu fazda); `.env.prod` (tüm prod zorunluları + `USE_SEFER_FUEL_ESTIMATOR=true`); pilot Excel verisi yükleme + e2e smoke.
- Backup-restore **tatbikatı** (yedekten gerçek geri dönüş); alerting uçtan uca doğrulama (sahte CRITICAL → Telegram); Open-Meteo/Mapbox kota gözlemi; kısa runbook (restart, yedek dönüşü, sık arızalar, migration prosedürü).
- **CTO önerileri:** dışarıdan uptime izleme (UptimeRobot/healthchecks.io → `/health/liveness`); pilot feedback butonu (frontend → Telegram OPS); KVKK mini paketi (veri envanteri, şoför aydınlatma metni, saklama süresi kararı).
- **Kabul:** Dış ağdan TLS'li erişim; restore tatbikatı belgeli; alarm zinciri kanıtlı; uptime izleme aktif; KVKK belgeleri repo'da.

### Faz 12 — Go-live + pilot izleme *(küçük + 2 hafta gözlem)*
- Operatör hesapları + rol ataması, kısa onboarding.
- İlk 2 hafta izlenen metrikler: Sentry hataları, fuel-accuracy `coverage_pct`, anomali false-positive oranı, Open-Meteo 429 sayısı, feedback butonu girdileri.
- **Kabul:** 2 hafta kesintisiz veri girişi; çözülmemiş kritik Sentry hatası yok.

### Faz 13+ — Canlı sonrası backlog
Multi-tenant epic (`tenant_id` + RLS), şoför PWA (Feature G), müşteri bildirim (F), Insurance API (K), demo/satış ortamı.

## 3. Genel Kabul Kriterleri (her fazda)

- CI hard gate'leri: `ruff check` 0, `mypy` 0, `pytest` unit+integration %70+ coverage, `vitest --run` + `vite build`, `alembic check`.
- Her faz sonunda commit'lenmiş, çalışır durum; faz yarıda bırakılıp diğerine geçilmez.

## 4. Varsayımlar ve Riskler

| Risk / Varsayım | Etki | Önlem |
|---|---|---|
| Push engeli (billing) sürerse `main` merge lokalde kalır | CI doğrulaması gecikir | Faz 0'da çözüm; gerekirse lokal merge + CI komutlarını lokalde koş |
| Open-Meteo free tier dakikalık limiti | Backfill job ve segment sim'de 429 | Mevcut retry pattern (Retry-After/1.5s + tek retry) zorunlu; backfill gece + düşük tempo |
| Mapbox API maliyeti pilot trafiğinde belirsiz | Beklenmeyen fatura | Faz 11'de kota gözlemi; 24h TTL cache mevcut |
| Reports v2 kapsamı UX turunda büyüyebilir | Takvim kayar | Faz 10 spec'inde MVP sınırı net çizilir; tarih baskısı yok |
| Tek geliştirici | Fazlar seri ilerler | Sıralama buna göre tasarlandı (feature-first, context-switch yok) |

## 5. Kapsam Dışı (bilinçli)

K8s/orchestrator, API gateway, feature-flag servisi, data warehouse, demo ortamı, multi-tenant (Faz 13+'a ertelendi).
