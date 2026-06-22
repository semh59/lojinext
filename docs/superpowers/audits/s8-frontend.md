# S8-S9 — Frontend (React/TS) Bulguları

Kapsam: frontend/src/** (components ~241, pages 53, services 50, hooks 32, lib 8, stores 4, context 4, …).
Plan S8-S9. Denetim odağı: XSS, token storage, auth interceptor, API kontrat drift, state.

## S8-1 — auth/token + lib/state çekirdeği (9) — 3 bulgu (high 1)

**Güçlü güvenlik duruşu:** Frontend genelinde `dangerouslySetInnerHTML`/`innerHTML`/`eval` **YOK** (React
auto-escape). `access_token` **sessionStorage**'da (SEC-006, localStorage değil) + refresh **httpOnly cookie** +
WS **kısa-ömürlü ticket** (`/ws/ticket`, AUDIT-118'i çözer). `utils.safeHref` örnek: http/https/mailto/tel
allow-list + `java\tscript:` obfuscation strip. `use-trip-store` user-scoped key (B-007 cross-user bleed fix).
`api-validator` Zod safeParse + güvenli fallback (AUDIT-108 ailesi — validation fail'de ham data döner, low/iz).

### AUDIT-172 — axios 401 refresh interceptor'da mutex yok → eşzamanlı 401'ler birden çok /auth/refresh tetikler → refresh-token rotate ediliyorsa sahte logout
- Şiddet: medium
- Sınıf: concurrency
- Konum: axios-instance.ts:53-89
- Durum: confirmed
- Kanıt:
    ```js
    if (status === 401 && !originalRequest?.url?.includes("/auth/token")) {
      if (!originalRequest?._retry) {
        originalRequest._retry = true;
        const resp = await axios.post(`${API_BASE_URL}/auth/refresh`, {}, {withCredentials:true});
        // ... paylaşılan refresh-promise / mutex YOK
    ```
  `_retry` yalnız tek isteğin tekrarını engeller; ama token expire olduğunda aynı anda N istek 401 alırsa
  HER biri kendi `/auth/refresh` POST'unu atar (paylaşılan refresh promise yok). Backend refresh-token'ı
  rotate ediyorsa (one-time-use, kullanici_oturumlari.refresh_token_hash) ilk refresh başarılı + rotate eder,
  2..N eski cookie ile fail → logout → kullanıcı sayfa ortasında atılır. Rotate etmiyorsa yalnız N gereksiz
  refresh çağrısı. Backend rotate davranışı doğrulanmalı.
- Önerilen düzeltme: tek paylaşılan refresh promise (in-flight refresh varsa onu await et); refresh
  tamamlanana kadar diğer 401'leri kuyruğa al.
- Bağımlılık: auth/refresh endpoint rotation (S3), kullanici_oturumlari.

### AUDIT-173 — AuthContext.hasPermission sabit role→izin haritaları kullanıyor, fetch ettiği gerçek `rol_yetkiler`'i YOK SAYIYOR → backend RBAC ile drift
- Şiddet: medium
- Sınıf: maintainability
- Konum: AuthContext.tsx:57,111-152
- Durum: confirmed
- Kanıt:
    ```js
    rol_yetkiler: rol?.yetkiler as Record<string, boolean> | undefined,  // fetch edilir
    ...
    const hasPermission = (permission) => {
      if (role === "user") return ["sefer:read","sefer:write",...].includes(permission);  // SABİT liste
      return false;  // bilinmeyen rol → her şey gizli
    };  // rol_yetkiler hiç kullanılmıyor
    ```
  `mapUserData` backend'in gerçek `rol.yetkiler` haritasını alıyor ama `hasPermission` bunu kullanmıyor;
  yerine rol adına göre SABİT-KODLU izin listeleri uyguluyor. Sonuç: (a) admin_roles ile yaratılan özel roller
  (AUDIT-117) `return false`'a düşer → UI her şeyi gizler (backend izin verse de); (b) sabit roller için izin
  rol adından türetilir, backend'in gerçek yetkiler'inden değil → UI backend'in reddedeceği aksiyonları
  gösterebilir (403) ya da izin verdiğini gizleyebilir. Salt-UI (backend otoriter) ama tutarsızlık/UX kırığı.
- Önerilen düzeltme: `hasPermission`'ı `user.rol_yetkiler` haritasından türet (`yetkiler[permission] === true`
  veya `yetkiler["*"]`); sabit listeleri kaldır.
- Bağımlılık: AUDIT-117 (özel rol), SecurityService.verify_permission (backend RBAC).

### AUDIT-174 — Frontend trip-status canonical'ı TÜRKÇE ('Planlandı/Tamamlandı/İptal'), backend (0022 sonrası) İNGİLİZCE ('Planned/Completed/Cancelled') → durum gösterimi boş + durum filtresi 0-eşleşme/422
- Şiddet: high
- Sınıf: bug
- Konum: lib/trip-status.ts:1-61 + use-trip-store.ts:88-89,148 (vs app/schemas/sefer.py:29-37,246)
- Durum: confirmed
- Kanıt:
    ```js
    // frontend canonical = TÜRKÇE
    export const TRIP_STATUS_VALUES = ["Planlandı","Tamamlandı","İptal"];
    const LEGACY_TRIP_STATUS_ALIASES = { Tamam:.., Planlandi:.., "TamamlandÄ±":.., ... };  // İngilizce YOK
    normalizeTripStatus("Completed")  // → undefined (ne VALUES'te ne alias'ta)
    ```
    ```python
    # backend SeferResponse canonical = İNGİLİZCE (DB CHECK ile birebir)
    class SeferDurum: PLANNED="Planned"; COMPLETED="Completed"  # sefer.py:29
    "Durum'u canonical forma (Planned/Completed/Cancelled) çevirir"  # sefer.py:246
    ```
  Backend API durum'u İngilizce canonical döndürüyor (0022 + sefer.py:246 doğrulandı). Frontend trip-status
  canonical'ı hâlâ Türkçe; legacy alias haritası mojibake (`TamamlandÄ±`) dahil her şeyi kapsıyor AMA backend'in
  İngilizce değerlerini KAPSAMIYOR → `normalizeTripStatus('Completed')` undefined → durum rozeti boş/bilinmeyen.
  Ayrıca trip-store filtresi backend'e Türkçe 'Tamamlandı' yolluyor → backend SeferDurum enum (İngilizce-only)
  ya 422 verir ya da `WHERE durum='Tamamlandı'` 0 satır → durum filtresi tamamen kırık. AUDIT-058 carry'si
  kesinleşti.
- Önerilen düzeltme: frontend canonical'ı backend ile hizala (İngilizce 'Planned/Completed/Cancelled' +
  Türkçe görünen etiketleri ayrı bir label map'te tut); alias'lara İngilizce'yi ekle; trip-store filtresi
  İngilizce göndersin. Tek "source of truth" backend SeferDurum.
- Bağımlılık: AUDIT-058 (carry), AUDIT-164/163 (durum drift), AUDIT-108 (SeferResponse), trip_status.py.

> S8-1: auth/token + lib/state çekirdeği temiz/güçlü; tek high AUDIT-174 (durum kontrat drift'i).

## S8-2 — validations + ai-store + NotificationContext + route-weather + theme(2) — 2 bulgu

Temiz: `validations.ts` Zod şemaları backend Pydantic'i aynalar (plaka/koordinat/sınır doğru); `route-weather`,
`theme`, `chart-theme` saf util/token. **AUDIT-174 PEKİŞTİ + AUDIT-165 frontend kanıtı:** `validations.ts`
tripSchema.durum = Türkçe + obsolet (`["Bekliyor","Planlandı","Yolda","Devam Ediyor","Tamamlandı","Tamam",
"İptal"]`, default 'Planlandı') → trip create/edit'te backend SeferCreate İngilizce enum'a düşürür
(sefer.py:246 "Planned'e fallback") = **sessiz durum kaybı** (kullanıcı 'Tamamlandı' seçer, 'Planned' kaydolur).
fuelSchema.durum = `'Onaylandı'` (Türkçe ı) → backend 0006 CHECK `'Onaylandi'` (ASCII) → AUDIT-165 onay ihlali
kesinleşti. Bunlar AUDIT-174/165 kapsamında (yeni bulgu açılmadı, kanıt eklendi).

### AUDIT-175 — NotificationContext WS bağlantısı JWT'yi query-param'da gönderiyor (`?token=`) → log sızıntısı; ws-service ticket kullanırken tutarsız
- Şiddet: medium
- Sınıf: security
- Konum: NotificationContext.tsx:80-92 (vs ws-service.ts ticket deseni)
- Durum: confirmed
- Kanıt:
    ```js
    const token = tokenStorage.get();
    const wsUrl = `${protocol}//${window.location.host}/api/v1/admin/ws/live?token=${token}`;
    const ws = new WebSocket(wsUrl);   // JWT URL query string'inde
    ```
  `ws-service.ts` güvenli kısa-ömürlü ticket (`POST /ws/ticket`) kullanırken, `NotificationContext` admin live
  WS'ine ham JWT access_token'ı **query parametresi** olarak yolluyor → server/proxy access log'larında,
  tarayıcı geçmişinde, Referer'da token sızar (AUDIT-118 backend tarafının frontend karşılığı). İki WS deseni
  tutarsız.
- Önerilen düzeltme: NotificationContext da `wsService.getTicket()` kullanıp ticket'ı query'ye koysun (ya da
  Sec-WebSocket-Protocol header'ı); ham JWT'yi URL'den kaldır.
- Bağımlılık: AUDIT-118 (admin_ws token query-param), ws-service ticket, AUDIT-155 (key-in-URL teması).

### AUDIT-176 — use-ai-store user-scoped DEĞİL → AI sohbet geçmişi paylaşılan tarayıcıda kullanıcılar arası sızar (use-trip-store B-007 ile tutarsız)
- Şiddet: low
- Sınıf: privacy
- Konum: stores/use-ai-store.ts:93-100 (vs use-trip-store.ts:57-70,137 userScopedStorage)
- Durum: confirmed
- Kanıt:
    ```js
    persist(..., { name: "loji-ai-storage", partialize: (s)=>({messages:s.messages,...}) })
    // userScopedStorage YOK → düz localStorage; use-trip-store B-007 user-scoped key kullanıyor
    ```
  `use-trip-store` cross-user bleed'i `userScopedStorage` (B-007) ile çözmüş ama `use-ai-store` düz
  `localStorage`'a (`loji-ai-storage`) kalıcılaştırıyor → aynı tarayıcıda kullanıcı değiştiğinde önceki
  kullanıcının AI sohbet geçmişi (filo/operasyon soruları içerebilir) yeni kullanıcıya görünür. Paylaşımlı
  cihaz gizlilik riski.
- Önerilen düzeltme: use-ai-store'a da `userScopedStorage` uygula (trip-store gibi) veya logout'ta
  `loji-ai-storage`'ı temizle.
- Bağımlılık: use-trip-store B-007, AuthContext.logout.

> S8-2: validations/ai-store/context temiz; AUDIT-175 (WS token query), 176 (ai-store user-scope yok);
> AUDIT-174/165 frontend kanıtlarıyla pekişti (durum form-submit sessiz kayıp + yakit CHECK ihlali).

## S8-3 — API services çekirdeği (8): trip/admin/driver/fuel/vehicle/anomaly/push/index — 0 yeni bulgu

API service katmanı **tutarlı ve temiz**: hepsi `axiosInstance` (fetchWithAuth misuse YOK — yalnız auth-service
kullanıyor, CLAUDE.md kuralına uygun) + `validateResponse` (Zod) + {data,meta}/raw-list fallback'leri +
B-003 idempotency-key (trip create/upload). Sabit-kodlu sır YOK, client-side authz varsayımı YOK (backend
otoriter). Response-shape drift'leri bilinçle düzeltilmiş (fuel/vehicle upload `message` parse yorumları).
**AUDIT-174 genişledi:** `trip-service.getAll`/`getStats` durum filtresi + `bulkUpdateStatus` Türkçe
`TripStatus`/`TripAssignableStatus` gönderiyor → backend İngilizce enum → liste filtresi + toplu durum
güncelleme de kırık (yeni bulgu yok, AUDIT-174 kapsamı: gösterim+filtre+form+bulk+store = tüm trips modülü).

> S8-3: API çekirdeği temiz; durum drift'i (AUDIT-174) trip-service filtre+bulk'a uzanıyor.

## S8-4 — kalan API services (19): location/executive/prediction/ai/error/report/investigation/coaching/reports-studio/route-sim/trip-planner/today/preference/notification/analytics/fleet-insights/maintenance-predictions/weather/feedback — 0 yeni bulgu

**API service katmanı TAMAM (32/32) — üniform yüksek kalite.** Hepsi axiosInstance + (çoğu) Zod validateResponse;
blob indirme (executive/maintenance ics/PDF) `URL.createObjectURL`+`revokeObjectURL` ile doğru temizleniyor;
SSE (prediction stream, error-stream) dedike kısa-ömürlü token kullanıyor (raw JWT DEĞİL — AUDIT-175'ten farklı,
güvenli); analytics/feedback best-effort (hata yutulur, UI bozulmaz); coaching backend html.escape notu.
**Component-review carry (XSS):** `today-service.TriageAction.url` ve `ai-service.actions[].url` backend/LLM
üretimi URL'ler → render eden component'ler `safeHref` kullanmalı (TriageItemCard window.open dahil doğrulanacak).

> S8-4: API katmanı 32/32 temiz. Tek kontrat sorunu AUDIT-174 (durum). Sıradaki: hooks + components (URL-href
> safeHref doğrulaması + durum gösterim component'leri).

## S8-5 — component XSS/href spot-check (TriageItemCard, InvestigationDetailDialog) — 1 bulgu

Örnek: `InvestigationDetailDialog` backend evidence URL'lerini `href={safeHref(url)}` + `target="_blank"` +
`rel="noopener noreferrer"` ile render ediyor (doğru desen — takım safeHref'i biliyor). `navigate(url)`
react-router'da `javascript:` şemasını nötralize eder (güvenli).

### AUDIT-177 — TriageItemCard.handleAction backend/LLM URL'sini safeHref scheme-doğrulaması olmadan window.open'a veriyor (InvestigationDetailDialog safeHref kullanırken tutarsız)
- Şiddet: low
- Sınıf: security
- Konum: components/today/TriageItemCard.tsx:63-72 (vs InvestigationDetailDialog.tsx:290 safeHref)
- Durum: confirmed
- Kanıt:
    ```js
    const handleAction = (url, actionType) => {
      if (actionType === "external") {
        window.open(url, "_blank", "noopener,noreferrer");  // safeHref YOK
      } else { navigate(url); }  // navigate güvenli (react-router javascript: nötralize)
    };
    ```
  `TriageAction.url` ve benzer şekilde `ai-service.actions[].url` backend/LLM üretimi. TriageItemCard
  `external` aksiyonda url'yi `window.open`'a şema doğrulaması yapmadan veriyor. URL'ler şu an server-üretimi
  iç path'ler + `noopener` yeni pencereyi izole ettiğinden gerçek istismar düşük; ama `safeHref` util'i mevcut
  ve InvestigationDetailDialog'da doğru uygulanırken burada uygulanmıyor → tutarsız defense-in-depth boşluğu.
  Bir triage url'si ileride kullanıcı verisi/`javascript:` içerirse risk artar.
- Önerilen düzeltme: `window.open(safeHref(url) ?? "", ...)` (boşsa açma); aynı kontrolü AI action-link
  render'ında uygula. Tek "URL render = safeHref" konvansiyonu.
- Bağımlılık: utils.safeHref, today-service/ai-service URL'leri, InvestigationDetailDialog (doğru desen).

> S8-5: href/window.open XSS yüzeyi büyük ölçüde safeHref ile korunuyor; AUDIT-177 tek tutarsızlık (low).
> NOT: components(241)+pages(53)+hooks(32) ve tüm testler (463) henüz okunmadı — sunum/test ağırlıklı bulk.

## S8-6 — hooks (22 non-test) — 1 bulgu (low)

**Hooks katmanı ÖRNEK kalite (TanStack Query best-practice):** queryKey konvansiyonları (CLAUDE.md ile uyumlu,
prefix-collision yok), staleTime/refetchInterval bilinçli, mutation+invalidation, terminal-status'ta polling
durdurma (useTaskStatus), SSE expo-backoff + mounted-ref cleanup (use-event-source), debounce, render-guard
(observability), userScoped URL-state. **AUDIT-174 PEKİŞTİ:** useTripsData refetchInterval `normalizeTripStatus
(trip.durum)===TRIP_STATUS_PLANLANDI` → backend 'Planned' → undefined ≠ 'Planlandı' → "planlanan var → 15s
refetch" hiç tetiklenmez; useTripActions.handleStatusChange `normalizeTripStatus(trip.durum)` undefined →
"statusTransitionMissing" → durum geçişi UI'da kırık. (AUDIT-174 kapsamı: +refetch +status-transition-UI.)

### AUDIT-178 — useLocationForm.normalizePlaceName Türkçe-bilinçsiz büyük harf (`charAt(0).toUpperCase()`) → kayıtlı güzergah adlarında İ/ı bozulması
- Şiddet: low
- Sınıf: i18n
- Konum: hooks/useLocationForm.ts:83-89,435-436
- Durum: confirmed
- Kanıt:
    ```js
    const normalizePlaceName = (value) => value.trim().split(/\s+/)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())  // "istanbul"→"Istanbul"
      .join(" ");
    // onSubmit: cikis_yeri: normalizePlaceName(values.cikis_yeri)  → DB'ye yazılır
    ```
  Güzergah kaydederken `normalizePlaceName` `charAt(0).toUpperCase()` ile büyütüyor; Türkçe `i`→`İ` değil
  `i`→`I` yapar → "istanbul"→"Istanbul" (yanlış). DB'ye bozuk ad yazılır; sefer-import lokasyonu ad ile
  eşlerken (AUDIT-135) "İstanbul" vs "Istanbul" uyuşmazlığı → eşleşme kaçabilir. AUDIT-074/109/170 i18n ailesi
  frontend tezahürü.
- Önerilen düzeltme: Türkçe-güvenli capitalize (`toLocaleUpperCase('tr')`/`toLocaleLowerCase('tr')`) ya da
  hiç normalize etme (kullanıcı girdisini koru); backend ile tek normalize konvansiyonu.
- Bağımlılık: AUDIT-074, AUDIT-109, AUDIT-170 (.title()/sanitize ailesi), AUDIT-135 (sefer-lokasyon eşleme).

> S8-6: hooks 22/22 örnek kalite; AUDIT-178 (low i18n). AUDIT-174 refetch+status-UI'a da uzandı.

## S8-7 — features(5) + schemas(2) — 0 yeni bulgu (AUDIT-174/165 KÖK doğrulandı)

route-lab component'leri (RouteHeatmap SVG, RouteProfileChart Recharts, RouteSimSummary, RouteSimForm) +
TripsModule temiz/saf-fonksiyonlu (heatmap projeksiyon/profil testable; XSS yok). services.ts şemaları
`.passthrough()`+optional (defansif). İz: `DashboardStatsSchema` hem entities.ts hem services.ts'te (duplike,
hafif drift — low). TripsModule bulk-approve `Promise.all` kısmi-hata yutar (low UX).

**AUDIT-174 KÖK (schemas/entities.ts):** `TripStatusSchema` Zod transform `normalizeTripStatus` undefined
dönerse `z.NEVER`+issue ile **validation FAIL** ettiriyor → backend 'Completed' → her sefer Zod-fail →
console/errorTracker spam + ham (valide edilmemiş) data; bir sefer fail edince PaginatedResponseSchema tüm
listeyi fail eder. **AUDIT-165 KÖK:** `FuelRecordSchema.durum` enum `["Bekliyor","Onaylandı"(Türkçe ı),
"Reddedildi"]` ≠ backend `'Onaylandi'`(ASCII) → yakit kaydı Zod-fail. (Yeni numara yok; 174/165 kök kanıtı.)

> S8-7: frontend MANTIK katmanı (API 32 + hooks 22 + lib/store/context + features 5 + schemas 2) TAMAM.
> Kalan: components(240) + pages(53) + layouts(5) + resources(18) + types + frontend __tests__ + S10 backend
> testler — sunum + test bulk. Frontend bulgular: AUDIT-172..178 (7). Güvenlik/kontrat yüksek kalite,
> tek sistemik high: AUDIT-174 (durum TR↔EN drift, kök entities.ts).

## S8-8 — durum-display component spot-check (TripFilters, TodaysActiveTrips, NotificationFeed) — 0 yeni bulgu (AUDIT-174 GÖRÜNÜR semptom doğrulandı)

`NotificationFeed` temiz (WS baslik/icerik React-escape, getEventConfig İngilizce event-tipi). **AUDIT-174
GÖRÜNÜR UI SEMPTOMU:** `TodaysActiveTrips` `STATUS_VARIANT` Türkçe anahtarlı (`Planlandı/Yolda/Tamamlandı/
İptal`) ama backend İngilizce `trip.durum` ('Completed') render ediyor → `STATUS_VARIANT['Completed']`
undefined → badge **gri "default"** renkle + **İngilizce "Completed" metni** gösterir (Türkçe 'Tamamlandı'
yeşil yerine). Dashboard'da kullanıcıya doğrudan yansır. `TripFilters` STATUS_TABS Türkçe → filtre backend'e
Türkçe yollar → 0-eşleşme. `STATUS_VARIANT`'ta obsolet 'Yolda' (post-0022 yok) ölü girdi. Tümü AUDIT-174.

> S8-8: AUDIT-174 artık kullanıcı-görünür UI semptomuyla (yanlış renk + İngilizce metin) kanıtlı. Yeni numara yok.

## S8-9 — güvenlik-kritik page spot-check (LoginPage, KullanicilarPage, KonfigurasyonPage) — 0 bulgu

`LoginPage` örnek: forgot-password her zaman success (user-enumeration yok), autoComplete doğru, client lockout
429'da; `ProfilePage` parola şeması güçlü (8+ büyük/küçük/rakam, strength bar — ilk 130 satır okundu, kalanı
işaretlenmedi). `KullanicilarPage` React-Query CRUD, React-escape (XSS yok). `KonfigurasyonPage` admin config
editörü tip-coerce, React-escape. Page'ler ince kompozisyon + zaten denetlenmiş hook/component'leri çağırıyor.

> S8-9: güvenlik-kritik page'ler (login/admin) temiz. Kalan page'ler ince kompozisyon (sunum bulk).
> **SUBSTANTIVE DENETİM TAMAM:** tüm backend + tüm frontend mantık/güvenlik/kontrat + güvenlik-kritik UI.
> Kalan ~850 dosya: presentational component + Türkçe-string resource + test (düşük bulgu yoğunluğu).
