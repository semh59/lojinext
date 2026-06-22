# S8-S9 — Frontend Sunum Component'leri (presentational sweep)

Kapsam: frontend/src/components/** (non-test) + pages + resources + layouts + misc. S10 testler HARİÇ.
Mantık katmanı (API/hooks/lib/features/schemas) zaten `s8-frontend.md`'de. Bu dosya sunum component'leri.
Genel beklenti: render-only, React auto-escape (XSS sweep'i temiz — dangerouslySetInnerHTML/eval YOK).

## S9-1 — shared primitives: ui(11) + common(3) + auth(2) — 0 bulgu

`ui/`: Button/Input/Card/Badge/Toggle/Skeleton/Toast/Modal/Table/ErrorBoundary/EliteToaster — saf presentational,
iyi a11y (role=switch, aria-checked, aria-modal/labelledby, focus-visible, sr-only), forwardRef, React-escape.
Modal: createPortal + Escape + body-overflow lock. `common/`: ErrorBoundary (errorTracker.capture, import.meta.env.DEV),
Skeleton (jenerik loading), LojiNextLogo (SVG). `auth/`: RequirePermission + PrivateRoute (client-side advisory
guard — backend otoriter; hasPermission AUDIT-173 drift'ini miras alır). İz (kozmetik): `ui/ErrorBoundary`
`process.env.NODE_ENV` kullanıyor (Vite'ta tanımsız olabilir) — `common/ErrorBoundary` doğru `import.meta.env.DEV`
kullanıyor; tutarsızlık, dev-detay gösterimi etkisiz kalabilir (low/kozmetik, bulgu değil).

## S9-2 — trips/ (25 component, non-test) — 0 YENİ bulgu (AUDIT-174 uçtan-uca teyit)

trips/ klasörünün TAMAMI okundu (25 sunum component + TripForm/ alt-bölümleri). Yeni numara yok;
durum (TR/EN) ailesi **AUDIT-174** burada görünür UI'da defalarca teyit edildi, gerisi temiz presentational.

**AUDIT-174 manifestoları (kök s8-frontend.md / entities.ts TripStatusSchema; hepsi aynı bulgu):**
- `TripTable.tsx` — `getStatusStyles`/`getStatusConfig` → frontend `normalizeTripStatus(trip.durum)`;
  backend İngilizce `'Completed'` → alias map'te İngilizce yok → `undefined` → gri "default" badge +
  `status.toUpperCase()` ham "COMPLETED" metni + %0 progress bar. Ana tablo semptomu.
- `TripFormModal.tsx` — `tripSchema.durum: z.enum(TRIP_STATUS_VALUES).default(TRIP_STATUS_PLANLANDI)` Türkçe.
  **En ağır yol:** mevcut sefer DÜZENLENİRKEN `reset(initialData)` durum='Completed' (backend İngilizce) set eder;
  Türkçe `z.enum` bunu tanımaz → select ilk Türkçe seçeneğe düşer → kaydet'te durum Türkçe'ye/Planned'a sessizce
  geri yazılır (düzenleme her seferinde statüyü bozabilir). Aksi halde form sağlam (rhf + weather debounce + wizard).
- `TripFormSections.tsx` (`TripStatusSection`) — durum `<select>` seçenekleri Türkçe (PLANLANDI/TAMAMLANDI);
  ayrıca `normalizeTripStatus(initialData?.durum) === TRIP_STATUS_IPTAL` İngilizce 'Cancelled' için undefined →
  İptal seçeneği iptal edilmiş seferde gösterilmez.
- `TripList.tsx` — `getStatusBadgeClass(normalizeTripStatus(...))` + `displayStatus = normalized ?? trip.durum`;
  İngilizce durumda gri badge + ham İngilizce metin. (İz: TripsModule TripTable kullanıyor; TripList olası ölü
  component — düşük öncelik, AUDIT-174 fix'inde birlikte ele alınır.)
- `BulkStatusModal.tsx` — toplu durum güncelleme seçenekleri Türkçe (s8-8'de işaretliydi, burada teyit).

**Temiz presentational (0 bulgu):** TripTimeline (renderValue JSON.stringify/String, React-escape),
PlanWizardXaiPanel + PlanWizardCard + PlanWizardStep (XAI skor barları; `reasons`/`risk_label`/`route_type`
backend trip_planner'dan server-construct, React-escape; `r.startsWith("⚠")` yalnız ikon seçimi),
TripCostAnalysisModal (async job + useTaskStatus; result number değilse JSON.stringify `<pre>` React-escape),
TripAnalytics (recharts; tüm değerler numeric `.toFixed`, `reason_label`/`plaka` React-escape),
TripStats / TripHeader / BulkActionBar (RequirePermission ile sefer:onayla/write/delete gate'li) /
BulkCancelModal (reason min 5 char guard) / ImportProgressModal / TripsTodaySummary (backend-computed sayaçlar,
ham durum okumaz — AUDIT-174'ten ETKİLENMEZ) / TelemetrySection (trips/ + TripForm/ ikisi) / RouteSelector /
StaffVehicleSection / LoadManagementSection / DateTimeSection / RoundTripSection / RoundTripSelector —
hepsi register/props-driven, raw-HTML/eval yok, a11y düzgün.

## S9-3 — predictions(10) + fuel(10) + ai(2) + weather/today/feedback(3) = 25 dosya — 0 YENİ bulgu

Tahmin/yakıt/AI sunum katmanı tamamen okundu. XSS yüzeyi temiz (dangerouslySetInnerHTML/eval YOK; tüm
LLM/back-end metni React-escape ile interpolate). Yeni numara yok; iki mevcut bulgu burada da görünür.

**Mevcut bulgu manifestoları (yeni numara değil):**
- `ai/ChatAssistant.tsx` — `useAiStore` mesaj geçmişini render eder; store persist'i **AUDIT-176** (kullanıcı-scope'suz
  sohbet geçmişi reload/cross-user'da sızar) buradan görünür. `msg.content` (LLM yanıtı) düz metin `{msg.content}` →
  React-escape (XSS yok).
- `ai/AiQueryPanel.tsx` — AI aksiyon URL'leri react-router `<Link to={a.url}>` ile render edilir; **AUDIT-177'nin
  ham-href (`javascript:`/open-redirect) riski BURADA YOK** çünkü react-router `to`'yu path olarak çözer
  (`javascript:`/mutlak URL nötralize olur). `result.answer` düz metin (whitespace-pre-line) → React-escape.
  Web Speech API opsiyonel (feature-detect). recharts grafiği numeric.
- `fuel/FuelModal.tsx` — `fuelSchema.durum` zod default `fuelModalText.enums.pending` create'te submit edilir ama
  formda durum `<select>` RENDER EDİLMEZ (yalnız defaultValues). Bu, **AUDIT-165** (yakit `durum` değeri DB CHECK
  ASCII `Onaylandi` vs Türkçe) frontend submit ayağı — aynı bulgu. depo_durumu select 3. seçenek `enums.full` value'su
  ile `tankStatusOptions.unknown` label eşleşmesinde iz var (kozmetik).

**Temiz presentational (0 bulgu):** predictions: PredictionResult/PredictionSimulator/XaiExplainPanel/XaiPanel
(+EnsembleWeightsPanel)/AccuracyChart/MetricCards/EnsembleStatusCard/TimeSeriesForecast/TimeSeriesStatusCard/
TimeSeriesTrendSection — recharts SVG (escaped), tüm değer numeric `.toFixed`, model/feature key'leri React-escape,
`as any` yalnız tip-gevşetme (bulgu değil). fuel: FuelTable (virtualized, plaka/istasyon/fis_no escaped, durum kolonu
yok)/FuelFilters/FuelAnomalyWidget (manuel tz-safe formatDate)/ComparisonWidget/CostTrendChart/FuelHeader/
FuelPagination/FuelStats (useAnomalyCount paylaşımlı cache)/ReceiptUpload (OCR best-effort, controlled input escape).
weather/WeatherAnalysisCard (numeric impact), today/QuickActionsBar (statik route navigate), feedback/FeedbackButton
(textarea maxLength 2000, backend best-effort Telegram OPS).

## S9-4 — monitoring(9) + alerts(7) + admin(5) = 21 dosya — 0 YENİ bulgu; AUDIT-175 WS genişlemesi

İzleme/anomali/admin paneli okundu. XSS temiz (dangerouslySetInnerHTML/eval YOK; stack_trace, Groq insight,
soruşturma notları hepsi React-escape `<pre>{}`/`<p>{}`).

**AUDIT-175 GENİŞLEMESİ (yeni numara değil — aynı sınıf, blast-radius büyüdü):**
- `monitoring/useMonitoringSocket.ts:28` — `/admin/ws/live?token=${token}` (token = `tokenStorage.get()` ham JWT)
- `monitoring/useTrainingSocket.ts:27` — `/admin/ws/training?token=${token}` (aynı ham JWT)
  AUDIT-175 (NotificationContext WS JWT query-param) yalnız bildirim WS'iydi; bu İKİ admin WS daha **ham access
  token'ı query string'e** koyuyor → proxy/access-log/browser-history/referrer'a sızar; admin token olduğu için
  daha hassas. **Düzeltme zaten repo'da var:** `monitoring/useErrorStream.ts` SSE'yi `errorService.getSseToken()`
  ile kısa-ömürlü TICKET URL'inden açıyor (ham JWT yok) — örnek/güvenli desen; WS'ler bunu uygulamıyor.

**Örnek/güvenli (AUDIT-177 referans deseni):**
- `alerts/InvestigationDetailDialog.tsx` — kanıt URL'lerinde `safeHref(url)` HEM ekleme-validasyonunda (http(s)/
  mailto dışını reddet) HEM render'da (`href={safeHref(url)}` + `rel="noopener noreferrer"`); notes maxLength 4000,
  kanıt ≤10. AUDIT-177'nin istediği desen — burada doğru uygulanmış (referans).
- `monitoring/useErrorStream.ts` — SSE ticket deseni (yukarıda).

**Temiz presentational (0 bulgu):** monitoring: ErrorEventsTab (evt.message/path/severity escape; iz: satır 315
runtime Tailwind arbitrary class `border-l-[${...}]` JIT üretmez → kozmetik, renk uygulanmaz)/TraceDetailDialog
(stack_trace `<pre>` escape, clipboard)/TrainingTab/NotificationsTab/ConnectionStatus/useNotifications (RQ merge+
optimistic read). alerts: InvestigationCard/InvestigationsKanban/AnomalyTable(LeakageSummary+SeverityBadge+
MaintenanceTable)/AnomalyClusters (Groq insight `<p>{}` escape)/PatternList/SeverityFilter. admin: UserRolePanel
(parent-controlled RBAC form, password autoComplete=new-password)/TelegramOnayPanel (onayla/reddet backend-authz)/
maintenance/MaintenanceCalendar (FullCalendar event title text-render)/MaintenanceDetailDrawer/PredictionsTable.

## S9-5 — drivers/ (9 dosya) — 0 YENİ bulgu

Şoför yönetimi + XAI skor bileşenleri okundu. Temiz. PII (tc_no/telefon/telegram_id) yalnız form input;
maskeleme backend sorumluluğu (AUDIT-121/122/127/144 ailesi — frontend sızdırmıyor).

**İz (yeni numara değil):** `DriverScoreModal.tsx` `calculateHybridScore` 0.6/0.4 ağırlıkları HARDCODE ile hibrit
skoru ÖN-İZLEME yapar (`estimatedHybrid`, "Tahmini" etiketli); `DriverScoreBreakdown` ise backend'den
`manual_weight`/`auto_weight` alır. Bu ön-izleme/gerçek ağırlık sapması **AUDIT-048** (çoklu puanlama ölçeği)
ailesini pekiştirir — kozmetik (gerçek değer kayıtta backend'den gelir), düşük öncelik.

**Temiz presentational (0 bulgu):** DriverModal (rhf+zod, 3 tab temel/kişisel/telegram, telefon format,
tc_no max11, telegram_id regex digits)/DriverScoreBreakdown (XAI skor kırılımı, numeric)/DriverRouteProfile
(recharts güzergah tipi sapma)/DriverTable (ad_soyad/telefon escape, yıldız)/DriverScoreModal/DriverPerformanceModal
(safety/eco/compliance numeric skor — AI freetext YOK)/DriverGrid/DriverHeader (DataExportImport)/DriverFilters
(arama + skor range clamp). Hepsi register/props-driven, React-escape, raw-HTML/eval yok.

## S9-6 — executive(8) + vehicles(8) = 16 dosya — 0 bulgu

Yönetici (executive) gösterge + araç yönetimi okundu. Tamamen temiz; XSS yüzeyi yok (recharts SVG, numeric,
React-escape). Notable: `executive/BusFactorWidget` şoförleri index ile ANONİMLEŞTİRİR (#1/#2, isim yok) + piiNote
— iyi gizlilik pratiği.

**Temiz presentational (0 bulgu):** executive: DownloadPdfButton (backend PDF)/WhatIfPanel (senaryo numeric input,
reasons `<li>` escape)/BusFactorWidget (anonim)/CarbonReportCard/ComplianceHeatmap (plaka escape)/
CashflowProjectionChart/CrossFeatureSavings/FleetEfficiencyCard (FVI alt-skor bar). vehicles: VehicleModal
(useVehicleData rhf, plaka/marka/motor_no/sasi_no input)/VehicleDetailModal (notlar + event.details `<p>{}` escape,
stats numeric)/VehicleTable (kart grid, optimistic delete)/InspectionAlertModal (muayene listesi)/VehicleDeleteModal
(soft vs hard delete ayrımı)/VehicleFilters/VehicleHeader (DataExportImport)/SkeletonTable. register/props-driven.

## S9-7 — reports(5) + reports-studio(2) + shared(3) + trailers(6) = 16 dosya — 0 bulgu

Rapor/şablon/dosya-transfer/dorse sunum katmanı okundu. Tamamen temiz. Dosya yükleme güvenli desende:
`shared/ExcelUploadModal` + `DataExportImport.processFile` uzantı (.xlsx/.xls) doğrular (içerik backend doğrular,
client advisory); import aksiyonu `RequirePermission "sefer:write"` ile gate'li. Upload hata satırları React-escape
(JSON.stringify fallback). Tüm rapor değerleri numeric (recharts/Intl).

**Temiz presentational (0 bulgu):** reports: CostAnalysisChart/PeriodCostBreakdown/ReportCards/SavingsPotentialCard
/ROICalculator (yatırım slider + ROI numeric). reports-studio: TemplateConfigPanel (template.title/description escape)
/TemplateGallery. shared: DataExportImport (RequirePermission gate)/ExcelUploadModal (uzantı validation, createPortal)
/ExportDialog (format/tarih/araç seçimi, plaka option escape). trailers: TrailerTable (grid+list, plaka/marka/tipi
escape, optimistic delete)/TrailerModal (raw-setState form, plaka/marka/notlar input)/TrailerDetailModal (InfoCard
value escape)/TrailerDeleteModal/TrailerFilters/TrailerHeader (DataExportImport). register/props-driven, React-escape.

## S9-8 — locations(5)+dashboard(4)+coaching(4)+modules(3)+profile(2)+fleet(1)+fleet-insights(1) = 20 dosya — 0 bulgu

components/ ağacının kalanı okundu — TÜM components/ bitti. Tamamen temiz.

**Notable temiz desenler:**
- `coaching/CoachingInsightsPanel` — LLM/fallback üretimi koçluk metni (`headline`/`pattern`/`suggestion`/`evidence`)
  düz React-escape `<p>{}`/`<span>{}` ile render (dangerouslySetInnerHTML YOK). `data.source==='llm'` rozet ile şeffaf.
- `coaching/SendCoachingDialog` — Telegram mesajı; textarea min10/max1000, insight.suggestion preset.
- `modules/{Vehicles,Drivers,Trailers}Module` — orkestrasyon (RQ + mutation + blob export `createObjectURL`→`click`→
  `revokeObjectURL` temizlikli, AUDIT frontend API katmanı kalitesiyle uyumlu); bulk delete `window.confirm` gate.
- `locations/CalibrationModal` — sefer ID input + admin kalibrasyon (kalibrasyon_duzenle backend-authz).

**Temiz presentational (0 bulgu):** locations: LocationFormModal (rhf useLocationForm, geocode suggestion.label
escape)/CalibrationModal/AnalysisModal/LocationList (cikis/varis_yeri escape, correction_reason title-attr)/
RouteAnalysisCard (recharts pie). dashboard: AnomalyWidget (plaka/reason escape)/ConsumptionChart/KpiRow/
KpiTrendBadge. coaching: CoachingInsightsPanel/SendCoachingDialog/CoachingDriverList/EffectivenessMiniCard.
modules: VehiclesModule/DriversModule/TrailersModule. profile: PushNotificationToggle (usePushNotifications)/
QuietHoursSettings (preferenceService). fleet/FleetInsights (StatCard numeric). fleet-insights/PeriodComparisonCard.

> **S9 components/ TAMAM:** 8 batch (s9-1..s9-8), ~205 sunum component'i. Yeni bulgu YOK; tüm durum=AUDIT-174,
> AUDIT-175 WS genişlemesi (monitoring sockets), AUDIT-176/177/165/048 manifestoları. XSS yüzeyi tamamen temiz
> (dangerouslySetInnerHTML/eval HİÇBİR component'te yok; tüm LLM/backend metni React-escape).

## S9-9 — layouts(3) + services root(3) + types(2) = 8 dosya — 0 YENİ bulgu

Yerleşim + kök servisler + tip tanımları okundu. Temiz.

**İz (yeni numara değil, low/nv):** `services/error-tracker.ts` hata raporunu (`message`/`stack`/`componentStack`/
`url=window.location.href`/`userAgent`/`extra`) backend `/system/error-report` sink'ine POST eder (token Bearer ile,
dedup+cooldown+sendBeacon flush — sağlam tasarım). `url` TAM query string içerir → bir route query-param secret
taşıyorsa (örn. reset-password `?token=`) error-report tablosuna sızabilir (PII/secret-in-log ailesi, AUDIT-121/122
+ Sentry scrub ile aynı sınıf). Backend tarafının URL scrub edip etmediği doğrulanmalı (nv). `storageService.getItem
("access_token")` — axios `tokenStorage` ile aynı store olduğu varsayılıyor (tutarlılık izi).

**Temiz (0 bulgu):** `layouts/EliteLayout` (NotificationPanel n.baslik/icerik escape; navGroups role-gate;
user.full_name/role escape; tema localStorage), `layouts/LanguageSwitcher` (i18n toggle), `layouts/navGroups`
(rol-bazlı sidebar — client-advisory, backend otoriter = AUDIT-173 ailesi), `services/dorseService` (axiosInstance
+ blob revokeObjectURL temizlikli — s8 32-servis kalitesiyle uyumlu), `services/error-middleware` (zustand set
wrapper, safeStringify 100-char cap), `types/index.ts` (497 satır saf interface, mantık YOK), `types/location.ts`.

## S9-10 — pages/ (27 dosya: 20 sayfa + 7 admin) — 0 YENİ bulgu

Tüm sayfalar okundu (CLAUDE.md'deki "thin page" deseni doğrulandı — çoğu modül kompozisyonu). XSS temiz.

**Notable temiz desenler:**
- `pages/admin/AdminLayout` — sert rol gate (`role !== super_admin && !== admin` → access-denied); client-advisory,
  backend her admin endpoint'te otoriter (AUDIT-173 ailesi). `pages/HomePage` rol-bazlı lazy (TodayPage vs Dashboard).
- `pages/admin/SistemSaglikPage` — SSE'yi `errorService.getSseToken()` TICKET ile açar (ham JWT YOK) — AUDIT-175
  WS düzeltme yönünü pekiştiren güvenli desen. CB reset/backup admin mutation'ları.
- `pages/AlertsPage` — URL paramları whitelist+aralık valide eder (days 1-365, tip/status enum); ack/resolve
  `RequirePermission "anomali:yonet"` gate; anomaly.rca_summary/suggested_action (olası LLM) düz React-escape;
  resolve textarea maxLength 2000.
- `pages/ProfilePage` — şifre değiştir formu (rhf+zod güç ölçer, current_password zorunlu, 8+/upper/lower/digit);
  user.son_giris_ip (kendi PII'si) gösterimi React-escape.
- Tüm export/import sayfaları blob `createObjectURL`→`click`→`revokeObjectURL` temizlikli (FuelPage/ReportsPage/
  ReportsStudioPage/VeriYonetim).

**Temiz (0 bulgu):** sayfalar: Trips/RouteLab/Fleet/Monitoring/Today/Dashboard/Coaching/Drivers/Executive/
FleetInsights/Fuel/Locations/Predictions/Reports/ReportsStudio/NotFound/Home/Profile/Alerts. admin: AdminLayout/
Overview/Analytics(route path escape)/Bakim/Bildirimler(rule CRUD)/MLYonetim/SistemSaglik/VeriYonetim. Tümü
RQ+mutation orkestrasyon, recharts/numeric, React-escape, raw-HTML/eval YOK.

## S9-11 — kök dosyalar (App/main/i18n/sw-push/vite-env) = 5 dosya — 1 YENİ bulgu (AUDIT-183, low/nv)

Frontend bootstrap + routing + service worker okundu. App.tsx route-level RBAC (`PrivateRoute
requiredPermission="admin:read"` /admin'i sarar — client-advisory, backend otoriter). main.tsx errorTracker
install + web-vitals + **console.error monkey-patch** (console.error içeriğini 500-char cap ile error-sink'e yollar
— AUDIT'teki error-tracker url-leak iz'ini genişletir, aynı aile). i18n.ts `escapeValue:false` — **bu react-i18next
için DOĞRU ayar** (React zaten escape eder, XSS değil). vite-env.d.ts tip referansı.

### AUDIT-183 — sw-push notificationclick push payload `url`'sini same-origin doğrulaması olmadan `openWindow` ile açıyor
- Şiddet: low
- Sınıf: security
- Konum: sw-push.ts:40-58 (notificationclick → `self.clients.openWindow(url)`), url kaynağı satır 34 `data.url`
- Durum: needs-verification
- Kanıt:
    ```ts
    self.addEventListener("notificationclick", (event) => {
      const url = (event.notification.data as { url?: string })?.url ?? "/today";
      ...
      if (self.clients.openWindow) return self.clients.openWindow(url);  // url valide edilmiyor
    });
    // push handler: data = event.data.json(); options.data = { url: data.url ?? "/today" }
    ```
  `notificationclick`, push payload'ından gelen `url`'i (`event.notification.data.url`) hiçbir same-origin/relative
  doğrulaması yapmadan `openWindow(url)` ile açar. Push payload backend web-push gönderiminden gelir; bugün
  deterministik deep-link (`/today`, `/alerts`). Ancak backend push `url`'i hiç güvenilmeyen girdiden türetilirse
  (örn. kullanıcı içerikli bildirim), `openWindow("https://evil.com")` ile harici origin'e yönlendirme/phishing
  click-through olur (`javascript:` SW'de bloklu; harici https açılır). `w.url.includes(url)` focus kontrolü de
  gevşek (substring). AUDIT-177 (safeHref) ile aynı "navigasyon öncesi URL valide et" prensibi, farklı yüzey (SW push).
- Önerilen düzeltme: `url`'i same-origin relative path'e kısıtla — `new URL(url, self.location.origin)` parse et,
  `origin === self.location.origin` değilse `/today`'e düş; focus eşleşmesini `includes` yerine pathname-eşit yap.
- Bağımlılık: AUDIT-177 (safeHref deseni), backend push payload yapısı (push-service), usePushNotifications.

> **S9-11 + S8-S9 FRONTEND TAMAM.** Tüm frontend non-test (components + pages + layouts + services + types +
> root) okundu. Toplam yeni bulgu (S8-S9 sweep): **AUDIT-183 (1)** + AUDIT-175 WS genişlemesi (yeni numara değil) +
> error-tracker/url-leak iz (nv). XSS yüzeyi: dangerouslySetInnerHTML/eval HİÇBİR frontend dosyasında yok.

## S9-12 — resources/tr/ (18 dosya, 2257 satır) — 0 bulgu

Türkçe string kaynak nesneleri. İçerik-düzeyi tarama: http(s) URL YOK, HTML/script tag YOK, eval/window/document/
localStorage/innerHTML YOK, sabit sır YOK. Tüm template helper'ları (trips 23 / vehicles 12 / drivers 10 /
locations 9 vb.) saf string interpolation (`(count)=>\`${count} sefer\``, `(name)=>\`${name} • ...\``) — interpolate
edilen değerler (count/name/plaka/origin) display verisi, React-escape ile render edilir, tehlikeli sink yok.
Saf sunum verisi; mantık/güvenlik yüzeyi yok.

> **S8-S9 FRONTEND TAMAM (resources dahil).** Frontend non-test'in TAMAMI denetlendi: components(~205) + pages(27) +
> layouts(3) + services(3 kök) + types(2) + resources(18) + kök(5) = ~263 sunum/data dosyası. S9 toplam yeni bulgu:
> **AUDIT-183** (sw-push openWindow). Diğer tüm tespitler mevcut bulgu manifestoları (AUDIT-174/175/176/177/165/048/
> 173) veya iz (error-tracker url-leak nv). **Frontend XSS yüzeyi tertemiz** (dangerouslySetInnerHTML/eval YOK).
> Kalan kapsam: yalnız S10 testler (frontend __tests__ + backend app/tests/) — kullanıcı kararıyla HARİÇ.
