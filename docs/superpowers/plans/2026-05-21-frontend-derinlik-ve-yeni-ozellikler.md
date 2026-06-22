# LojiNext — Frontend Derinlik Tamamlama + Yeni Ürün Özellikleri

> **Agentic worker için:** Bu plan iki fazdan oluşur. Faz 1 reaktif (backend boşlukları + bug fix), Faz 2 proaktif (yeni özellik geliştirme). Her görev `- [ ]` checkbox ile izlenir. Bir görevi başlatmadan önce ilgili dosyaları okuyarak `Pre-conditions` bölümündeki varsayımları doğrula.

**Amaç:** LojiNext frontend'inin backend ile derin entegrasyonunu tamamlamak ve filo yönetiminde gerçek değer üreten 12 yeni özellik eklemek.

**Mimari:** Mevcut FastAPI + React TS yapısı korunur. Yeni özellikler için ek backend endpoint/repo metodu eklenebilir; ML/AI iş yükü RAG (Groq LLM) ve mevcut ensemble üzerinde inşa edilir.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Celery, Redis, React 18, TanStack Query, Recharts, Framer Motion, sentence-transformers/FAISS, Groq LLM, Telegram Bot API.

**Toplam Tahmini Süre:** Faz 1 ≈ 16 saat · Faz 2 ≈ 60-80 saat

---

## 0 — Genel Verifikasyon (plan öncesi audit)

| Konu | Durum | Kanıt |
|------|-------|-------|
| `DashboardStatsResponse` schema vs implementation | **CONFIRMED BUG** | `reports.py:71-77` sadece 5/8 alan dolduruyor; `aktif_arac/aktif_sofor/bugun_sefer/trends` default `0` |
| `MeResponseSchema` Zod beklenen alan | **FIXED IN PRIOR SESSION** | `services.ts:48` — `kullanici_adi` → `email` (commit `2ef72bb3`) |
| `useMonitoringSocket` ping keepalive | **FIXED IN PRIOR SESSION** | commit `5d04e153` |
| `/admin/notifications/my` kullanımı | **FIXED IN PRIOR SESSION** | NotificationsTab (commit `5d04e153`) |
| `predictionService.getComparison(arac_id)` filtre | **CONFIRMED MISSING** | `predictions.py:128` `arac_id` Query param yok |
| `/trips/today` frontend kullanımı | **CONFIRMED MISSING** | DashboardPage ve TripsPage hiç çağırmıyor |
| `/anomalies/{id}/acknowledge` / `/resolve` | **CONFIRMED MISSING** | Sadece `GET` ve `/fleet/insights` var |
| `OCR servisi` (telegram_bot/ocr_service) | **STANDALONE** | docker-compose'da var, frontend entegrasyonu yok |
| RAG (smart_ai_service) | **CONFIRMED IDLE** | Mevcut, frontend'de "AI sohbet" panelinde sınırlı kullanılıyor |

---

# 🔧 FAZ 1 — Backend Boşluk Doldurma + Bug Fixes (~16 saat)

## Faz 1 File Map

| Action | File | Görev |
|--------|------|-------|
| Modify | `app/api/v1/endpoints/reports.py:53-86` | T1.1 — Dashboard stats eksik alanları doldur |
| Modify | `app/database/repositories/arac_repo.py` | T1.1 — `count_active()` ekle |
| Modify | `app/database/repositories/sefer_repo.py` | T1.1 — `count_today()` ekle |
| Modify | `app/database/repositories/analiz_repo.py` | T1.1 — `get_month_over_month_trends()` ekle |
| Create | `app/tests/integration/test_dashboard_stats.py` | T1.1 — Test |
| Modify | `frontend/src/pages/DashboardPage.tsx` | T1.2 — Trend rozetleri, today widget |
| Create | `frontend/src/components/dashboard/TodaysActiveTrips.tsx` | T1.2 |
| Create | `frontend/src/components/dashboard/KpiTrendBadge.tsx` | T1.2 |
| Modify | `app/api/v1/endpoints/predictions.py:128` | T2.1 — `arac_id` param ekle `/comparison`'a |
| Modify | `frontend/src/services/api/prediction-service.ts` | T2.1 — `getComparison(days, arac_id?)` |
| Modify | `frontend/src/components/fuel/ComparisonWidget.tsx` | T2.1 — Vehicle dropdown |
| Modify | `frontend/src/components/fuel/FuelStats.tsx` | T2.2 — 4→6 kart |
| Create | `frontend/src/components/fuel/FuelAnomalyWidget.tsx` | T2.3 |
| Create | `frontend/src/components/fuel/CostTrendChart.tsx` | T2.4 |
| Modify | `frontend/src/pages/FuelPage.tsx` | T2.x — Widget yerleştirme |
| Create | `frontend/src/components/drivers/DriverFilters.tsx` | T3.1 |
| Create | `frontend/src/components/drivers/DriversHeader.tsx` | T3.2 |
| Modify | `frontend/src/components/modules/DriversModule.tsx` | T3.1-3.4 |
| Create | `frontend/src/components/drivers/DriverScoreBreakdown.tsx` | T3.3 |
| Create | `frontend/src/components/drivers/DriverRouteProfile.tsx` | T3.4 |
| Modify | `frontend/src/services/api/driver-service.ts` | T3.5 |
| Create | `frontend/src/components/predictions/PredictionSimulator.tsx` | T4.1 |
| Create | `frontend/src/components/predictions/TimeSeriesForecast.tsx` | T4.2 |
| Modify | `frontend/src/pages/PredictionsPage.tsx` | T4.x — 3 sekmeli |
| Modify | `frontend/src/pages/ReportsPage.tsx` | T5.x — Tasarruf potansiyeli, period cost |
| Create | `frontend/src/components/reports/SavingsPotentialCard.tsx` | T5.1 |
| Create | `frontend/src/components/reports/PeriodCostBreakdown.tsx` | T5.2 |
| Modify | `app/api/v1/endpoints/anomalies.py` | T7.1 — acknowledge/resolve POST |
| Modify | `app/database/models.py` | T7.1 — Anomali alanları (varsa) |
| Modify | `frontend/src/pages/AlertsPage.tsx` | T7.x |
| Create | `frontend/src/components/trips/TripsTodaySummary.tsx` | T6.1 |
| Create | `frontend/src/components/trips/TripCostAnalysisTab.tsx` | T6.2 |
| Create | `frontend/src/components/vehicles/VehiclesHeader.tsx` | T8.1 |
| Create | `frontend/src/components/vehicles/InspectionAlertModal.tsx` | T8.2 |
| Create | `frontend/src/components/locations/CalibrationModal.tsx` | T9.1 |

