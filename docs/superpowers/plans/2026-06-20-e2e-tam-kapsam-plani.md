# E2E Tam Kapsam Planı — Her Sayfa Her Buton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Hedef:** 166 → 280+ test. Tüm route'lar, tüm butonlar, tüm form submit yolları, tüm hata durumları kapsanacak.

**Mevcut durum (2026-06-20):** 166/167 PASS, 1 SKIP, 21 spec dosyası.

**Kural seti (tüm testler için):**
- `page.unroute(pattern)` → her re-registration öncesinde
- `waitForTimeout()` yok → `waitForResponse` / `waitForSelector` / `toBeVisible()`
- Turkish chars için `/i` flag yok → exact string veya uppercase-explicit regex
- `{ exact: true }` → substring match riski olan `getByText` için

---

## Mevcut Durum Envanteri

| Spec | Test Sayısı | Kapsanan Buton/Form |
|------|-------------|---------------------|
| auth.spec.ts | 5 | login, logout, 404, private route |
| dashboard.spec.ts | 8 | KPI kartlar, anomali widget, bildirim bell |
| trips.spec.ts | 11 | liste, oluştur, filtrele, sil, stat kartlar |
| fuel.spec.ts | 10 | CRUD, istatistik, Excel export |
| fleet.spec.ts | 7 | araç CRUD, dorses tab geçiş |
| drivers.spec.ts | 5 | liste, oluştur, sil |
| locations.spec.ts | 8 | CRUD, arama, pagination |
| alerts.spec.ts | 8 | KPI, tab filtre, boş durum |
| predictions.spec.ts | 8 | metrik kartlar, tab bar render |
| reports.spec.ts | 6 | kartlar, export dialog, cost chart |
| monitoring.spec.ts | 6 | temel yükleme |
| coaching.spec.ts | 9 | şoför seç, insights, boş/hata durumu |
| fleet-insights.spec.ts | 8 | period switch, karşılaştırma |
| executive.spec.ts | 9 | tüm kartlar, WhatIf, PDF butonu |
| profile.spec.ts | 2 | profil yükle, ad güncelle |
| admin.spec.ts | 14 | overview, kullanıcılar, roller, konfig, ML, bildirimler |
| roller.spec.ts | 11 | CRUD, yetki validation, sil onayı |
| dogruluk.spec.ts | 9 | period switch, metrik kartlar, boş durum |
| atama.spec.ts | 9 | form validasyon, submit, hata durumu |
| veri-yonetim.spec.ts | 9 | import geçmişi, rollback |
| navigation.spec.ts | 4 | sayfa geçişi, geri tuşu |
| **TOPLAM** | **166** | |

---

## SIFIR KAPSAMLI SAYFALAR — Yeni Spec Dosyaları

### Görev 1 — `today.spec.ts` (Route: `/today`)

**Sayfa:** TodayPage — admin/super_admin için ana giriş noktası. Tab switcher + triage item cards + KPI sayaçlar.

- [ ] 1.1 Sayfa başlığı görünür ve aktif sefer sayacı render edilir
- [ ] 1.2 Tab: "Tümü" varsayılan aktif, tüm itemlar listelenir
- [ ] 1.3 Tab: "Anomali" → sadece `category: 'anomaly'` itemlar görünür
- [ ] 1.4 Tab: "Bakım" → sadece `category: 'maintenance'` itemlar görünür
- [ ] 1.5 Tab: "Soruşturma" → sadece `category: 'investigation'` itemlar görünür
- [ ] 1.6 `severity: 'critical'` olan item kırmızı bölümde ayrı gösterilir
- [ ] 1.7 Boş durum — `items: []` → yeşil "Her şey yolunda" mesajı
- [ ] 1.8 Backend 500 → hata mesajı render edilir, sayfa çökmez
- [ ] 1.9 QuickActionsBar render edilir (en az 1 aksiyon butonu görünür)

**Mock endpoint:** `**/api/v1/today/triage**`

