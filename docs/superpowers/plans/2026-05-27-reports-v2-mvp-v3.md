# Reports v2 MVP — v3 Plan

**Tarih:** 2026-05-27
**Status:** PLAN — uygulamaya hazır
**Önceki sürüm:** `2026-05-27-reports-v2-derin-inceleme.md` (758 satır analysis)
**Tetikleyici:** Kullanıcı 2026-05-26 — yönetim+rapor sayfaları yetersiz

---

## §0 TL;DR

Reports v2 MVP — 3 yeni içgörü sayfası + Reports Studio rewrite + Sidebar
yeniden organizasyon + **PWA tam destek** (service worker + offline +
push notification).

**6 karar (kullanıcı onaylı):**
1. **MVP scope parça parça**: RV2.1 Today → RV2.2 Fleet → RV2.5 Reports
   Studio → RV2.9 Sidebar → **RV2.PWA**
2. **LLM narration**: feature flag arkasında, Groq cache 1h
3. **SMTP e-posta**: tamamen iptal — sadece manual download
4. **PWA**: full — service worker + offline + Web Push (VAPID)
5. **Dashboard → Today rename**: hibrit (`/` role-based; `/legacy-dashboard`
   3 ay korunur)
6. **Eski URL alias**: 6 ay redirect

**Tahmini iş yükü:** ~42 saat
- RV2.1 Today (9 sa)
- RV2.2 Fleet İçgörü (8 sa)
- RV2.5 Reports Studio (12 sa) — e-posta çıkarıldı, -1 sa
- RV2.9 Sidebar (3 sa)
- **RV2.PWA (10 sa)** — manifest + service worker + Web Push VAPID

**Geleceğe bırakılan (v2.1):**
- RV2.3 Şoför İK
- RV2.4 Compliance
- RV2.6 LLM narration (flag var ama Groq entegre v2.1)
- RV2.7 Insight feedback

---

## §1 6 karar — gerekçeli

### Karar 1: MVP parça parça (4+1 alt görev)

Tek seferde 42 saat teslim = hata riski. Her commit'in tek bir alt-görev
kapsayan küçük scope'u olmalı:
- RV2.1 Today (en yüksek değer — operasyon şefi)
- RV2.2 Fleet İçgörü (filo müdürü — cross-feature)
- RV2.5 Reports Studio (eski ReportsPage rewrite)
- RV2.9 Sidebar (yeni navigasyon)
- RV2.PWA (mobil + push)

### Karar 2: LLM narration flag arkasında

Groq API zaten config'de (Feature A koçluk). Cache 1h ile maliyet minimum.
**Ancak v1'de LLM çağrısı yapılmıyor** — sadece infrastructure (flag,
endpoint stub) hazırlanır. Gerçek LLM call v2.1'de.

```python
# config.py
REPORTS_V2_LLM_NARRATION_ENABLED: bool = False  # v1 default OFF
```

### Karar 3: SMTP e-posta tamamen iptal

- `report_schedules` tablosu **yaratılmaz**
- "Kaydet ve Planla" UI yok
- Saved views (RV2.7) v1'de yine yok (v2.1'e geçti)
- Sadece "Şimdi indir" (PDF/Excel/CSV) butonu

### Karar 4: PWA + Push (full)

**Stack seçimi: VAPID self-hosted** (Firebase yerine)

| Boyut | Firebase FCM | VAPID self-hosted |
|---|---|---|
| Setup | Firebase project + console | Backend'de VAPID anahtar çifti üret |
| Cost | Free tier var ama vendor lock | 0 (kendi sunucumuz) |
| iOS Safari | 16.4+ destekler (ikisi de) | 16.4+ destekler |
| Backend dep | firebase-admin SDK | pywebpush + cryptography (zaten var) |
| Token yönetimi | FCM token (Firebase tarafı) | endpoint URL + p256dh + auth (browser native) |

VAPID önerim: 3rd-party dependency yok, KVKK-friendly.

### Karar 5: Hibrit `/` route

```tsx
function HomePage() {
    const { user } = useAuth()
    const canSeeTriage = ['admin', 'super_admin', 'fleet_manager'].includes(user?.role)
    return canSeeTriage ? <TodayPage /> : <DashboardPage />  // mevcut
}
```