---

## Task 1.1 — DashboardPage Backend Düzeltmesi

**Files:**
- Modify: `app/api/v1/endpoints/reports.py:53-86`
- Modify: `app/database/repositories/arac_repo.py`
- Modify: `app/database/repositories/sefer_repo.py`
- Modify: `app/database/repositories/analiz_repo.py`
- Create: `app/tests/integration/test_dashboard_stats.py`

**Pre-conditions (verify before coding):**
- `reports.py:71-77`'de `DashboardStatsResponse(...)` çağrısında sadece `toplam_sefer`, `toplam_km`, `toplam_yakit`, `filo_ortalama`, `toplam_arac` dolduruluyor.
- `arac_repo` içinde `count_active()` benzeri metod **yok** (`grep -n "count_active\|count_all" app/database/repositories/arac_repo.py` ile doğrula).
- `sefer_repo` içinde `count_today()` metodu **yok**.
- `analiz_repo` içinde month-over-month trend metodu **yok**.

**Implementation:**

- [ ] Adım 1: `arac_repo.count_active()` ekle — `SELECT COUNT(*) FROM araclar WHERE aktif = TRUE`
- [ ] Adım 2: `sefer_repo.count_today()` ekle — `SELECT COUNT(*) FROM seferler WHERE tarih = CURRENT_DATE`
- [ ] Adım 3: `analiz_repo.get_month_over_month_trends()` ekle. Bu ayın ve önceki ayın `(sefer_count, total_km, avg_consumption)` değerlerini hesapla, % delta dön:
  ```python
  return {
      "sefer": ((curr_sefer - prev_sefer) / prev_sefer * 100) if prev_sefer else 0,
      "km": ((curr_km - prev_km) / prev_km * 100) if prev_km else 0,
      "tuketim": ((curr_avg - prev_avg) / prev_avg * 100) if prev_avg else 0,
  }
  ```
- [ ] Adım 4: `reports.py:get_dashboard_stats`'ı yeniden yaz. `service.generate_fleet_summary()` sonrası eksik alanları paralel `asyncio.gather` ile çek:
  ```python
  aktif_arac, aktif_sofor, bugun_sefer, trends = await asyncio.gather(
      arac_repo.count_active(),
      sofor_repo.count_active(),
      sefer_repo.count_today(),
      analiz_repo.get_month_over_month_trends(),
  )
  return DashboardStatsResponse(
      toplam_sefer=data.get("total_trips", 0),
      ...mevcut alanlar...,
      aktif_arac=aktif_arac,
      aktif_sofor=aktif_sofor,
      bugun_sefer=bugun_sefer,
      trends=DashboardTrends(**trends),
  )
  ```
- [ ] Adım 5: Integration test yaz: `test_dashboard_stats.py` — 1 araç + 1 şoför + 1 bugünkü sefer ile fixture oluştur, endpoint çağır, tüm alanların >0 döndüğünü doğrula.

**Acceptance Criteria:**
- `GET /api/v1/reports/dashboard` yanıtında `aktif_arac`, `aktif_sofor`, `bugun_sefer`, `trends.sefer/km/tuketim` artık **0 olmayan** anlamlı değerler döner (test verisi varsa).
- Mevcut testler (181) hâlâ geçiyor.

**Verification:**
```bash
cd D:/PROJECT/LOJINEXT
pytest app/tests/integration/test_dashboard_stats.py -v
pytest -m "unit or not integration" --cov=app.api.v1.endpoints.reports --cov-fail-under=70
```

---