```typescript
const MOCK_TRIAGE = {
  items: [
    { id: 1, category: 'anomaly', severity: 'critical', title: 'Yakıt açığı tespit edildi', description: '...', entity_id: 1 },
    { id: 2, category: 'maintenance', severity: 'warning', title: 'Muayene tarihi yaklaşıyor', description: '...', entity_id: 2 },
    { id: 3, category: 'investigation', severity: 'info', title: 'Güzergah sapması', description: '...', entity_id: 3 },
  ],
  active_trips_count: 5,
  completed_today_count: 12,
}
```

---

### Görev 2 — `route-lab.spec.ts` (Route: `/route-lab`)

**Sayfa:** RouteLabPage — güzergah simülasyon formu + sonuç (RouteSimSummary + chart + heatmap).

- [ ] 2.1 Sayfa başlığı ve açıklama metni görünür
- [ ] 2.2 "Simüle Et" butonu görünür, form alanları render edilir
- [ ] 2.3 Boş form submit → form submit gerçekleşmez (HTML5 required)
- [ ] 2.4 Dolu form submit → POST `/api/v1/simulate` isteği gönderilir
- [ ] 2.5 Sonuç yükleniyor → spinner görünür
- [ ] 2.6 Başarılı simülasyon → RouteSimSummary (toplam km, litre, süre) görünür
- [ ] 2.7 elevation_coverage_pct < 100 → amber uyarı banner görünür
- [ ] 2.8 API 429 → "Hız limiti aşıldı" hata mesajı
- [ ] 2.9 API 502 → "Sağlayıcı erişilemiyor" hata mesajı
- [ ] 2.10 Genel hata → generic hata mesajı render edilir

**Mock endpoint:** `**/api/v1/simulate**`

```typescript
const MOCK_SIM_RESULT = {
  total_km: 451.2, total_l: 135.8, total_eta_sec: 18000,
  avg_l_per_100km: 30.1, elevation_coverage_pct: 85,
  segments: [{ km: 50, l_per_100km: 28.5, elevation_m: 120 }],
}
```

---

### Görev 3 — `reports-studio.spec.ts` (Route: `/reports`)

**Sayfa:** ReportsStudioPage — 5 rapor şablonu, format/period config, indirme.

- [ ] 3.1 Sayfa başlığı ve şablon kartları görünür (en az 3 şablon)
- [ ] 3.2 Şablon seçildiğinde ReportConfigPanel açılır
- [ ] 3.3 Format seçimi (PDF/Excel) değiştirilebilir
- [ ] 3.4 Period seçimi (7/30/90 gün) değiştirilebilir
- [ ] 3.5 "İndir" butonu → GET/POST isteği gönderilir, blob response
- [ ] 3.6 Backend 500 → sayfa çökmez, hata mesajı görünür
- [ ] 3.7 Yükleme durumu → spinner veya disabled state görünür
- [ ] 3.8 Seçim iptal → panel kapanır veya başka şablon seçilebilir

**Mock endpoints:** `/api/v1/reports/**`

---

### Görev 4 — `bakim.spec.ts` (Route: `/maintenance`)

**Sayfa:** BakimPage (AdminMaintenancePage) — bakım tahminleri, geçmiş, takvim view + yeni giriş modalı.

- [ ] 4.1 Sayfa yüklenir ve araç listesi/bakım kayıtları görünür
- [ ] 4.2 View: "Tahminler" butonuyla tahmin tablosu görünür
- [ ] 4.3 View: "Geçmiş" butonuyla geçmiş tablosu görünür
- [ ] 4.4 View: "Takvim" butonuyla takvim görünümü render edilir
- [ ] 4.5 "Yeni Giriş" butonu → modal açılır
- [ ] 4.6 Boş modal form submit → validasyon hatası gösterilir
- [ ] 4.7 Dolu form submit → POST isteği gönderilir ve modal kapanır
- [ ] 4.8 Tahmin tablosunda "Tamamla" butonu → PATCH/PUT isteği gönderilir
- [ ] 4.9 Backend 500 → sayfa çökmez
- [ ] 4.10 Modal "İptal" butonu → modal kapanır, POST isteği gönderilmez