`/legacy-dashboard` route'u 3 ay korunur (kullanıcı eski versiyonu görmek
isterse).

### Karar 6: 6 ay URL alias

Redirect'ler:
- `/admin` → `/insights/fleet` (eski admin BI içeriği yeni Fleet İçgörü'de)
- `/admin/bakim` → `/maintenance` (iş süreç ana menüye)
- `/admin/ml` → `/admin/system/ml` (sistem alt-grubuna)
- `/admin/saglik` → `/admin/system/health`
- `/admin/veri` → `/admin/system/data`
- `/admin/bildirimler` → `/admin/system/notifications`
- `/admin/konfigurasyon` → `/admin/system/config`
- `/admin/kullanicilar` → `/admin/system/users`

6 ay sonra alias'lar kaldırılır.

---

## §2 Mimari özet (öncül inceleme dokümanından)

3 katmanlı yapı:

```
┌──────────────────────────────────────────────────┐
│ Sidebar                                           │
├──────────────────────────────────────────────────┤
│ 📊 Bugün       (RV2.1 — Today, triage)           │
│ 🎯 Filo İçgörü (RV2.2)                            │
│ 👥 Şoför İK    [v2.1]                             │
│ ✅ Uyum Defteri[v2.1]                             │
│ 🚀 Strategic   (E.8 var)                          │
│ 📄 Raporlar    (RV2.5 — Studio rewrite)           │
├──────────────────────────────────────────────────┤
│ Operasyonel sayfalar (Trips, Fuel, Fleet, ...)   │
├──────────────────────────────────────────────────┤
│ ⚙ Sistem       (RV2.9 — Admin yeniden)           │
└──────────────────────────────────────────────────┘
```

---

## §3 RV2.1 — Today (Triage) sayfası

### 3.1 Backend: `GET /reports/today/triage`

```python
# app/api/v1/endpoints/today_triage.py (NEW)
# app/schemas/today.py (NEW)
# app/core/services/triage_aggregator.py (NEW)

@router.get("/triage", response_model=TodayTriageResponse)
async def get_today_triage(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> TodayTriageResponse:
    """Bugünün acil + bekleyen aksiyonları (öncelik sıralı)."""
```

**Veri kaynakları (tek SQL ve in-memory aggregat):**

```sql
-- 1. Açık anomaliler (severity = critical öncelik)
SELECT id, severity, tip, sapma_yuzde, tarih, plaka
FROM anomalies WHERE resolved_at IS NULL
  AND tarih >= CURRENT_DATE - INTERVAL '7 days'

-- 2. Bakım gecikmeli + 7g içinde olan (D.1 predictions)
SELECT ... FROM compute_bus_factor() veya D.1 cached

-- 3. Aktif sefer (durum='Yolda')
SELECT id, plaka, sofor_adi, ... FROM seferler WHERE durum='Yolda'

-- 4. Bekleyen Telegram onay (varsa)
-- 5. Açık fuel investigation (B)
```

**Response schema:**

```python
class TriageItem(BaseModel):
    id: str                         # "anomaly:42", "maintenance:7"
    category: Literal[
        "anomaly", "maintenance", "investigation",
        "telegram_approval", "active_trip"
    ]
    severity: Literal["critical", "high", "medium", "low"]
    title: str                      # "Yakıt sapma %35"
    subtitle: str                   # "34 ABC 123 — bugün"
    timestamp: datetime
    actions: List[TriageAction]     # [{label: "İncele", url: "/alerts/42"}]


class TodayTriageResponse(BaseModel):
    critical_count: int
    pending_count: int
    items: List[TriageItem]         # priority sorted (critical first)
    active_trips_count: int
    completed_today_count: int
```

### 3.2 Frontend: `TodayPage.tsx`

```tsx
// pages/TodayPage.tsx (NEW)
// components/today/TriageItem.tsx (NEW)
// components/today/QuickActionsBar.tsx (NEW)

const tabs: Array<{ id: TriageCategory | 'all'; label: string }> = [
    { id: 'all', label: 'Tümü' },
    { id: 'anomaly', label: 'Anomali' },
    { id: 'maintenance', label: 'Bakım' },
    { id: 'investigation', label: 'Soruşturma' },
]
```

Layout:
```
┌──────────────────────────────────────────┐
│ Bugün — 27 Mayıs 2026                    │
│ [tabs: Tümü | Anomali | Bakım | ...]     │
├──────────────────────────────────────────┤
│ ⚠ 3 Acil Eylem                          │
│ ┌──────────────────────────────────────┐ │
│ │ [critical] Yakıt sapma %35           │ │
│ │ 34 ABC 123 — 2 saat önce             │ │
│ │ [İncele] [Soruşturma Aç] [Çöz]       │ │
│ └──────────────────────────────────────┘ │
│ ┌──────────────────────────────────────┐ │
│ │ [high] PERIYODIK bakım gecikti       │ │
│ │ 06 XYZ 789 — 5 gün gecikme           │ │
│ │ [Planla] [Atla]                      │ │
│ └──────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│ 📋 7 Bekleyen Aksiyon (sırada)          │
│ [list...]                                │
├──────────────────────────────────────────┤
│ Quick Actions                            │
│ [Sefer Planla] [Anomali] [Şoför]         │
│                                          │
│ Aktif: 23 sefer · Bugün tamamlanan: 12   │
└──────────────────────────────────────────┘
```

### 3.3 Testler

- 5 backend unit test (FakeSession + farklı senaryolar)
- 4 vitest (TodayPage render + tab switch + quick action click)

---

## §4 RV2.2 — Fleet İçgörü sayfası

### 4.1 Backend: `GET /reports/insights/fleet`

Yeni endpoint **gerek yok** — mevcut E endpoint'lerinin client-side
composition'u yeterli:

- `/reports/executive/kpi` (FVI)
- `/reports/executive/cross-feature` (D.4+A.5+B)
- `/reports/executive/bus-factor`
- `/drivers/{id}/score-breakdown` (top/bottom performer için)

**Sadece 1 yeni endpoint** — period-over-period karşılaştırma:

```python
@router.get("/insights/fleet/comparison")
async def get_fleet_comparison(
    period: Literal["week", "month"] = "month",
    compare_with: Literal["last_period"] = "last_period",
) -> FleetComparisonResponse:
    """Bu periyot vs geçen periyot karşılaştırma (yakıt, sefer, anomali)."""
```

### 4.2 Frontend: `FleetInsightsPage.tsx`

Layout:
```
┌──────────────────────────────────────────────┐
│ Filo İçgörü — Mayıs 2026                     │
│ [period: Bu Hafta | Bu Ay] vs [Geçen]        │
├──────────────────────────────────────────────┤
│ FleetEfficiencyCard (E.8 reuse)              │
├──────────────────────────────────────────────┤
│ PeriodComparison (yeni)                      │
│ Yakıt:    45,820 L  (-2.1% vs geçen)         │
│ Maliyet:  ₺2.3M    (-1.8%)                   │
│ Anomali:  12       (+25%)                    │
├──────────────────────────────────────────────┤
│ CrossFeatureSavings (E.8 reuse)              │
├──────────────────────────────────────────────┤
│ Top 3 Performer / Bottom 3 (anonim drill)    │
└──────────────────────────────────────────────┘
```

### 4.3 Testler

- 3 backend unit (comparison hesabı, empty period, edge case)
- 3 vitest (page render + period switch + comparison fetch)

---

## §5 RV2.5 — Reports Studio (rewrite)

### 5.1 Backend: yeni endpoint yok (mevcut report'lar reuse)

Mevcut PDF/Excel endpoint'leri çağrılır. Yeni dosya:

```python
# app/api/v1/endpoints/reports_studio.py (NEW)
# yeni endpoint: rapor şablonları listesi (statik)

@router.get("/studio/templates")
async def list_templates() -> List[TemplateMeta]:
    """6 statik şablon meta listesi."""
```

Şablonlar:
1. **CEO Aylık 1-Pager** — E.9 PDF reuse
2. **Filo Müdürü Haftalık** — yeni şablon (FVI + cross-feature + top driver)
3. **Yakıt Maliyet Analizi** — eski cost/period reuse
4. **Araç Karşılaştırma** — eski vehicle_comparison reuse
5. **Karbon Raporu** — E.3 reuse + 12 ay özet
6. **What-if Sonucu** — kullanıcının çalıştırdığı senaryonun PDF'i

### 5.2 Frontend: `ReportsStudioPage.tsx`

Tek dosya rewrite. Eski ReportsPage.tsx 245 satır → yeni ~400 satır.

Layout:
```
┌─────────────────────────────────────────────────┐
│ Rapor Stüdyosu                                  │
├─────────────────────────────────────────────────┤
│ Şablon Kütüphanesi (kart galerisi)              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │ CEO 1-P  │ │ Haftalık │ │ Maliyet  │         │
│ │ [PDF]    │ │ [PDF/XL] │ │ [PDF/XL] │         │
│ └──────────┘ └──────────┘ └──────────┘         │
├─────────────────────────────────────────────────┤
│ Yapılandırma (şablon seçildiğinde)              │
│ Periyot: [Bu ay ▼]  Format: [PDF ▼]             │
│ Filtre: [Tüm filo ▼]                            │
│                                                  │
│ [Önizle] [İndir]                                │
└─────────────────────────────────────────────────┘
```

### 5.3 Testler

- 1 backend unit (template listesi)
- 5 vitest (template seçimi, format değiştirme, download click, error)

---

## §6 RV2.9 — Sidebar restructure

### 6.1 EliteLayout.tsx değişiklikleri

```tsx
const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
const canSeeTriage = isAdmin || user?.role === 'fleet_manager';
const canSeeInsights = canSeeTriage;
const canSeeExecutive = canSeeTriage;

const navGroups = [
    {
        label: null,
        items: [
            canSeeTriage
                ? { icon: ListChecks, label: 'Bugün', path: '/today' }
                : { icon: BarChart3, label: 'Panel', path: '/' },
        ],
    },
    {
        label: 'Operasyon',
        items: [
            { icon: Activity, label: 'Seferler', path: '/trips' },
            { icon: Radio, label: 'Canlı Takip', path: '/monitoring' },
            { icon: Fuel, label: 'Yakıt', path: '/fuel' },
            { icon: Wrench, label: 'Bakım', path: '/maintenance' },  // YENİ — admin/bakim taşındı
        ],
    },
    {
        label: 'Filo',
        items: [/* aynı */],
    },
    {
        label: 'İçgörü',  // YENİ grup
        items: [
            ...(canSeeInsights ? [
                { icon: Sparkles, label: 'Filo İçgörü', path: '/insights/fleet' },
            ] : []),
            { icon: AlertTriangle, label: 'Anomaliler', path: '/alerts' },
            { icon: BrainCircuit, label: 'ML Tahminler', path: '/predictions' },
            { icon: GraduationCap, label: 'Koçluk', path: '/coaching' },
            ...(canSeeExecutive ? [
                { icon: LineChart, label: 'Strategic Cockpit', path: '/executive' },
            ] : []),
            { icon: FileText, label: 'Rapor Stüdyosu', path: '/reports' },
        ],
    },
    ...(isAdmin ? [{
        label: 'Sistem',
        items: [
            { icon: Shield, label: 'Sistem Yönetimi', path: '/admin/system' },
        ],
    }] : []),
];
```

### 6.2 App.tsx route aliasları

```tsx
// Eski path'lar 6 ay redirect
<Route path="/admin" element={<Navigate to="/insights/fleet" replace />} />
<Route path="/admin/bakim" element={<Navigate to="/maintenance" replace />} />
<Route path="/admin/ml" element={<Navigate to="/admin/system/ml" replace />} />
{/* ... vb. */}

// Yeni route'lar
<Route path="/today" element={<TodayPage />} />
<Route path="/insights/fleet" element={<FleetInsightsPage />} />
<Route path="/maintenance" element={<MaintenancePage />} />  {/* BakimPage taşındı */}
<Route path="/admin/system">
    <Route path="ml" element={<MLYonetimPage />} />
    <Route path="health" element={<SistemSaglikPage />} />
    {/* ... */}
</Route>
```

### 6.3 Testler

- 4 vitest (sidebar groups, role-based visibility, redirect tests)

---

## §7 RV2.PWA — Tam PWA + Web Push (VAPID)

### 7.1 Manifest + Service Worker

**Paketler:**
```bash
npm install -D vite-plugin-pwa workbox-window
```

**vite.config.ts değişikliği:**

```ts
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
    plugins: [
        react(),
        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.svg', 'icons/*.png'],
            manifest: {
                name: 'LojiNext',
                short_name: 'LojiNext',
                description: 'AI-powered TIR fleet management',
                theme_color: '#1e40af',
                background_color: '#f8fafc',
                display: 'standalone',
                start_url: '/today',
                icons: [
                    { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
                    { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
                    {
                        src: '/icons/icon-maskable-512.png',
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'maskable',
                    },
                ],
            },
            workbox: {
                runtimeCaching: [
                    {
                        urlPattern: /\/api\/v1\/.*/,
                        handler: 'NetworkFirst',
                        options: {
                            cacheName: 'api-cache',
                            networkTimeoutSeconds: 5,
                            expiration: { maxEntries: 100, maxAgeSeconds: 60 * 5 },
                        },
                    },
                ],
            },
        }),
    ],
})
```

### 7.2 Web Push (VAPID) — Backend

**Yeni paket:**
```bash
pip install pywebpush
```

**Yeni migration:**

```sql
-- alembic/versions/0016_push_subscriptions.py
CREATE TABLE push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES kullanicilar(id) ON DELETE CASCADE NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);
CREATE INDEX ix_push_user_id ON push_subscriptions(user_id);
```

**VAPID anahtar üretimi (manuel, tek seferlik):**

```bash
# scripts/generate_vapid_keys.py (NEW)
python -m py_vapid generate
# .env'e ekle:
# VAPID_PRIVATE_KEY=...
# VAPID_PUBLIC_KEY=...
# VAPID_SUBJECT=mailto:admin@lojinext.com
```

**Config:**
```python
# app/config.py
VAPID_PUBLIC_KEY: str = ""
VAPID_PRIVATE_KEY: str = ""
VAPID_SUBJECT: str = ""
PUSH_NOTIFICATION_ENABLED: bool = False  # default OFF; keys set edilince True
```

**Yeni endpoint'ler:**

```python
# app/api/v1/endpoints/push.py (NEW)

@router.get("/push/vapid-public-key")
async def get_vapid_public_key(...) -> dict:
    """Frontend subscribe için public key."""
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/push/subscribe")
async def subscribe(payload: PushSubscriptionRequest, ...):
    """Frontend subscription'ı kaydet."""

@router.delete("/push/subscribe")
async def unsubscribe(...):
    """Subscription sil."""

@router.post("/push/test")  # sadece admin
async def send_test_push(...):
    """Test push gönder (debugging)."""
```

**Push send servisi:**

```python
# app/core/services/push_sender.py (NEW)

async def send_push_to_user(
    user_id: int, title: str, body: str, url: Optional[str] = None
) -> int:
    """Bir kullanıcının tüm subscription'larına push gönder.
    Returns: gönderilen sayı.
    """
    # SELECT subscriptions WHERE user_id
    # for each: webpush.send(...) with VAPID
    # 410 Gone → subscription expired, delete
```

**B.5 ile entegrasyon:**

```python
# investigations.py POST endpoint sonunda:
if classification.suspicion_level == "high":
    await send_push_to_subscribed_admins(
        title="🚨 Yüksek Şüpheli Yakıt Olayı",
        body=f"Soruşturma #{inv.id} — score {classification.suspicion_score:.2f}",
        url=f"/alerts?inv={inv.id}",
    )
```

### 7.3 Web Push — Frontend

**Service worker dosyası:**

```ts
// frontend/src/sw-push.ts (NEW)
self.addEventListener('push', (event) => {
    const data = event.data?.json() ?? {}
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/icons/icon-192.png',
            badge: '/icons/badge-72.png',
            data: { url: data.url },
        }),
    )
})

self.addEventListener('notificationclick', (event) => {
    event.notification.close()
    const url = event.notification.data?.url ?? '/today'
    event.waitUntil(clients.openWindow(url))
})
```

**Permission flow + subscription:**

```tsx
// frontend/src/hooks/usePushNotifications.ts (NEW)
export function usePushNotifications() {
    const enable = async () => {
        // 1. Permission iste
        const perm = await Notification.requestPermission()
        if (perm !== 'granted') return false

        // 2. Service worker registration
        const reg = await navigator.serviceWorker.ready

        // 3. VAPID public key al
        const { public_key } = await axios.get('/push/vapid-public-key')

        // 4. Subscribe
        const sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(public_key),
        })

        // 5. Backend'e kaydet
        await axios.post('/push/subscribe', sub.toJSON())
        return true
    }

    return { enable, ... }
}
```

**Settings sayfasında toggle:**

```tsx
// pages/ProfilePage.tsx içine ekle
<section>
    <h3>Bildirimler</h3>
    <Switch
        checked={pushEnabled}
        onChange={togglePush}
        label="Mobil push bildirimleri"
    />
</section>
```

### 7.4 Icon set hazırlama

Mevcut `frontend/public/icons/` klasörü yoksa oluşturulur:
- `icon-192.png` (192×192)
- `icon-512.png` (512×512)
- `icon-maskable-512.png` (safe-zone padding ile)
- `badge-72.png` (notification badge)
- `favicon.svg` (mevcut)

Kullanıcıdan logo alınacak; yoksa LojiNext "L" harfi + theme color
fallback.

### 7.5 Testler

- 3 backend unit test (subscribe, unsubscribe, send mock)
- 2 vitest (usePushNotifications hook + permission flow)
- 1 manuel test: HTTPS sunucuda iOS Safari 16.4+ ve Chrome'da
  notification görünüm doğrulaması (CI'de değil)

---

## §8 Konfig + flag'ler

```python
# app/config.py — yeni alanlar
REPORTS_V2_ENABLED: bool = True
REPORTS_V2_LLM_NARRATION_ENABLED: bool = False  # v1'de OFF
VAPID_PUBLIC_KEY: str = ""
VAPID_PRIVATE_KEY: str = ""
VAPID_SUBJECT: str = ""
PUSH_NOTIFICATION_ENABLED: bool = False  # VAPID set olunca True
```

---

## §9 Migration

```sql
-- alembic/versions/0016_push_subscriptions.py
-- Yalnız 1 tablo (push_subscriptions). schedule + saved_views v2.1'e bırakıldı.

CREATE TABLE push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES kullanicilar(id) ON DELETE CASCADE NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);
CREATE INDEX ix_push_user_id ON push_subscriptions(user_id);
```

---

## §10 Yol haritası

| Sıra | Alt görev | Çıktı | Test | Tahmini |
|---|---|---|---|---|
| RV2.1 | Today sayfası + endpoint | TriageAggregator + TodayPage | 5 unit + 4 vitest | 9 sa |
| RV2.2 | Fleet İçgörü | comparison endpoint + FleetInsightsPage | 3 unit + 3 vitest | 8 sa |
| RV2.5 | Reports Studio rewrite | templates endpoint + ReportsStudioPage | 1 unit + 5 vitest | 12 sa |
| RV2.9 | Sidebar + redirect | EliteLayout + App.tsx + alias'lar | 4 vitest | 3 sa |
| RV2.PWA | Manifest + SW + Web Push (VAPID) | migration + push.py + sw-push.ts + hook | 3 unit + 2 vitest + manuel | 10 sa |

**Toplam:** ~42 saat.

**Gating:**
- RV2.1, RV2.2, RV2.5 paralel başlatılabilir (bağımsız endpoint'ler)
- RV2.9 hepsinden sonra (yeni sayfaları sidebar'a bağlar)
- RV2.PWA bağımsız ama HTTPS gerekiyor (dev'de localhost ile çalışır)

---

## §11 Riskler + azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| `/admin` rotası başkalarına 301 redirect şaşırtır | UX şikayet | Sidebar'a notification "Yeni: Fleet İçgörü" rozeti |
| Triage queue çok ağır (100+ item) | Sayfa yavaş | Tek SQL ile limit 50; "Daha fazla" pagination |
| LLM narration v2.1'e bırakıldı ama UI'da boş kalır | UX uyarısı | v1'de statik özet metin fallback |
| PWA iOS Safari < 16.4 desteklemiyor | Sınırlı erişim | UI'da "iOS 16.4+ önerilir" notice |
| VAPID anahtar yönetimi (private key güvenliği) | Güvenlik | .env'de tutulur, Sentry/log'a sızmaz; rotation script |
| Push permission reddedildi | Bildirim yok | "Bildirimler kapalı" rozeti + manuel açma linki |
| Service worker cache stale data gösterir | Yanıltıcı | NetworkFirst + 5sn timeout; en güncel veriye öncelik |
| Eski URL alias'ları 6 ay sonra unutulur | Teknik borç | TODO + commit hash yorum + Q4 review |
| Push spam (her küçük anomali) | Kullanıcı kapatır | Sadece `severity='critical'` + per-kullanıcı 24sa cooldown |

---

## §12 PII + güvenlik

- **Triage item'ları**: plaka + sapma % içerir (admin için OK)
- **Top performer şoför**: anonim drill (RV2.2) — score + km, ad/id ayrı endpoint
- **Push notification body**: max 100 karakter; PII'siz "Anomali #42"
  formatında — şoför adı gönderilmez
- **VAPID private key**: env var; loglara yazılmaz; audit erişim
- **Push subscription**: kullanıcı kendi kayıtlarını silebilir (`DELETE /push/subscribe`)
- **Audit log**:
  - `today_triage_viewed`
  - `report_template_downloaded`
  - `push_subscribed`, `push_unsubscribed`
  - `push_sent` (success count)

---

## §13 Acceptance criteria

### Genel
- [ ] `REPORTS_V2_ENABLED=False` → tüm yeni route'lar 503 / sidebar gizli
- [ ] Eski URL'ler 6 ay redirect (301)
- [ ] Tüm yeni unit/vitest yeşil
- [ ] `ruff check --ignore=E501`, `tsc --noEmit`, `vite build` clean

### RV2.1 Today
- [ ] `GET /reports/today/triage` 200 + critical-first sorted
- [ ] Empty fleet → boş items + counts=0
- [ ] Quick actions navigate doğru sayfaya
- [ ] Critical badge görsel olarak ayırt edilir

### RV2.2 Fleet İçgörü
- [ ] `GET /reports/insights/fleet/comparison?period=week` → 200 + delta'lar
- [ ] FVI card E.8'den reuse (zaten test edildi)
- [ ] Top/bottom performer anonim (score + km only)

### RV2.5 Reports Studio
- [ ] Template kart galerisi
- [ ] PDF indirme E.9 reuse
- [ ] Excel indirme (mevcut endpoint reuse)
- [ ] "Önizle" modal

### RV2.9 Sidebar
- [ ] Yeni gruplar (İçgörü) + role-based gizleme
- [ ] Eski admin/* rotaları redirect
- [ ] Bakım `/maintenance`'a taşındı

### RV2.PWA
- [ ] `manifest.json` doğru theme color + 3 icon
- [ ] Service worker registered (chrome dev tools)
- [ ] Offline'da `/today` yüklenir (network-first stale)
- [ ] VAPID keys env'de set olunca push endpoint 200 döner
- [ ] B.5 critical alarm → push notification görünür
- [ ] Permission reddedildi → graceful UI mesajı

---

## §14 Açık notlar (v2.1'e ertelenen)

1. **RV2.3 Şoför İK sayfası** — aylık karne + A.5 effectiveness drill
2. **RV2.4 Compliance sayfası** — E.4 reuse + audit log timeline + yıllık PDF
3. **RV2.6 LLM narration** — Groq aktif çağrı (flag açılınca)
4. **RV2.7 Insight feedback** — thumbs up/down tablosu
5. **RV2.8 Saved views + e-posta** — kullanıcı bookmark + Celery schedule
6. **PWA Firebase migration** — VAPID'den FCM'e geçiş istenirse
7. **iOS background push** — iOS 16.4+ değilse "browser açık iken" yetinmek
8. **Compliance audit retention** — KVKK 90g/365g tartışılacak