## Task 1.2 — DashboardPage Frontend Genişletme

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/components/dashboard/KpiRow.tsx`
- Create: `frontend/src/components/dashboard/KpiTrendBadge.tsx`
- Create: `frontend/src/components/dashboard/TodaysActiveTrips.tsx`
- Modify: `frontend/src/types/index.ts` (gerekirse `DashboardStats` zaten doğru)

**Pre-conditions:**
- Task 1.1 tamamlanmış olmalı (backend artık `aktif_arac`, `bugun_sefer`, `trends` dönüyor).
- `frontend/src/types/index.ts:248-263` `DashboardStats` interface'i tüm alanları zaten içeriyor (verified).

**Implementation:**

- [ ] Adım 1: `KpiTrendBadge` bileşeni — `+%3.2 bu ay` / `-%1.8 bu ay` rozeti. Pozitif/negatif renk kodu.
- [ ] Adım 2: `KpiRow` props'una `trend?: number` ekle, varsa `KpiTrendBadge` göster.
- [ ] Adım 3: `DashboardPage.tsx` `kpiItems` array'ini güncelle:
  - "Toplam Sefer" → `trend: stats?.trends?.sefer`
  - "Aktif Araç" → bu kalsın
  - **YENİ:** "Bugün" → `value: stats?.bugun_sefer`, `trend: stats?.trends?.sefer`
  - "Yoldaki Sefer" → bu kalsın
  - "ML Doğruluk" → bu kalsın
- [ ] Adım 4: `TodaysActiveTrips` widget — `useQuery(['trips','today'], () => tripService.getAll({ tarih: today }))`. Max 5 satır, "Tümünü Gör" → TripsPage filtered link.
- [ ] Adım 5: AnomalyWidget'ı tıklanabilir yap → `useNavigate('/alerts?days=30')`.
- [ ] Adım 6: `staleTime` 2 dakikadan 60 saniyeye düşür, `refetchOnWindowFocus: true` ekle.

**Acceptance Criteria:**
- Dashboard'da "Bugün X sefer" görünüyor (sıfır olsa bile).
- Trend rozetleri görünür.
- TodaysActiveTrips widget'ı 5 sefer listeliyor (varsa).

**Verification:**
```bash
cd D:/PROJECT/LOJINEXT/frontend
npx tsc --noEmit | grep -v "TS6133\|node_modules"
npx vitest --run src/components/dashboard
npx vite build
```

---

## Task 2.1 — FuelPage `ComparisonWidget` Araç Filtresi (Bug Fix)

**Files:**
- Modify: `app/api/v1/endpoints/predictions.py:128-150`
- Modify: `app/schemas/prediction.py` (varsa PredictionComparisonResponse)
- Modify: `frontend/src/services/api/prediction-service.ts`
- Modify: `frontend/src/components/fuel/ComparisonWidget.tsx`

**Pre-conditions:**
- `/predictions/comparison` şu an `arac_id` query param **almıyor** (`predictions.py:128`).
- ComparisonWidget herhangi bir araç filtrelemesi yapmıyor → global rakam görünüyor.

**Implementation:**

- [ ] Adım 1: `predictions.py:128 get_prediction_comparison` fonksiyonuna `arac_id: Optional[int] = Query(None)` parametresi ekle. Sorguda `if arac_id: query = query.where(Sefer.arac_id == arac_id)`.
- [ ] Adım 2: `prediction-service.ts` `getComparison(days: number, aracId?: number)` imzasını güncelle.
- [ ] Adım 3: `ComparisonWidget`'a vehicle dropdown ekle (vehicles prop'u veya `useQuery(['vehicles','minimal'])`). Seçilen araca göre `getComparison(30, vehicleId)`.

**Acceptance Criteria:**
- ComparisonWidget'ta araç seçilebiliyor, seçim değiştiğinde data refresh oluyor.
- "Tüm Filo" seçeneği global rakamı gösteriyor.

---

## Task 2.2 — FuelStats 4→6 Kart Genişletme

**Files:**
- Modify: `frontend/src/components/fuel/FuelStats.tsx`
- Modify: `frontend/src/types/index.ts` (FuelStats interface'i `total_distance` alanını içeriyor mu doğrula, yoksa ekle)
- Modify: `frontend/src/resources/tr/fuel.ts` (yeni etiket çevirileri)

**Pre-conditions:**
- Backend `yakit_repo.get_stats` (line 297-303) `total_distance` dönüyor — frontend göstermiyor.
- `FuelStatsResponse` schema'da `extra="allow"` — yeni alanlar kabul ediliyor.

**Implementation:**

- [ ] Adım 1: `FuelStats.tsx` `items` array'ine 5. ve 6. kartı ekle:
  - "Toplam Mesafe" (`stats?.total_distance` km)
  - "Yakıt Anomalisi" (`useAnomalyCount('tuketim', 30)` hook'tan)
- [ ] Adım 2: Grid `lg:grid-cols-4` → `lg:grid-cols-6`.
- [ ] Adım 3: Çeviriler `fuelStatsText` resource'una ekle.

---

## Task 2.3 — Fuel Anomaly Widget

**Files:**
- Create: `frontend/src/components/fuel/FuelAnomalyWidget.tsx`
- Modify: `frontend/src/pages/FuelPage.tsx`

**Implementation:**

- [ ] Adım 1: `useQuery` ile `/anomalies/?tip=tuketim&days=30&limit=5` çağır.
- [ ] Adım 2: Mini liste — her satır: plaka, şoför, sapma %, tarih.
- [ ] Adım 3: "Tüm Anomaliler" linki → AlertsPage filtered.
- [ ] Adım 4: FuelPage'in altına yerleştir (stats ve trend grafiklerinden sonra).

---

## Task 2.4 — Maliyet Trend Grafiği

**Files:**
- Create: `frontend/src/components/fuel/CostTrendChart.tsx`
- Modify: `frontend/src/pages/FuelPage.tsx`

**Implementation:**

- [ ] Adım 1: `reportService.getConsumptionTrend()` çağrısı + birim fiyat trend hesabı (mevcut trend × ortalama TL/L).
- [ ] Adım 2: Dual-axis LineChart: sol Y = Litre, sağ Y = TL/Litre.
- [ ] Adım 3: Mevcut tüketim trend grafiğinin yanına yerleştir (2-column grid).

---

## Task 3 Serisi — DriversPage Genişletme

### Task 3.1 — DriverFilters
**Files:**
- Create: `frontend/src/components/drivers/DriverFilters.tsx`
- Modify: `frontend/src/components/modules/DriversModule.tsx`

- [ ] Search input (debounced 300ms) → `search` query
- [ ] Ehliyet sınıfı select (B/C/D/E/CE/D1E) → `ehliyet_sinifi`
- [ ] Min/Max score range slider (0.1-2.0) → `min_score`, `max_score`
- [ ] Aktif/Pasif toggle

### Task 3.2 — DriversHeader (Import/Export)
**Files:**
- Create: `frontend/src/components/drivers/DriversHeader.tsx`

- [ ] FuelHeader paterni: "Şoför Ekle", "Excel İndir", "Şablon İndir", "Excel Yükle"
- [ ] Service çağrıları: `driverService.exportExcel(filters)`, `downloadTemplate()`, `uploadExcel(file)` — Faz 3.5'te eklenecek

### Task 3.3 — DriverScoreBreakdown (XAI)
**Files:**
- Create: `frontend/src/components/drivers/DriverScoreBreakdown.tsx`
- Modify: `frontend/src/components/drivers/DriverPerformanceModal.tsx`

- [ ] DriverPerformanceModal'a yeni sekme "Skor Detayı"
- [ ] `calculate_hybrid_score` formülünün görsel kırılımı:
  ```
  Manuel Puan:    1.20 × 0.4 = 0.48
  Otomatik Puan:  1.08 × 0.6 = 0.65 (12 sefer)
  ─────────────────────────────
  TOPLAM:                     1.13
  ```
- [ ] Backend desteği gerekir — `sofor_service.get_score_breakdown(sofor_id)` ekle, response = `{manual, manual_weight, auto, auto_weight, total, trip_count}`

### Task 3.4 — DriverRouteProfile
**Files:**
- Create: `frontend/src/components/drivers/DriverRouteProfile.tsx`
- Modify: `frontend/src/components/drivers/DriverPerformanceModal.tsx`

- [ ] Backend'de `app/core/ml/driver_route_profile.py` v5 commit'inde implement edilmiş — bağlan
- [ ] Yeni endpoint: `GET /drivers/{id}/route-profile` (eklenecek)
- [ ] Frontend: güzergah tipi × L/100km × sapma % bar chart
- [ ] "Bu şoförün en güçlü olduğu güzergah tipi: Uzun Yol Düz"

### Task 3.5 — driver-service eksik metodlar
**Files:**
- Modify: `frontend/src/services/api/driver-service.ts`

- [ ] `bulkDelete(ids: number[])` — `DELETE /drivers/bulk`
- [ ] `exportExcel(filters)` — `GET /drivers/excel/export`
- [ ] `downloadTemplate()` — `GET /drivers/excel/template`
- [ ] `uploadExcel(file: File)` — `POST /drivers/excel/upload`
- [ ] `getRouteProfile(id: number)` — `GET /drivers/{id}/route-profile`

---

## Task 4 Serisi — PredictionsPage 3 Sekmeli Yapı

### Task 4.1 — Sefer Simülasyon Sekmesi
**Files:**
- Create: `frontend/src/components/predictions/PredictionSimulator.tsx`
- Create: `frontend/src/components/predictions/PredictionResult.tsx`
- Create: `frontend/src/components/predictions/XaiExplainPanel.tsx` (interactive)
- Modify: `frontend/src/services/api/prediction-service.ts`

- [ ] Form: araç, mesafe, ton, ascent_m, descent_m, flat_distance_km, şoför, zorluk
- [ ] "Tahmini Hesapla" → `POST /predictions/predict`
- [ ] Sonuç kartı: tahmini L, maliyet projeksiyonu, %güven
- [ ] "Açıkla" butonu → `POST /predictions/explain` → feature importance bar chart

### Task 4.2 — Zaman Serisi Sekmesi
**Files:**
- Create: `frontend/src/components/predictions/TimeSeriesForecast.tsx`
- Create: `frontend/src/components/predictions/TimeSeriesStatusCard.tsx`

- [ ] Üst: `/time-series/status` çağır, model durumu göster
- [ ] Orta: Araç seçici + "Haftalık Tahmin" → `POST /time-series/forecast` line chart with confidence band
- [ ] Alt: `/time-series/trend` — son 30 günün trend yönü + yorumla

### Task 4.3 — PredictionsPage 3 Sekme
**Files:**
- Modify: `frontend/src/pages/PredictionsPage.tsx`

- [ ] Tab bar: Genel Bakış / Sefer Simülasyonu / Zaman Serisi (MonitoringPage tab patternine bak)
- [ ] Mevcut içerik "Genel Bakış" tabına taşı

---

## Task 5 Serisi — ReportsPage Tasarruf + Period Cost

### Task 5.1 — SavingsPotentialCard
**Files:**
- Create: `frontend/src/components/reports/SavingsPotentialCard.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx`

- [ ] `useQuery(['savings-potential', target], () => reportsApi.getSavingsPotential(target))`
- [ ] Target consumption slider (20-45 L/100km, default 30)
- [ ] Görüntülenen: `potential_savings`, `annual_projection`, `savings_percentage`
- [ ] Cost sekmesine yerleştir

### Task 5.2 — PeriodCostBreakdown
**Files:**
- Create: `frontend/src/components/reports/PeriodCostBreakdown.tsx`

- [ ] Date range picker
- [ ] `/cost/period?start_date=X&end_date=Y` çağrısı
- [ ] KPI kartları: `cost_per_km`, `avg_price_per_liter`, `trip_count`, `total_distance`, `fuel_cost`

### Task 5.3 — Vehicle Cost Drill-down
**Files:**
- Modify: `frontend/src/pages/ReportsPage.tsx` (vehicle tab)

- [ ] BarChart barına tıklanınca modal → `/cost/period?arac_id=X` detayı

---

## Task 6 Serisi — TripsPage Detay

### Task 6.1 — TripsTodaySummary
**Files:**
- Create: `frontend/src/components/trips/TripsTodaySummary.tsx`

- [ ] `tripService.getStats({ baslangic_tarih: today, bitis_tarih: today })`
- [ ] Üst banner: "Bugün 12 sefer (8 devam ediyor, 4 tamamlandı)"

### Task 6.2 — Cost Analysis Modal/Tab
**Files:**
- Create: `frontend/src/components/trips/TripCostAnalysisTab.tsx`
- Modify: Sefer detay görünümü

- [ ] `POST /trips/{id}/cost-analysis` — async (status 202), `task_id` döner
- [ ] `useTaskStatus(task_id)` hook ile polling
- [ ] Sonuç: yakıt maliyeti, sürücü payı, amortisman, toplam

### Task 6.3 — Import Progress Modal
**Files:**
- Create: `frontend/src/components/trips/ImportProgressModal.tsx`
- Create: `frontend/src/hooks/useTaskStatus.ts`

- [ ] Excel upload sonrası `task_id` ile progress modal
- [ ] Backend'de `task_id` dönmüyor şu an — `trips.py:upload` revize edilmeli

---

## Task 7 Serisi — AlertsPage Acknowledge/Resolve

### Task 7.1 — Backend Anomali Aksiyonları
**Files:**
- Modify: `app/api/v1/endpoints/anomalies.py`
- Modify: `app/database/models.py` (Anomali model `acknowledged_at`, `acknowledged_by`, `resolved_at`, `resolved_by`, `resolution_notes` alanları)
- Migration: `alembic revision --autogenerate -m "anomaly_action_fields"`

- [ ] `POST /anomalies/{id}/acknowledge` — `acknowledged_at`, `acknowledged_by` doldur
- [ ] `POST /anomalies/{id}/resolve` — body: `{notes: string}`, `resolved_at`, `resolved_by`, `resolution_notes`
- [ ] `GET /anomalies/?status=open|acknowledged|resolved` filtresi

### Task 7.2 — AlertsPage Aksiyonlar
**Files:**
- Modify: `frontend/src/pages/AlertsPage.tsx`
- Modify: `frontend/src/services/api/anomaly-service.ts`

- [ ] Her anomali satırında "Onayla" ve "Çöz" butonları
- [ ] "Çöz" → modal: not yaz + onayla
- [ ] Filtre sekmesi: Açık / Onaylanmış / Çözülmüş

### Task 7.3 — Anomali Tipi Filtresi
- [ ] severity yanına tip dropdown (tuketim/maliyet/sefer)

---

## Task 8 — FleetPage Genişletme

### Task 8.1 — VehiclesHeader (Import/Export)
**Files:**
- Create: `frontend/src/components/vehicles/VehiclesHeader.tsx`
- Modify: `frontend/src/components/modules/VehiclesModule.tsx`

- [ ] FuelHeader paterni — Add/Export/Template/Import

### Task 8.2 — InspectionAlertModal
**Files:**
- Create: `frontend/src/components/vehicles/InspectionAlertModal.tsx`
- Modify: `frontend/src/components/fleet/FleetInsights.tsx`

- [ ] FleetInsights'taki "muayene uyarı" kartı tıklanabilir
- [ ] Modal: muayenesi yaklaşan/geçmiş araç listesi
- [ ] Backend'de filter parametresi gerekirse: `vehicleService.getAll({ inspection_within_days: 30 })`

---

## Task 9 — LocationsPage Kalibrasyon

### Task 9.1 — CalibrationModal
**Files:**
- Create: `frontend/src/components/locations/CalibrationModal.tsx`
- Modify: `frontend/src/components/locations/RouteAnalysisCard.tsx`

- [ ] "Bu Lokasyona Sefer Kalibre Et" butonu
- [ ] Trip ID seç → `POST /admin/calibration/calibrate?trip_id=X`

### Task 9.2 — Fuel Estimate Tooltip
- [ ] info ikonu + hover tooltip: "mesafe × araç ort. tüketim × yük katsayısı"

---

# 🚀 FAZ 2 — Yeni Ürün Özellikleri (~60-80 saat)

> **Agent için not:** Faz 2 özellikleri büyük ölçekli — her özellik için önce mini-plan çıkarılması ve PR'a bölünmesi gerekir. Aşağıdaki başlıklar yüksek seviyeli mimari; her birinin detaylandırılması ayrı çalışma seansı gerektirir.

## Feature A — Şoför Koçluk Modülü ⭐ (en yüksek değer)

**İş Problemi:** Şoförler anomali yapıyor ama "neyi yanlış yaptım?" geribildirimi alamıyor. Skorları düşüyor ama nedenini bilmiyorlar.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ai/driver_coaching_engine.py` (NEW) — RAG + LLM ile şoför × anomali kümeleri analiz eder
  - `GET /drivers/{id}/coaching-insights` — son 30 günde N anomali → kategorize edilmiş öneriler
  - `POST /drivers/{id}/send-coaching` — Telegram bot üzerinden mesaj gönder
  - Celery task: günlük/haftalık skor değişimi → otomatik koçluk