**Mock endpoints:** `**/api/v1/maintenance/**`, `**/api/v1/vehicles/**`

---

### Görev 5 — `analytics.spec.ts` (Route: `/admin/analitik`)

**Sayfa:** AnalyticsPage — kullanım analitiği (top/bottom routes, total views).

- [ ] 5.1 Sayfa başlığı "Kullanım Analitiği" görünür
- [ ] 5.2 "En çok kullanılan" rota listesi render edilir
- [ ] 5.3 "En az kullanılan" rota listesi render edilir
- [ ] 5.4 Period (30 gün) ve toplam görüntüleme sayısı gösterilir
- [ ] 5.5 Backend 500 → "Yükleniyor…" spinner veya hata gracefully handle edilir

**Mock endpoint:** `**/api/v1/admin/analytics/page-views**`

```typescript
const MOCK_ANALYTICS = {
  period_days: 30, total_views: 1240,
  top_routes: [{ route: '/trips', count: 450 }, { route: '/fuel', count: 310 }],
  bottom_routes: [{ route: '/route-lab', count: 5 }],
}
```

---

### Görev 6 — `home.spec.ts` (Route: `/`)

**Sayfa:** HomePage — rol bazlı render (admin → TodayPage, driver → DashboardPage).

- [ ] 6.1 super_admin rolüyle `/` → TodayPage içeriği (triage başlık) görünür
- [ ] 6.2 driver rolüyle `/` → DashboardPage içeriği (KPI kartlar) görünür
- [ ] 6.3 `/` → `/login` redirect: yetkisiz erişimde çalışır

---

## MEVCUT SPEC GENİŞLETMELERİ

### Görev 7 — `profile.spec.ts` → +7 test (2 → 9)

**Eksik:** şifre değiştirme formu, push notification toggle, quiet hours.

- [ ] 7.1 Şifre formu: mevcut şifre boşsa validasyon
- [ ] 7.2 Şifre formu: yeni şifre 8 karakter altı → kural ihlali gösterilir
- [ ] 7.3 Şifre formu: şifreler eşleşmiyorsa "Şifreler eşleşmiyor" hatası
- [ ] 7.4 Şifre formu: geçerli submit → POST `/users/me/change-password` gönderilir
- [ ] 7.5 Şifreyi göster/gizle → input type değişir
- [ ] 7.6 Sessiz saatleri kaydet → POST `/preferences` gönderilir
- [ ] 7.7 Push notification "Etkinleştir" butonu görünür (unsupported tarayıcıda "BellOff" mesajı)

---

### Görev 8 — `drivers.spec.ts` → +8 test (5 → 13)

**Eksik:** düzenleme, skor güncelleme, XAI paneller (score-breakdown, route-profile).

- [ ] 8.1 Düzenle butonu → modal açılır ve mevcut değerler dolu gelir
- [ ] 8.2 Düzenle submit → PUT isteği gönderilir
- [ ] 8.3 Manuel skor güncelleme → POST `/drivers/{id}/score` isteği
- [ ] 8.4 Skor güncelleme sonrası toast gösterilir
- [ ] 8.5 XAI: "Skor Dökümü" kartı görünür → hibrit skor formülü (manual/auto ağırlık)
- [ ] 8.6 XAI: `has_trips: false` → "Henüz sefer verisi yok" mesajı
- [ ] 8.7 XAI: "Güzergah Profili" kartı görünür → 4 güzergah tipi
- [ ] 8.8 Aktif/pasif filtresi → sadece aktif şoförler listelenir

---

### Görev 9 — `alerts.spec.ts` → +6 test (8 → 14)

**Eksik:** anomali onayla/çöz butonları, period filtresi.

