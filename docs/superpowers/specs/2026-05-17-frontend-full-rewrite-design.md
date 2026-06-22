# Frontend Tam Yeniden Yazım Tasarımı

**Tarih:** 2026-05-17
**Durum:** Onaylı
**Kapsam:** LojiNext React/TypeScript frontend — backend kapasitesiyle hizalı tam yeniden tasarım

---

## Problem

Mevcut frontend, backend'in sunduğu kapasitenin küçük bir kısmını yansıtıyor:
- Dashboard yok; giriş CRUD tablosuna düşüyor
- ML tahminler, anomali tespiti, WebSocket için UI yok
- Mevcut sayfalar sığ (FleetInsights: 3 sayı kartı; Admin Overview: liste, grafik yok)
- "Elite Zen" gibi anlamsız marka yazıları sidebar'da görünüyor
- `/alerts`, `/monitoring`, `/intelligence` route'ları `/trips`'e yönlendiriliyor

## Hedef

Backend endpoint'lerini tam olarak yüzeyine çıkaran, operasyonel ve analitik olarak derin bir lojistik ops dashboard.

---

## Bilgi Mimarisi

### Sidebar Navigasyonu (Gruplandırılmış)

```
── Dashboard          /
── Operasyon ──────────────────────
   Seferler           /trips
   Canlı Takip        /monitoring       ← YENİ
   Yakıt              /fuel
── Filo ────────────────────────────
   Araçlar/Sürücüler  /fleet
   Lokasyonlar        /locations
── Analitik ────────────────────────
   Anomaliler         /alerts           ← YENİ
   ML Tahminler       /predictions      ← YENİ
   Raporlar           /reports
── Sistem ──────────────────────────
   Yönetim            /admin
```

---

## Korunan Katman (Değişmez)

| Klasör | Durum | Açıklama |
|--------|-------|----------|
| `frontend/src/services/api/` | **Değişmez** | Tüm servis dosyaları, API bağlantıları |
| `frontend/src/components/ui/` | **Değişmez** | Card, Badge, Button, Table, Modal, Input |
| `frontend/src/context/` | **Değişmez** | AuthContext, NotificationContext |
| `frontend/src/stores/` | **Değişmez** | Zustand persist stores |
| `frontend/src/test/` | **Değişmez** | Test altyapısı |
| `frontend/src/i18n.ts` | **Değişmez** | i18n konfigürasyonu |
| `frontend/src/types/` | **Değişmez** | Type tanımları |

---

## Değişen Dosyalar

### `EliteLayout.tsx`
- "Elite Zen" yazısı kaldırılır, logo sadece "LojiNext" olarak kalır
- Sidebar'a grup başlıkları eklenir (Operasyon, Filo, Analitik, Sistem)
- Yeni route'lar nav'a eklenir: `/monitoring`, `/alerts`, `/predictions`
- Grup başlıkları için ikon: Activity (Operasyon), Truck (Filo), BarChart2 (Analitik), Settings (Sistem)

### `App.tsx`
- Yeni route'lar eklenir
- `path="/alerts"` → `<AlertsPage />` (artık `/trips` yönlendirmesi yok)
- `path="/monitoring"` → `<MonitoringPage />`
- `path="/predictions"` → `<PredictionsPage />`
- `path="/"` → `<DashboardPage />` (artık `/trips` yönlendirmesi yok)

---

## Yeni Sayfalar

### Dashboard `/`

**Endpoint'ler:**
- `GET /reports/dashboard` → KPI kartları
- `GET /reports/consumption-trend` → tüketim trend chart
- `GET /anomalies/fleet/insights` → anomali özeti widget
- `GET /predictions/comparison` → ML accuracy widget

