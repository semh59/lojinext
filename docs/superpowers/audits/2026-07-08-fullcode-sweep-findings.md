# Tam-Kod Sweep Bulguları (2026-07-08/09)

Kampanya: [[2026-07-07-live-readiness-campaign]]. 647 dosya satır-satır + sözleşme
denetimi; her bulgu bağımsız adversarial doğrulamadan geçer.

**DURUM (2026-07-09, kullanıcı kararıyla DURDURULDU):** 63/166 grup (280 dosya)
tamamlandı ve kalıcı (workflow cache, run `wf_b61405af-9fe`). Kalan ~103 grup
KOŞULMADI — maliyet gerekçesiyle (bir resume turu ~9.5 dakikada ~3M token
yakıp oturum limitine çarpıyordu; haftalık kota riske girdi). Kullanıcı
"burada durdur, 63/166 ile yetin" dedi. Devam etmek istenirse: aynı
scriptPath + resumeFromRunId ile resume edilebilir, cache'li 63 grup bedava
replay olur, kalan ~103 grup çalışır (~yine saatlerce/birkaç pencere sürer).

**Kapsam dışı kalan alanlar (sweep tamamlanmadığı için TARANMADI):**
frontend'in tamamı (64 grup), micro-services (2 grup), 3 sözleşme denetçisi
(endpoint-envelope, frontend-consumption, ws-micro), backend'in ~40 grubu
(worker tasks, bazı repository'ler, bazı schema dosyaları — tam liste
`fullcode-sweep-fine.js` script'indeki backend dizisinin son ~40 elemanı).
Bu bölümler "0 kritik" iddiasının kanıtlanmadığı, sadece henüz-kontrol-
edilmemiş alanlardır — güvenli varsayılmamalı.

## Doğrulanmış KRİTİK (63 grup içinde)
_(yok)_

## Doğrulanmış MİNÖR (63 grup içinde)
_(yok — ama aşağıya bakın: 1 bulgu doğrulanamadan limite çarpıldı)_

## TEYİT EDİLEMEDİ (review bulundu, adversarial doğrulama oturum limitine çarptı — MANUEL BAKILMALI)

1. **`app/api/v1/endpoints/fleet_insights.py:31`** — `GET /fleet-insights/comparison`
   sadece kimlik doğrulaması (`get_current_active_user`) istiyor, rol/yetki
   kontrolü yok; kardeş filo-aggregate endpoint'i (`executive.py`)
   `require_yetki([super_admin, fleet_manager, yonetim_rapor])` ile korunuyor.
   **Senaryo:** düşük-yetkili bir hesap (ör. şoför rolü) geçerli JWT ile bu
   endpoint'i çağırıp filo geneli yakıt-maliyet/anomali/dönem-karşılaştırma
   verisini görebilir — kardeş endpoint'teki yetki geçidi burada yok, tutarsız
   RBAC yüzeyi. Bu bir review-ajanı bulgusu; adversarial çürütme ajanı oturum
   limitine çarpıp hiç koşamadı, yani "gerçek mi değil mi" ikinci bir gözden
   geçmedi. **Önerilen: kod satırını elle doğrulayın (require_yetki eksik mi,
   yoksa kasıtlı mı — ör. bu endpoint'in daha az hassas bir alt-küme
   döndürdüğü için düşük yetki yeterli olabilir).**

## INFO (koku — kritik değil, pilot sonrası değerlendirilecek)

### backend-06 grubu (AI/LLM katmanı, 10 dosya / 3181 satır — attested)
1. **`app/core/ai/llm_client.py:77`** — Retry döngüsü `max_retries+1` deneme yapar, log "attempt 3/2" basar ve SON başarısız denemeden sonra da gereksiz `asyncio.sleep` uygular. Etki: kalıcı 401'de fazladan ~1.5s boşa sleep + yanıltıcı log. İş sonucu değişmez.
2. **`app/core/ai/rag_engine.py:128`** — Upsert eski vektörü FAISS'ten silmez, metadata'da `_deleted` işaretler; her ARAC/SEFER_UPDATED yeni vektör ekler → index sınırsız büyür, `MAX_INDEX_SIZE` ölü kayıtlarla dolunca yeni indeksleme sessizce durur ("Learning silently stopped"). Etki: uzun-ömürlü instance'ta RAG context güncelliğini yitirir. **Pilot/uzun-koşum izlemesi gereken kalem.**
3. **`app/core/ai/rag_sync_service.py:96`** — `_on_sofor_changed/_on_sefer_changed` yalnız dict payload işler; event data int ID gelirse güncelleme sessizce atlanır → RAG'de bayat şoför/sefer verisi.
4. **`app/core/ai/recommendation_engine.py:226`** — Filo/kötü-araç SQL'leri `a.aktif` ve sefer soft-delete filtresi içermiyor → pasif/silinmiş araç "Acil bakım gerekli" önerisi üretebilir. **Doğrulanırsa minör'e yükselebilir (yanlış operasyonel öneri).**
5. **`app/core/container.py:501`** — `shutdown()` `_analiz_repo/_export_service/_internal_service`'i sıfırlamıyor → test izolasyonu bozulabilir; prod'da shutdown çağrılmadığı için etki test-sınırlı.