- [ ] 9.1 Anomali "Onayla" butonu → POST `/anomalies/{id}/acknowledge`
- [ ] 9.2 Onay sonrası badge "Onaylandı" olarak güncellenir
- [ ] 9.3 Anomali "Çöz" butonu → POST `/anomalies/{id}/resolve` (body: notes)
- [ ] 9.4 Çözüm sonrası badge "Çözüldü" olur
- [ ] 9.5 Period: "7 gün" seçilince API isteği period=7 içerir
- [ ] 9.6 Period: "90 gün" seçilince API isteği period=90 içerir

---

### Görev 10 — `fleet.spec.ts` → +7 test (7 → 14)

**Eksik:** dorse CRUD, araç arama, muayene uyarıları.

- [ ] 10.1 Dorseler sekmesi → dorse listesi yüklenir
- [ ] 10.2 Yeni Dorse butonu → modal açılır
- [ ] 10.3 Boş dorse formu → validasyon hatası
- [ ] 10.4 Dorse oluştur → POST `/trailers/` gönderilir
- [ ] 10.5 Dorse sil → DELETE isteği gönderilir
- [ ] 10.6 Araç arama input → filtre çalışır (API veya client-side)
- [ ] 10.7 Muayene uyarısı: `/vehicles/inspection-alerts` → uyarı varsa banner görünür

---

### Görev 11 — `trips.spec.ts` → +7 test (11 → 18)

**Eksik:** dönüş seferi, durum güncelleme, Excel export, Plan Wizard adımları.

- [ ] 11.1 Durum: "PLANLANDI" → "DEVAM EDİYOR" güncelleme butonu görünür
- [ ] 11.2 Durum güncelleme → PATCH isteği gönderilir
- [ ] 11.3 Excel export butonu → GET `/trips/excel` isteği
- [ ] 11.4 Dönüş seferi: "Dönüş Ekle" butonu → POST `/trips/{id}/return`
- [ ] 11.5 Plan Wizard: İlk adım (Temel Bilgiler) form alanları görünür
- [ ] 11.6 Plan Wizard: "İleri" butonu → 2. adıma geçer
- [ ] 11.7 Sefer detay paneli: içerik yüklendiğinde temel alanlar görünür

---

### Görev 12 — `monitoring.spec.ts` → +5 test (6 → 11)

**Eksik:** tab geçişi, canlı event akışı, temizle butonu.

- [ ] 12.1 Tab: "Bildirimler" → bildirim listesi render edilir
- [ ] 12.2 Tab: "Hata Olayları" → hata event listesi görünür
- [ ] 12.3 Tab: "Eğitim" → ML eğitim log akışı render edilir
- [ ] 12.4 "Tümünü Temizle" butonu (bildirimler tab) → liste boşalır
- [ ] 12.5 Backend event stream veri → en az 1 event satırı DOM'da görünür

---

### Görev 13 — `predictions.spec.ts` → +5 test (8 → 13)

**Eksik:** tab geçişi, simülatör form, zaman serisi.

- [ ] 13.1 Tab: "Genel Bakış" → ensemble kart görünür
- [ ] 13.2 Tab: "Simülatör" → form alanları (araç, yük) görünür
- [ ] 13.3 Simülatör: form submit → POST `/predictions/simulate` gönderilir
- [ ] 13.4 Simülatör: sonuç → tahmini tüketim litresi gösterilir
- [ ] 13.5 Tab: "Zaman Serisi" → grafik başlığı veya boş durum görünür

---

### Görev 14 — `coaching.spec.ts` → +3 test (9 → 12)

**Eksik:** koçluk gönderme dialogu.

- [ ] 14.1 "Koçluk Gönder" butonu (insights içinde) → dialog/modal açılır
- [ ] 14.2 Dialog: mesaj formu doldurulup submit → POST `/coaching/{id}/send`
- [ ] 14.3 Başarılı gönderim → toast mesajı görünür

---

### Görev 15 — `locations.spec.ts` → +4 test (8 → 12)

**Eksik:** analiz modalı, geocode arama.