- **Frontend:**
  - Yeni sayfa: `/coaching` (sidebar'a ekle)
  - Şoför listesi + skor trendi + son aksiyonlar
  - Her şoför için: tespit edilen pattern'ler ("tepe sürüşlerinde vites kullanımı"), önerilen koçluk mesajları
  - "Telegram'dan Gönder" butonu (manuel onay flow)
- **Telegram Bot:**
  - `telegram_bot/driver_bot.py`'a koçluk komut handler ekle
  - Şoför `/score` ile kendi skorunu görür
  - Otomatik haftalık özet: "Bu hafta verimliliğin %3 azaldı, en çok zayıfladığın güzergah X"

**Görevler:**
- [ ] A.1 — Coaching engine (LLM prompt mühendisliği)
- [ ] A.2 — Backend endpoints + Celery task
- [ ] A.3 — Frontend sayfa
- [ ] A.4 — Telegram bot komutları
- [ ] A.5 — A/B test infra (gönderilen mesaj → 2 hafta sonra skor delta ölç)

**Tahmini Süre:** 12-15 saat

---

## Feature B — Yakıt Hırsızlığı Tespit + Soruşturma Akışı ⭐

**İş Problemi:** Yakıt anomalileri tespit ediliyor (kaçak L > 0) ama "ne yapacağım?" yok. Filo yöneticisi her anomaliyi tek tek değerlendirmek zorunda.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ai/fuel_theft_classifier.py` (NEW) — anomali metadata + pattern analizi → "yüksek/orta/düşük şüphe" sınıflandırma
  - `app/database/models.py` — `FuelInvestigation` yeni tablo: `anomali_id`, `status`, `assigned_to`, `notes`, `resolution_type`, `evidence_files`
  - `/admin/investigations/*` CRUD endpoint'leri
  - Pattern detection: aynı şoför/araç/lokasyon kombinasyonu — `GET /investigations/patterns`
- **Frontend:**
  - AlertsPage'e "Soruşturmalar" sekmesi
  - Akış: Şüpheli → Atama (kime soruşturulacak) → Soruşturma (notlar, kanıt yükleme) → Çözüm (gerçek/sahte alarm/yanıltıcı veri)
  - Kanban benzeri görünüm
  - Pattern dashboard: heat-map (gün × şoför)
- **Bildirim:**
  - Yüksek şüphe → otomatik Telegram alarm (admin grup)

**Görevler:**
- [ ] B.1 — Theft classifier (ML/rule-based hybrid)
- [ ] B.2 — Investigation tablo + migration + CRUD
- [ ] B.3 — Pattern detection algorithm
- [ ] B.4 — Frontend Kanban + akış
- [ ] B.5 — Telegram alarm entegrasyonu

**Tahmini Süre:** 14-18 saat

---

## Feature C — Akıllı Sefer Planlama Sihirbazı ⭐

**İş Problemi:** Yeni sefer oluştururken yönetici manuel olarak araç + şoför seçiyor. AI önerisi yok.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ai/trip_planner.py` (NEW) — input: güzergah + tarih + yük; output: önerilen araç/şoför + maliyet/süre/risk tahmini
  - Karar mantığı:
    - Araç: geçmiş benzer güzergahlarda en verimli (route_similarity engine ile)
    - Şoför: güzergah tipinde en yüksek skor (driver_route_profile ile)
    - Hava: `/weather` endpoint sorgulanır, risk hesaplanır
  - `POST /trips/plan-wizard` — öneri payload'u döner
- **Frontend:**
  - TripFormModal'da yeni adım: "🪄 Akıllı Plan"
  - Güzergah girilince → 3 araç + 3 şoför önerisi (skor ile)
  - Her öneri için: tahmini L, maliyet, süre, risk skoru, açıklama
  - Kullanıcı seçer → form prefill

**Görevler:**
- [ ] C.1 — Trip planner backend logic (mevcut route_similarity + driver_route_profile birleştir)
- [ ] C.2 — Weather risk hesabı
- [ ] C.3 — `POST /trips/plan-wizard` endpoint
- [ ] C.4 — TripFormModal wizard step
- [ ] C.5 — XAI: "Neden bu araç önerildi?" gerekçe paneli

**Tahmini Süre:** 10-12 saat

---

## Feature D — Tahmine Dayalı Bakım Takvimi

**İş Problemi:** `/admin/maintenance` statik liste. ML kullanılmıyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ml/maintenance_predictor.py` (NEW) — kilometre artışı + tüketim trendi + yaş → tahmini bakım tarihi
  - `GET /admin/maintenance/predictions` — her araç için tahmini next maintenance date
  - `POST /admin/maintenance/{id}/schedule` — takvime ekle, .ics dosyası dön
- **Frontend:**
  - `BakimPage` yenileme: FullCalendar component
  - Her bakım: tahmini tarih, gerçek tarih (planlandığı zaman), durum
  - "Bu bakım yapılırsa %X yakıt tasarrufu" projeksiyonu

**Görevler:**
- [ ] D.1 — Maintenance ML predictor
- [ ] D.2 — Endpoints + .ics generator
- [ ] D.3 — Calendar UI

**Tahmini Süre:** 8-10 saat

---

## Feature E — Yönetici Paneli (Executive Dashboard)

**İş Problemi:** DashboardPage operasyonel. Yönetici stratejik veri istiyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `GET /reports/executive` — aylık/üç aylık/yıllık aggregat
  - What-if hesaplama: `POST /reports/what-if` — body: `{target_consumption, target_fleet_size, etc}`
  - Benchmarking: sektör ortalamaları (statik veya başka API)
  - Karbon ayak izi: `GET /reports/carbon-footprint`
- **Frontend:**
  - Yeni sayfa: `/executive` (sidebar — rol bazlı görünür)
  - 12 aylık trend grafikleri
  - What-if simulator (slider'larla)
  - Karbon raporu (regulasyon için)
  - PDF export

**Görevler:**
- [ ] E.1 — Executive aggregat endpoint
- [ ] E.2 — What-if scenario engine
- [ ] E.3 — Carbon footprint hesabı
- [ ] E.4 — Frontend executive page
- [ ] E.5 — PDF export

**Tahmini Süre:** 10-12 saat

---

## Feature F — Müşteri Bildirim Sistemi

**İş Problemi:** Müşteri kargosunun nerede olduğunu bilmiyor. Yönetici telefonla bilgi veriyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/database/models.py` — `Sefer.musteri_id`, `Sefer.musteri_iletisim` (telefon/email)
  - `app/core/services/customer_notification.py` (NEW) — SMS/email gönderim adaptörü
  - Sefer event'lerinde otomatik bildirim:
    - SEFER_STARTED → "Kargo yola çıktı, ETA: X"
    - SLA_DELAY → "Gecikme algılandı, yeni ETA: Y"
    - SEFER_COMPLETED → "Teslim edildi, teşekkürler"
  - `GET /public/tracking/{tracking_token}` — auth gerektirmeyen tracking
- **Frontend:**
  - Yeni public sayfa: `/track/{token}` — read-only tracking (harita, ETA, durum)
  - TripsPage'de "Tracking Link Üret" butonu

**Görevler:**
- [ ] F.1 — Customer model + Sefer ilişkisi
- [ ] F.2 — Notification adapter (Twilio/SendGrid)
- [ ] F.3 — Event listener'lar
- [ ] F.4 — Public tracking endpoint
- [ ] F.5 — Public tracking sayfası
- [ ] F.6 — TripsPage entegrasyonu

**Tahmini Süre:** 12-15 saat

---

## Feature G — Şoför PWA (Mobile-First)

**İş Problemi:** Şoförler sadece Telegram'da etkileşiyor. Görsel arayüz yok.

**Çözüm Mimarisi:**
- **Frontend:**
  - Yeni route: `/driver-portal` (auth: sadece driver rolü)
  - Mobile-first design (vite-pwa-plugin ile PWA)
  - Sayfalar:
    - Bugünkü sefer (planlanmış)
    - Geçmiş seferler + her birinin performans skoru
    - Skor trendi grafiği
    - Koçluk önerileri (Feature A'dan beslenir)
    - Yarışma/leaderboard (filo genel)
- **Backend:**
  - `GET /driver-portal/today` — sadece kendi seferleri
  - `GET /driver-portal/performance` — kendi skoru/trendi
  - `GET /driver-portal/leaderboard` — filo geneli (anonim olabilir)

**Görevler:**
- [ ] G.1 — PWA setup (vite-pwa-plugin, manifest)
- [ ] G.2 — Driver-only route guard
- [ ] G.3 — Backend driver-portal endpoints
- [ ] G.4 — Mobile UI bileşenleri

**Tahmini Süre:** 14-18 saat

---

## Feature H — Anomali Kümeleme (Pattern Detection)

**İş Problemi:** Anomaliler tek tek görünüyor — pattern'ler kaçıyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ml/anomaly_clustering.py` (NEW) — DBSCAN/HDBSCAN ile anomali gruplamayı çalıştır (Celery task, günde 1 kez)
  - Feature: (saat, gün, lokasyon, araç_yaşı, yük, hava) → cluster
  - `GET /anomalies/clusters` — listelenen pattern'ler
- **Frontend:**
  - AlertsPage'e "Pattern" sekmesi
  - Cluster özet kartları: "X anomalinin hepsi Cuma sabahları İstanbul→Ankara güzergahında" + LLM ile insight

**Görevler:**
- [ ] H.1 — Clustering algorithm
- [ ] H.2 — Celery task + DB store
- [ ] H.3 — LLM insight generator
- [ ] H.4 — Frontend pattern visualization

**Tahmini Süre:** 8-10 saat

---

## Feature I — Doğal Dil Sorgulama Paneli

**İş Problemi:** RAG var ama frontend'de AI sohbeti çok sınırlı.

**Çözüm Mimarisi:**
- **Backend:** Mevcut `smart_ai_service` zaten kullanılıyor ama frontend yeterince güçlü değil
- **Frontend:**
  - Mevcut AI panelini genişlet:
    - Sorgu kategorileri (filo / araç / şoför / yakıt / anomali)
    - "Bu hafta hangi araç en kötü performans gösterdi?" → cevap + otomatik grafik
    - Sözlü komut (Web Speech API)
    - Cevap-ile-aksiyon: AI cevabında link/buton ("Bu araca git", "Bu seferin detayı")

**Görevler:**
- [ ] I.1 — Query categorization
- [ ] I.2 — Auto-chart generation (LLM → chart JSON)
- [ ] I.3 — Web Speech API entegrasyonu
- [ ] I.4 — Aksiyon link parsing

**Tahmini Süre:** 8-10 saat

---

## Feature J — OCR ile Otomatik Belge İşleme

**İş Problemi:** `ocr_service/` standalone — frontend entegrasyonu yok.

**Çözüm Mimarisi:**
- **Backend:**
  - `GET /api/v1/documents/upload` — fiş/fatura yükle → OCR servisine yönlendir → yapılandırılmış veri dön
  - Otomatik yakıt kaydı oluşturma (kullanıcı onayı ile)
  - `Document` model + belge arşivi
- **Frontend:**
  - FuelPage'e "Belge Yükle" butonu — fotoğraf çek/yükle → OCR sonuç önizle → onayla → kayıt oluştur
  - Telegram bot: şoför fiş fotoğrafı çeker → OCR → sisteme düşer

**Görevler:**
- [ ] J.1 — OCR servisine REST bridge
- [ ] J.2 — Document model + arşiv
- [ ] J.3 — FuelPage upload UI
- [ ] J.4 — Telegram bot fotoğraf handler

**Tahmini Süre:** 10-12 saat

---

## Feature K — Insurance Risk Scoring API

**İş Problemi:** Sigorta şirketlerine manuel rapor gönderiliyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/services/insurance_risk.py` (NEW) — filo risk skoru hesabı
  - `GET /api/v1/insurance/risk-score` — API key auth (yeni `ApiKey` modeli)
  - Aylık otomatik PDF rapor (Celery beat)
- **Frontend:**
  - Admin sayfası: API key yönetimi, rapor geçmişi

**Görevler:**
- [ ] K.1 — Risk scoring algorithm
- [ ] K.2 — API key model + auth
- [ ] K.3 — Celery scheduled report
- [ ] K.4 — Admin UI

**Tahmini Süre:** 8-10 saat

---

## Feature L — Akıllı Bildirim Akışı

**İş Problemi:** Bildirimler statik — kullanıcı bildirim yorgunluğu yaşıyor.

**Çözüm Mimarisi:**
- **Backend:**
  - `app/core/ai/notification_prioritizer.py` (NEW) — kullanıcının geçmiş aksiyonlarına göre önemli/önemsiz sınıflandır
  - Akıllı zamanlama: kullanıcının aktif olduğu saatleri öğren, kritik olmayanları o zamana bekle
  - "Bu hafta dikkat etmen gereken 3 şey" özet bildirimi (haftalık digest)
- **Frontend:**
  - NotificationsTab'a "Önem" sıralaması toggle
  - Bildirim ayarları sayfası (sessize alma zamanları)

**Görevler:**
- [ ] L.1 — Prioritization model
- [ ] L.2 — User activity learning
- [ ] L.3 — Weekly digest builder
- [ ] L.4 — Settings UI

**Tahmini Süre:** 8-10 saat

---

# 📋 Önerilen Uygulama Sırası

```
SPRINT 1 (Hafta 1-2): Faz 1 Kritik (DashboardPage bug, FuelPage bug)
  - Task 1.1, 1.2, 2.1, 2.2, 2.3, 2.4

SPRINT 2 (Hafta 3): Faz 1 Major (DriversPage, PredictionsPage)
  - Task 3.x, 4.x

SPRINT 3 (Hafta 4): Faz 1 Polish (ReportsPage, TripsPage, AlertsPage, FleetPage, LocationsPage)
  - Task 5.x, 6.x, 7.x, 8.x, 9.x

SPRINT 4-5 (Hafta 5-6): Feature A (Şoför Koçluk) + Feature B (Hırsızlık Tespit)
  - En yüksek değer üreten özellikler

SPRINT 6 (Hafta 7): Feature C (Akıllı Planlama) + Feature D (Tahmine Dayalı Bakım)

SPRINT 7 (Hafta 8): Feature E (Executive) + Feature H (Anomali Kümeleme)

SPRINT 8 (Hafta 9): Feature F (Müşteri Bildirim) + Feature J (OCR)

SPRINT 9 (Hafta 10): Feature G (Şoför PWA)

SPRINT 10 (Hafta 11): Feature I (AI Sorgulama) + Feature L (Akıllı Bildirim)

BACKLOG: Feature K (Insurance API)
```

---

# 🔒 Kabul Kriterleri (Genel)

Her görev için zorunlu:
- [ ] `npx tsc --noEmit` 0 hata (yeni TS6133 hariç)
- [ ] `npx vitest --run` tüm testler geçer (yeni testler dahil)
- [ ] `pytest -m "unit or not integration"` geçer
- [ ] `ruff check app` 0 lint hatası
- [ ] `mypy app --ignore-missing-imports` 0 type hatası
- [ ] `alembic check` yeni migration ile uyumlu
- [ ] Production build başarılı (`npx vite build`)
- [ ] CLAUDE.md güncellendi (yeni pattern/komut varsa)

---

# 📚 Referanslar

**Önceki çalışmaların commit'leri:**
- ProfilePage derinlik: `2ef72bb3`
- MonitoringPage tam yeniden yazım: `5d04e153`
- TripsPage/FleetPage geliştirme: `ef895dbd`
- LocationsPage genişletme: `9f79278c`
- AlertsPage tam redesign: `d208d15a`
- v5 görev listesi: `cefe1b96..c496f95c`

**Mimari dökümanlar:**
- `CLAUDE.md` — proje mimarisi, komutlar, frontend kuralları
- `docs/superpowers/plans/2026-05-20-v5-gorev-listesi.md` — son tamamlanan plan
- `docs/superpowers/plans/2026-05-17-frontend-full-rewrite.md` — frontend yeniden yazım referans

**Backend dosya konumları:**
- `app/api/v1/api.py` — tüm router'lar burada include ediliyor (32 router)
- `app/database/models.py` — SQLAlchemy 2 async ORM (1100+ satır)
- `app/core/services/` — domain logic
- `app/services/` — orkestrasyon, ML, external API
- `app/core/ml/` — ensemble + time series + route similarity + driver profile

**Frontend kuralları:**
- Tüm sayfa içeriği `frontend/src/pages/`
- Domain bileşenleri `frontend/src/components/<domain>/`
- API servisleri `frontend/src/services/api/`
- Turkish strings `frontend/src/resources/tr/<domain>.ts`
- Design tokens: `rounded-card`, `rounded-modal`, `bg-surface`, `bg-elevated`, semantic colors
- Test wrapper: `frontend/src/test/test-utils.tsx`
- Mock pattern: `vi.mock('@/components/auth/RequirePermission', () => ({ RequirePermission: ({ children }) => <>{children}</> }))`