**Layout:**
```
┌─ KPI Satırı (4 kart) ───────────────────────────────────────────┐
│  Aktif Sefer  │  Toplam Araç  │  Anomali (24h)  │  ML Acc. %   │
└─────────────────────────────────────────────────────────────────┘
┌─ Tüketim Trendi (Recharts LineChart) ──┐ ┌─ Anomali Özeti ───────┐
│  Son 12 ay, L/km aylık ortalama        │ │  Son 5 anomali listesi │
│  X: ay, Y: tüketim                     │ │  Araç, tip, önem badge │
└────────────────────────────────────────┘ └───────────────────────┘
┌─ Aktif Seferler Özeti ──────────────────────────────────────────┐
│  Tablo: son 5 sefer, araç plakası, sürücü, durum, rota          │
└─────────────────────────────────────────────────────────────────┘
```

**Dosyalar:**
- `pages/DashboardPage.tsx`
- `components/dashboard/KpiRow.tsx` — 4 KPI kartı
- `components/dashboard/ConsumptionChart.tsx` — Recharts LineChart
- `components/dashboard/AnomalyWidget.tsx` — son anomaliler listesi
- `components/dashboard/RecentTripsTable.tsx` — aktif seferler özeti

---

### Canlı Takip `/monitoring`

**Endpoint'ler:**
- `POST /ws/ticket` → kısa ömürlü WebSocket bileti alınır
- `ws://.../ws?ticket=<token>` → gerçek zamanlı mesaj akışı

**Davranış:**
- Sayfa açıldığında ticket alınır, WebSocket bağlantısı kurulur
- Bağlantı durum göstergesi: yeşil (bağlı) / sarı (yeniden bağlanıyor) / kırmızı (bağlantı yok)
- WebSocket mesajı geldiğinde ilgili sefer kartı güncellenir (React state)
- Bağlantı koptuğunda 3s backoff ile otomatik yeniden bağlanma (maks 5 deneme)
- Ticket süresi dolduğunda (`expires_in` ms sonra) yeni ticket alınır