- [ ] 15.1 "Analiz" butonu → analiz modalı açılır
- [ ] 15.2 Analiz modalı: hesapla → POST `/locations/{id}/analyze`
- [ ] 15.3 Güzergah arama: input doldurulunca GET `/locations/search?q=` gönderilir
- [ ] 15.4 Arama sonuçları listede görünür

---

### Görev 16 — `auth.spec.ts` → +3 test (5 → 8)

**Eksik:** şifremi unuttum formu.

- [ ] 16.1 "Şifremi Unuttum" link tıklanınca email formu görünür
- [ ] 16.2 Email gönder submit → POST `/auth/forgot-password` gönderilir
- [ ] 16.3 "Geri Dön" butonu → login formuna döner

---

### Görev 17 — `admin.spec.ts` (KonfigurasyonPage) → +4 test (14 → 18)

**Eksik:** konfig kaydetme.

- [ ] 17.1 KonfigurasyonPage yüklenir ve ayar anahtarları listelenir
- [ ] 17.2 Input değeri değiştirilip "Kaydet" → PUT/POST isteği gönderilir
- [ ] 17.3 Başarılı kayıt → toast görünür
- [ ] 17.4 Backend 422 → validasyon hatası inline gösterilir

---

## ÖZET SAYILAR

| Dilim | Yeni Dosya | +Test |
|-------|-----------|-------|
| Görev 1 today.spec.ts | ✓ yeni | +9 |
| Görev 2 route-lab.spec.ts | ✓ yeni | +10 |
| Görev 3 reports-studio.spec.ts | ✓ yeni | +8 |
| Görev 4 bakim.spec.ts | ✓ yeni | +10 |
| Görev 5 analytics.spec.ts | ✓ yeni | +5 |
| Görev 6 home.spec.ts | ✓ yeni | +3 |
| Görev 7–17 (mevcut spec genişletme) | — | +59 |
| **TOPLAM** | **6 yeni** | **+104** |

**Hedef: 166 + 104 = 270 test**

---

## Mock Altyapısı — Gereken Eklemeler

`frontend/e2e/mocks/index.ts` dosyasına eklenecekler:

```typescript
// Görev 1 — Today
export const MOCK_TRIAGE_ITEM = { id: 1, category: 'anomaly', severity: 'critical', title: 'Yakıt açığı', description: 'Açıklama', entity_id: 1 }
export async function setupTodayMocks(page: Page) { ... }

// Görev 2 — Route Lab
export const MOCK_SIM_RESULT = { total_km: 451.2, total_l: 135.8, total_eta_sec: 18000, avg_l_per_100km: 30.1, elevation_coverage_pct: 85, segments: [] }
export async function setupRouteLabMocks(page: Page) { ... }

// Görev 4 — Bakim
export const MOCK_MAINTENANCE = { id: 1, arac_id: 1, bakim_tipi: 'PERIYODIK', planlanan_tarih: '2026-07-01', tamamlandi: false }
export async function setupBakimMocks(page: Page) { ... }

// Görev 5 — Analytics
export const MOCK_PAGE_VIEWS = { period_days: 30, total_views: 1240, top_routes: [{ route: '/trips', count: 450 }], bottom_routes: [{ route: '/route-lab', count: 5 }] }
```

---

## Teknik Notlar

**`today-service.ts` mock formatı için:** `GET /api/v1/today/triage` → `{ items: [...], active_trips_count: N, completed_today_count: N }`

**`RouteSimForm` submit için:** Form `onSubmit` callback çağırıyor, `page.locator('button[type="submit"]')` veya `page.getByRole('button', { name: 'Simüle Et', exact: true })`

**`BakimPage` view switcher:** `page.getByRole('button', { name: 'Tahminler', exact: true })` — tab butonları `type="button"`.

**`ReportsStudioPage` template kartları:** `page.locator('[data-template-id], button').filter(...)` — implementation'a göre güncellenecek.

**HomePage testi:** `authedPage` fixture'ı super_admin döndürüyor, dolayısıyla `/` → TodayPage. Driver testi için ayrı fixture veya auth mock override gerekiyor.
