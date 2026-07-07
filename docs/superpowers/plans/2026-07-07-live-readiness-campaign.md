# Canlı-Kullanıma Hazırlık Kampanyası (Live-Readiness)

**Hedef (kullanıcı tanımı):** canlı kullanımda 0 kritik hata, minimum küçük hata.
**Yöntem ilkesi:** sentetik test yeşili yeterli DEĞİL — her faz gerçek stack'te,
gerçekçi-kirli veriyle, düşmanca senaryolarla koşar; bulunan her şey
triage→fix→yeniden-koşum döngüsünden geçer (loop-until-dry). Hiçbir faz
"checkbox" ile kapanmaz; kapanış kanıtı = koşum çıktısı.

**Kritik hata tanımı (bu kampanyada):** veri kaybı/bozulması, yanlış iş sonucu
(yanlış tutar/tüketim/rapor), auth/RBAC atlatma, çökme/erişilemezlik,
kurtarılamayan durum. Küçük hata: kozmetik/UX pürüzü, yanlış metin, yavaşlık
(SLA içinde), retry ile geçen transient.

---

## Faz 0 — Zemin (SÜRÜYOR)
- [x] Main uçtan uca yeşil + prod deploy (2026-07-07, run 28881225641)
- [ ] Uçuştaki dilim: çift-mesaj UX + get_physics_params + locations/upload N+1
- [ ] Sentry-fix run yeşil teyidi
- [ ] **KULLANICI:** Telegram bot token'larını yenile (alarmsız pilot = kör pilot)

## Faz 1 — Gerçekçi Pilot Simülasyonu (dry-run)
Prod-benzeri taze stack (alembic'li boş DB + gerçek compose + api-stub DEĞİL
gerçek dış API'ler mümkünse; değilse stub + not) üzerinde:
1. **Kirli-gerçekçi Excel fixture üretimi** — gerçek dünya pisliği: Türkçe
   karakterli/boşluklu plakalar, karışık tarih formatları, boş/yarım satırlar,
   mükerrerler, 5.000+ satırlık dosyalar, yanlış kolon adları, Excel'in
   sayıyı metin yapması. (scripts/pilot/ altında üretici + fixture'lar.)
2. **Tam kullanıcı yolculuğu, gerçek HTTP ile** (jsdom değil): login →
   5 entity Excel import → dashboard/rapor doğrulama (SAYILAR elle hesaplanan
   beklentiyle karşılaştırılır, sadece 200 değil) → sefer yaşam döngüsü
   (planla→tamamla→tahmin/gerçek karşılaştırma) → anomali ack/resolve →
   export'lar → admin akışları.
3. **Düşmanca koşum:** bozuk dosyalar, eşzamanlı upload'lar, yarıda kesilen
   istekler, aynı dosyanın iki kez yüklenmesi (idempotency), yetkisiz denemeler.
Kapanış kanıtı: journey script'i exit 0 + beklenen-sayı eşleşme raporu +
düşmanca senaryoların her birinin doğru (4xx/idempotent) cevabı.

## Faz 2 — Derin Denetimler (taze, bağımsız paralel ajanlar)
[[deep-verify-fresh-agents]] deseni: her denetçi sıfır bağlamla, birbirinden
habersiz, canlı stack üzerinde:
- **D1 Güvenlik:** RBAC matris taraması (her rol × kritik endpoint), token
  süresi/blacklist, IDOR denemeleri, upload içerik doğrulama.
- **D2 Veri bütünlüğü:** Faz 1 sonrası DB invariant taraması (net_kg check,
  FK yetimleri, soft-delete tutarlılığı, çift kayıt), coverage_pct gerçeği.
- **D3 Yük:** CI Locust GO gate (workflow_dispatch, 50 kullanıcı) — p95 < 2s,
  fail < %1; ayrıca upload altında eşzamanlı okuma.
- **D4 Arıza tatbikatı (DR):** redis kill→davranış, db restart→kurtarma,
  worker kill→kuyruk devamı, **yedekten tam restore tatbikatı + süre ölçümü
  (RTO belgeleme)**.
- **D5 Gerçek tarayıcı UX turu:** ana akışların ekran görüntülü turu; konsol
  hataları, kırık durumlar, TR metin hataları.
- **D6 TAM-KOD satır-satır taraması (kullanıcı direktifi 2026-07-07: "en ufak
  satır atlanmasın"):** 325 backend + 314 frontend + 8 mikroservis dosyası
  (~122k satır) ~40 paralel denetçiye bölünür; HER dosya için denetçi
  "okundu + bulgu listesi VEYA açıkça 0-bulgu" beyanı verir — kapsam
  attestation'ı olmadan hiçbir dosya kapanmaz. Bulgular ikinci turda
  bağımsız düşman-doğrulayıcıdan geçer (yanlış-pozitif ayıklama).
- **D7 Katı haberleşme sözleşmeleri denetimi:** (a) routing tablosu ↔
  openapi.json ↔ response_model/hata-zarfı uyumu, endpoint endpoint;
  (b) frontend'in tükettiği HER alan backend şemasında gerçekten var mı
  (legacy .data.detail sınıfı hatalar), el-yazımı servisler ↔ orval üretimi
  tutarlılığı; (c) WebSocket/SSE + telegram_bot/ocr_service ↔ backend
  sözleşmeleri.
Kapanış: her denetçinin bulgu listesi → kritik/küçük triage.

## Faz 3 — Kapatma Döngüsü
Bulgular → kritikler anında fix + test + CI yeşili; küçükler listelenir,
kullanıcı önceliklendirir. Faz 1-2, kritik bulgu ÇIKMAYANA kadar tekrarlanır
(loop-until-dry, en az 2 temiz tur).

## Faz 4 — Gerçek Pilot (KULLANICI ile)
2 hafta gerçek veri + günlük kullanım. Çıkış kriteri: 0 kritik, alarmlar
çalışır, tahmin coverage %70+, çıkan küçükler günü gününe kapatılmış.
**"Kullanıma hazır" damgası ancak bu fazın sonunda vurulur.**

---

## Bilinen açık riskler (kampanya boyunca izlenir)
- CI-only aralıklı 500 (2 görülme; tuzak kurulu — tekrar ederse Faz 3'e kritik girer)
- GHCR build flake (2/3; altyapı görünümlü, izleniyor)
- Tek host (DR tatbikatı D4'te RTO'ya bağlanacak)
- Open-Meteo free tier (gerçek çok-kullanıcı yükünde 429 riski — D3'te ölçülür)