**Layout:**
```
┌─ Bağlantı Durumu ──────────────────────────────────────────────┐
│  ● Bağlı — 12 aktif sefer izleniyor            [Yenile]        │
└─────────────────────────────────────────────────────────────────┘
┌─ Canlı Sefer Kartları (grid) ───────────────────────────────────┐
│  [34 ABC 567]  Ahmet Yılmaz  İstanbul→Ankara  120 km/h  Yolda  │
│  [12 DEF 890]  Mehmet Kaya   Ankara→İzmir     0 km/h    Mola   │
│  ...                                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Not:** WebSocket mesaj formatı implementation başında `app/api/v1/endpoints/admin_ws.py` incelenerek netleştirilmeli. Mesaj yapısı bilinmeden `LiveTripCard` props'ları tanımlanamaz.

**Dosyalar:**
- `pages/MonitoringPage.tsx`
- `components/monitoring/useMonitoringSocket.ts` — WebSocket hook (ticket yönetimi + reconnect)
- `components/monitoring/LiveTripCard.tsx` — tek sefer kartı, real-time güncellemeli
- `components/monitoring/ConnectionStatus.tsx` — bağlantı göstergesi

---

### Anomaliler `/alerts`

**Endpoint'ler:**
- `GET /anomalies/fleet/insights` → tüm veriler

**Layout:**
```
┌─ Fleet Health Özeti (3 kart) ──────────────────────────────────┐
│  Toplam Anomali  │  Ortalama Sapma  │  Kritik Uyarı Sayısı     │
└─────────────────────────────────────────────────────────────────┘
┌─ Filtreler ────────────────────────────────────────────────────┐
│  [Tümü] [Kritik] [Uyarı] [Bilgi]       Tarih aralığı seç      │
└─────────────────────────────────────────────────────────────────┘
┌─ Anomali Tablosu ───────────────────────────────────────────────┐
│  Tarih │ Araç │ Sürücü │ Tip │ Şiddet (Badge) │ Açıklama       │
└─────────────────────────────────────────────────────────────────┘
```

**Dosyalar:**
- `pages/AlertsPage.tsx`
- `components/alerts/AnomalyTable.tsx` — filtrelenebilir tablo
- `components/alerts/SeverityFilter.tsx` — severity tab bar

---

### ML Tahminler `/predictions`

**Endpoint'ler:**
- `GET /predictions/ensemble/status` → model ağırlıkları
- `GET /predictions/comparison?days=30` → gerçek vs tahmin
- `GET /predictions/time-series/trend` → zaman serisi trend
- `POST /predictions/explain` → XAI açıklama

**Layout:**
```
┌─ Ensemble Durum ─────────────────┐  ┌─ Gerçek vs Tahmin ────────────┐
│  Bar chart: model ağırlıkları     │  │  Recharts AreaChart            │
│  physics/lgbm/xgboost/gb/rf      │  │  Son 30 gün, L karşılaştırma   │
│  MAE, RMSE metrik kartları       │  │  İki çizgi: gerçek + tahmin    │
└───────────────────────────────────┘  └───────────────────────────────┘
┌─ XAI Açıklama Paneli ──────────────────────────────────────────────┐
│  Araç seç  |  Mesafe (km)  |  Yük (ton)  |  [Tahmin Et + Açıkla]  │
│  ──────────────────────────────────────────────────────────────    │
│  Tahmin: 28.4 L/100km                                              │
│  Etki faktörleri: Araç yaşı %35 | Yük %28 | Mesafe %22 | ...     │
└────────────────────────────────────────────────────────────────────┘
```

**Dosyalar:**
- `pages/PredictionsPage.tsx`
- `components/predictions/EnsembleStatusCard.tsx` — model ağırlıkları bar chart
- `components/predictions/AccuracyChart.tsx` — gerçek vs tahmin AreaChart
- `components/predictions/XaiPanel.tsx` — açıklama form + sonuç
- `components/predictions/MetricCards.tsx` — MAE, RMSE, accuracy kartları

---

## Mevcut Sayfalar — Derinleştirme

### Seferler `/trips`
- Aktif seferlerde WebSocket üzerinden canlı durum göstergesi (yeşil nokta animasyonu)
- Monitoring sayfasına "Canlı İzle" bağlantısı

### Yakıt `/fuel`
- Sayfanın üstüne tüketim trend chart eklenir (Recharts LineChart, 30 gün)
- Anomali flagleme: fleet insights'tan gelen araçlar kırmızı border ile işaretlenir

### Raporlar `/reports`
- Maliyet dönem kırılımı: pasta grafik (PieChart) → mevcut ROI hesaplama yanına
- Araç karşılaştırma: çubuk grafik (BarChart) → `GET /advanced-reports/cost/vehicle-comparison`
- Liste tabanlı görünüm kaldırılmaz, ama grafik tab önce gelir

### Admin Genel Bakış `/admin`
- Consumption trend: metin listesi → Recharts LineChart (mevcut veri aynı, görselleştirme değişir)
- "Elite Zen" veya benzeri süslü metin başlıklarda temizlenir

---

## Tasarım Dili

| Unsur | Kural |
|-------|-------|
| Renk semantiği | Mavi=bilgi, Yeşil=normal/başarı, Sarı=uyarı, Kırmızı=kritik |
| Grafik kütüphanesi | Recharts (zaten kurulu) |
| Animasyon | Framer Motion (mevcut kullanım devam eder) |
| Glassmorphism | Sadece sidebar ve modal'da kalır, kart içlerde kaldırılır |
| Branding | "LojiNext" — "Elite Zen" ve benzeri ek etiketler kaldırılır |
| Kart başlıkları | `text-sm font-semibold text-primary` — `tracking-[0.2em] uppercase` abartısı azaltılır |

---

## Kapsam Dışı

- Backend değişikliği yok
- Yeni API endpoint yazılmaz; mevcut endpoint'ler kullanılır
- Mobil responsive iyileştirme (mevcut yapı korunur)
- E2E test (Playwright) — mevcut testler korunur, yeni sayfalara birim test yeterlı
- `/admin/konfig`, `/admin/bakim`, `/admin/veri`, `/admin/kullanicilar` sayfaları derinleştirilmez

---

## Test Stratejisi

- Yeni her sayfa için `__tests__/` altında temel smoke test (render + API mock)
- Mevcut testler bozulmaz; mevcut mock yapısı korunur
- WebSocket hook için: `ws://` mock ile birim test (`useMonitoringSocket.test.ts`)
