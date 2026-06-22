# Frontend Tam Yeniden Yazım Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend'in tüm kapasitesini yüzeyine çıkaran derin bir lojistik ops dashboard; Dashboard, Monitoring (WebSocket bildirimler), Anomaliler, ML Tahminler sayfaları eklenir; mevcut sayfalar grafiklerle derinleştirilir; "Elite Zen" branding temizlenir.

**Architecture:** React Query + Recharts + Tailwind stack korunur. Yeni sayfalar mevcut servis katmanını (`services/api/`) kullanır; iki yeni servis dosyası eklenir (`anomaly-service.ts`, `prediction-service.ts` güncellenir). WebSocket bağlantısı JWT token ile doğrudan `/api/v1/admin/ws/live?token=<JWT>` adresine açılır.

**Tech Stack:** React 18, TypeScript, React Query v5, Recharts, Framer Motion, Tailwind CSS, Lucide React, Vitest + Testing Library

---

## Dosya Haritası

### Oluşturulacak
```
frontend/src/
  services/api/anomaly-service.ts          # GET /anomalies/fleet/insights
  pages/DashboardPage.tsx                   # Ana dashboard
  pages/MonitoringPage.tsx                  # WebSocket bildirimler
  pages/AlertsPage.tsx                      # Anomali/uyarı listesi
  pages/PredictionsPage.tsx                 # ML tahminler + XAI
  components/dashboard/KpiRow.tsx           # 4 KPI kartı
  components/dashboard/ConsumptionChart.tsx # Recharts LineChart
  components/dashboard/AnomalyWidget.tsx    # Son 5 anomali
  components/dashboard/RecentTripsTable.tsx # Aktif seferler
  components/monitoring/useMonitoringSocket.ts # WebSocket hook
  components/monitoring/ConnectionStatus.tsx   # Bağlantı göstergesi
  components/monitoring/NotificationFeed.tsx   # Bildirim listesi
  components/alerts/AnomalyTable.tsx        # Filtrelenebilir tablo
  components/alerts/SeverityFilter.tsx      # Severity tab bar
  components/predictions/EnsembleStatusCard.tsx # Model ağırlıkları
  components/predictions/AccuracyChart.tsx  # Gerçek vs Tahmin AreaChart
  components/predictions/XaiPanel.tsx       # XAI form + sonuç
  components/predictions/MetricCards.tsx    # MAE, RMSE kartları
```

### Değiştirilecek
```
frontend/src/
  layouts/EliteLayout.tsx                   # Branding + grouped nav
  App.tsx                                   # Yeni route'lar
  services/api/prediction-service.ts        # getEnsembleStatus() eklenir
  pages/FuelPage.tsx                        # Tüketim trendi chart eklenir
  pages/ReportsPage.tsx                     # Vehicle comparison BarChart
  pages/admin/OverviewPage.tsx              # Liste → LineChart
```

---

## Task 1: Foundation — Branding ve Routing

**Files:**
- Modify: `frontend/src/layouts/EliteLayout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: EliteLayout'ta "Elite Zen" yazısını kaldır, nav gruplarını ekle**

`frontend/src/layouts/EliteLayout.tsx` dosyasını aç.

**Değişiklik 1:** Satır 97 — `"Elite Zen"` span'ini kaldır:
```tsx
// ÖNCE:
<span className="text-[10px] font-bold text-accent uppercase tracking-[0.2em] mt-1">Elite Zen</span>

// SONRA: Bu satırı tamamen sil
```

**Değişiklik 2:** `navItems` dizisini silin, aşağıdaki gruplu yapıyla değiştirin (import'lara `Activity, AlertTriangle, BrainCircuit` ekle):

```tsx
import {
  BarChart3, Truck, Fuel, MapPin, FileText, LogOut,
  Menu, X, Bell, Moon, Sun, User, Shield,
  Activity, AlertTriangle, BrainCircuit,
} from 'lucide-react';
```

```tsx
const navGroups = [
  {
    label: null,
    items: [
      { icon: BarChart3, label: 'Dashboard', path: '/' },
    ],
  },
  {
    label: 'Operasyon',
    items: [
      { icon: Activity, label: t('dashboard.active_trips', 'Seferler'), path: '/trips' },
      { icon: Activity, label: 'Canlı Takip', path: '/monitoring' },
      { icon: Fuel, label: t('fuel.title', 'Yakıt'), path: '/fuel' },
    ],
  },
  {
    label: 'Filo',
    items: [
      { icon: Truck, label: t('dashboard.total_vehicles', 'Filo'), path: '/fleet' },
      { icon: MapPin, label: t('locations.title', 'Lokasyonlar'), path: '/locations' },
    ],
  },
  {
    label: 'Analitik',
    items: [
      { icon: AlertTriangle, label: 'Anomaliler', path: '/alerts' },
      { icon: BrainCircuit, label: 'ML Tahminler', path: '/predictions' },
      { icon: FileText, label: t('reports.title', 'Raporlar'), path: '/reports' },
    ],
  },
  ...(isAdmin ? [{
    label: 'Sistem',
    items: [{ icon: Shield, label: t('admin.title', 'Yönetim'), path: '/admin' }],
  }] : []),
];
```

**Değişiklik 3:** Nav render bölümünü `navItems.map` yerine gruplı yapıyla değiştir:

```tsx
<nav className="flex-1 space-y-4">
  {navGroups.map((group) => (
    <div key={group.label ?? 'top'}>
      {group.label && (
        <p className="px-4 mb-1 text-[10px] font-bold uppercase tracking-[0.2em] text-tertiary">
          {group.label}
        </p>
      )}
      <div className="space-y-0.5">
        {group.items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group',
                isActive
                  ? 'bg-accent text-white shadow-md shadow-accent/20'
                  : 'text-secondary hover:bg-accent-soft hover:text-accent',
              ].join(' ')
            }
          >
            <item.icon size={18} className="shrink-0" />
            <span className="font-medium text-sm">{item.label}</span>
          </NavLink>
        ))}
      </div>
    </div>
  ))}
</nav>
```

- [ ] **Step 2: App.tsx'e yeni route'ları ekle**

`frontend/src/App.tsx` dosyasını aç.

Lazy import'ları ekle:
```tsx
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const MonitoringPage = lazy(() => import('./pages/MonitoringPage'))
const AlertsPage = lazy(() => import('./pages/AlertsPage'))
const PredictionsPage = lazy(() => import('./pages/PredictionsPage'))
```

Route'ları güncelle — `<Route path="/" ...>` bölümünde:
```tsx
<Route path="/" element={<DashboardPage />} />
<Route path="/monitoring" element={<MonitoringPage />} />
<Route path="/alerts" element={<AlertsPage />} />
<Route path="/predictions" element={<PredictionsPage />} />
// Eski redirect'leri sil:
// <Route path="/dashboard" element={<Navigate to="/trips" replace />} />
// <Route path="/command-center" element={<Navigate to="/trips" replace />} />
// <Route path="/intelligence" element={<Navigate to="/trips" replace />} />
// <Route path="/monitoring" element={<Navigate to="/trips" replace />} />
// <Route path="/efficiency" element={<Navigate to="/trips" replace />} />
// <Route path="/alerts" element={<Navigate to="/trips" replace />} />
// Korun: /trips, /fuel, /fleet, /locations, /reports, /profile, /admin/*
```

- [ ] **Step 3: Geçici stub sayfaları oluştur (test için)**

```tsx
// frontend/src/pages/DashboardPage.tsx  — geçici stub
export default function DashboardPage() {
  return <div data-testid="dashboard-page"><h1>Dashboard</h1></div>
}
```
Aynısını `MonitoringPage.tsx`, `AlertsPage.tsx`, `PredictionsPage.tsx` için yap (sadece `data-testid` farklı).

- [ ] **Step 4: Smoke testini çalıştır**

```bash
cd frontend && npx vitest --run src/pages/__tests__/smoke.test.ts
```
Beklenen: PASS (mevcut smoke test'ler geçmeli; yeni sayfalar stub olduğu için render error vermemeli).

- [ ] **Step 5: Commit**
```bash
git add frontend/src/layouts/EliteLayout.tsx frontend/src/App.tsx \
  frontend/src/pages/DashboardPage.tsx frontend/src/pages/MonitoringPage.tsx \
  frontend/src/pages/AlertsPage.tsx frontend/src/pages/PredictionsPage.tsx
git commit -m "feat: add grouped nav, remove Elite Zen, stub new pages"
```

---

## Task 2: Anomaly Service

**Files:**
- Create: `frontend/src/services/api/anomaly-service.ts`

Backend endpoint: `GET /anomalies/fleet/insights?days=30`
Response shape: `{status: "success", data: {leakage: LeakageItem[], maintenance: MaintenanceCandidate[]}}`

- [ ] **Step 1: Test dosyasını yaz**

```ts
// frontend/src/services/api/__tests__/anomaly-service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axiosInstance from '../axios-instance'

vi.mock('../axios-instance', () => ({
  default: { get: vi.fn() },
}))

const mockedGet = vi.mocked(axiosInstance.get)

describe('anomalyService', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getFleetInsights calls correct endpoint', async () => {
    mockedGet.mockResolvedValueOnce({
      data: { status: 'success', data: { leakage: [], maintenance: [] } },
    })
    const { anomalyService } = await import('../anomaly-service')
    const result = await anomalyService.getFleetInsights(30)
    expect(mockedGet).toHaveBeenCalledWith('/anomalies/fleet/insights', { params: { days: 30 } })
    expect(result.leakage).toEqual([])
    expect(result.maintenance).toEqual([])
  })
})
```

- [ ] **Step 2: Testi çalıştır — FAIL bekleniyor**
```bash
cd frontend && npx vitest --run src/services/api/__tests__/anomaly-service.test.ts
```
Beklenen: FAIL — "Cannot find module '../anomaly-service'"

- [ ] **Step 3: Servisi yaz**

```ts
// frontend/src/services/api/anomaly-service.ts
import axiosInstance from './axios-instance';

export interface LeakageItem {
  arac_id: number;
  plaka?: string;
  ortalama_sapma?: number;
  sefer_sayisi?: number;
  tahmini_kayip_lt?: number;
}

export interface MaintenanceCandidate {
  arac_id: number;
  plaka?: string;
  toplam_km?: number;
  son_bakim_km?: number;
  fark_km?: number;
}

export interface FleetInsightsData {
  leakage: LeakageItem[];
  maintenance: MaintenanceCandidate[];
}

export const anomalyService = {
  getFleetInsights: async (days: number = 30): Promise<FleetInsightsData> => {
    const response = await axiosInstance.get<{ status: string; data: FleetInsightsData }>(
      '/anomalies/fleet/insights',
      { params: { days } },
    );
    return response.data.data;
  },
};
```

- [ ] **Step 4: Testi çalıştır — PASS bekleniyor**
```bash
cd frontend && npx vitest --run src/services/api/__tests__/anomaly-service.test.ts
```
Beklenen: PASS

- [ ] **Step 5: Commit**
```bash
git add frontend/src/services/api/anomaly-service.ts \
  frontend/src/services/api/__tests__/anomaly-service.test.ts
git commit -m "feat: add anomaly service for fleet insights"
```

---

## Task 3: Prediction Service Güncellemesi

**Files:**
- Modify: `frontend/src/services/api/prediction-service.ts`

Backend endpoint: `GET /predictions/ensemble/status`
Response: `{models: {physics: bool, lightgbm: bool, ...}, weights: {physics: number, lightgbm: number, ...}, total_models: number}`

- [ ] **Step 1: Mevcut servis testini güncelle**

`frontend/src/services/api/__tests__/` altında prediction ile ilgili test yoksa yeni dosya oluştur:

```ts
// frontend/src/services/api/__tests__/prediction-service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axiosInstance from '../axios-instance'

vi.mock('../axios-instance', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
const mockedGet = vi.mocked(axiosInstance.get)

describe('predictionService.getEnsembleStatus', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls /predictions/ensemble/status', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        models: { physics: true, lightgbm: false },
        weights: { physics: 0.8, lightgbm: 0.05 },
        total_models: 1,
      },
    })
    const { predictionService } = await import('../prediction-service')
    const result = await predictionService.getEnsembleStatus()
    expect(mockedGet).toHaveBeenCalledWith('/predictions/ensemble/status')
    expect(result.weights.physics).toBe(0.8)
  })
})
```

- [ ] **Step 2: Testi çalıştır — FAIL bekleniyor**
```bash
cd frontend && npx vitest --run src/services/api/__tests__/prediction-service.test.ts
```
Beklenen: FAIL — `predictionService.getEnsembleStatus is not a function`

- [ ] **Step 3: prediction-service.ts'e eksik tipleri ve metodu ekle**

Dosyanın başına interface ekle:
```ts
export interface EnsembleStatusResponse {
  models: Record<string, boolean>;
  weights: Record<string, number>;
  sklearn_available: boolean;
  lightgbm_available: boolean;
  xgboost_available: boolean;
  total_models: number;
}

export interface PredictionExplainRequest {
  arac_id: number;
  mesafe_km: number;
  ton?: number;
  ascent_m?: number;
  descent_m?: number;
  flat_distance_km?: number;
  sofor_id?: number;
}
```

`predictionService` objesine metodu ekle:
```ts
getEnsembleStatus: async (): Promise<EnsembleStatusResponse> => {
  const response = await axiosInstance.get<EnsembleStatusResponse>('/predictions/ensemble/status');
  return response.data;
},
```

- [ ] **Step 4: Testi çalıştır — PASS bekleniyor**
```bash
cd frontend && npx vitest --run src/services/api/__tests__/prediction-service.test.ts
```

- [ ] **Step 5: Commit**
```bash
git add frontend/src/services/api/prediction-service.ts \
  frontend/src/services/api/__tests__/prediction-service.test.ts
git commit -m "feat: add getEnsembleStatus to prediction service"
```

---

## Task 4: Dashboard Sayfası

**Files:**
- Create: `frontend/src/components/dashboard/KpiRow.tsx`
- Create: `frontend/src/components/dashboard/ConsumptionChart.tsx`
- Create: `frontend/src/components/dashboard/AnomalyWidget.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx` (stub'u değiştir)
- Create: `frontend/src/pages/__tests__/DashboardPage.test.tsx`

`reportService.getDashboardStats()` → `{toplam_sefer, aktif_arac, toplam_arac, ...}`
`reportService.getConsumptionTrend()` → `[{month: string, consumption: number}]`
`anomalyService.getFleetInsights()` → `{leakage: [...], maintenance: [...]}`
`predictionService.getComparison()` → `{mae, rmse, accuracy_distribution, trend, total_compared}`

- [ ] **Step 1: Test dosyasını yaz**

```tsx
// frontend/src/pages/__tests__/DashboardPage.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import DashboardPage from '../DashboardPage'

vi.mock('../../services/api/report-service', () => ({
  reportService: {
    getDashboardStats: vi.fn().mockResolvedValue({ toplam_sefer: 42, aktif_arac: 10 }),
    getConsumptionTrend: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('../../services/api/anomaly-service', () => ({
  anomalyService: {
    getFleetInsights: vi.fn().mockResolvedValue({ leakage: [], maintenance: [] }),
  },
}))
vi.mock('../../services/api/prediction-service', () => ({
  predictionService: {
    getComparison: vi.fn().mockResolvedValue({
      mae: 1.2, rmse: 2.1, total_compared: 100,
      accuracy_distribution: { good: 80, warning: 15, error: 5, good_pct: 80, warning_pct: 15, error_pct: 5 },
      trend: [],
    }),
  },
}))
vi.mock('../../services/api/trip-service', () => ({
  tripService: { getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
}))

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage', () => {
  it('renders dashboard heading', () => {
    wrap(<DashboardPage />)
    expect(screen.getByTestId('dashboard-page')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Testi çalıştır — önce PASS (stub), ardından gerçek bileşenle doğrula**
```bash
cd frontend && npx vitest --run src/pages/__tests__/DashboardPage.test.tsx
```

- [ ] **Step 3: KpiRow bileşenini yaz**

```tsx
// frontend/src/components/dashboard/KpiRow.tsx
import { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/Card'

interface KpiItem {
  label: string
  value: string | number
  icon: LucideIcon
  color: string
  bgColor: string
}

export function KpiRow({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label} padding="md" className="flex items-center gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${item.bgColor}`}>
            <item.icon className={`h-6 w-6 ${item.color}`} />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider text-secondary truncate">
              {item.label}
            </p>
            <p className={`mt-0.5 text-2xl font-bold ${item.color}`}>{item.value}</p>
          </div>
        </Card>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: ConsumptionChart bileşenini yaz**

Recharts import'ları: `LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer`

```tsx
// frontend/src/components/dashboard/ConsumptionChart.tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Card } from '@/components/ui/Card'

interface Props {
  data: Array<{ month: string; consumption: number }>
  isLoading?: boolean
}

export function ConsumptionChart({ data, isLoading }: Props) {
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">Tüketim Trendi</h2>
        <p className="text-xs text-secondary">Aylık ortalama L/100km</p>
      </div>
      {isLoading ? (
        <div className="h-48 animate-pulse rounded-xl bg-elevated/50" />
      ) : data.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-secondary">
          Henüz veri yok
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={192}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit=" L" />
            <Tooltip formatter={(v: number) => [`${v.toFixed(1)} L/100km`, 'Tüketim']} />
            <Line
              type="monotone"
              dataKey="consumption"
              stroke="var(--color-accent)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
```

- [ ] **Step 5: AnomalyWidget bileşenini yaz**

```tsx
// frontend/src/components/dashboard/AnomalyWidget.tsx
import { AlertTriangle } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import type { LeakageItem } from '@/services/api/anomaly-service'

interface Props {
  items: LeakageItem[]
  isLoading?: boolean
}

export function AnomalyWidget({ items, isLoading }: Props) {
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <h2 className="text-sm font-semibold text-primary">Yakıt Sapmaları</h2>
      </div>
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded-lg bg-elevated/50" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-secondary">Anomali tespit edilmedi</p>
      ) : (
        <div className="space-y-2">
          {items.slice(0, 5).map((item) => (
            <div
              key={item.arac_id}
              className="flex items-center justify-between rounded-lg border border-border/50 bg-elevated/30 px-3 py-2"
            >
              <span className="text-sm font-medium text-primary">
                {item.plaka ?? `Araç #${item.arac_id}`}
              </span>
              <Badge variant="warning">
                {item.ortalama_sapma != null
                  ? `+${item.ortalama_sapma.toFixed(1)} L`
                  : 'Sapma'}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 6: DashboardPage'i yaz (stub'u değiştir)**

```tsx
// frontend/src/pages/DashboardPage.tsx
import { useQuery } from '@tanstack/react-query'
import { Activity, Truck, AlertTriangle, Target } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { KpiRow } from '@/components/dashboard/KpiRow'
import { ConsumptionChart } from '@/components/dashboard/ConsumptionChart'
import { AnomalyWidget } from '@/components/dashboard/AnomalyWidget'
import { reportService } from '@/services/api/report-service'
import { anomalyService } from '@/services/api/anomaly-service'
import { predictionService } from '@/services/api/prediction-service'

export default function DashboardPage() {
  usePageTitle('Dashboard')

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => reportService.getDashboardStats(),
    staleTime: 2 * 60 * 1000,
  })

  const { data: trend = [], isLoading: trendLoading } = useQuery({
    queryKey: ['dashboard-consumption-trend'],
    queryFn: () => reportService.getConsumptionTrend(),
    staleTime: 10 * 60 * 1000,
  })

  const { data: insights, isLoading: insightsLoading } = useQuery({
    queryKey: ['dashboard-fleet-insights'],
    queryFn: () => anomalyService.getFleetInsights(30),
    staleTime: 5 * 60 * 1000,
  })

  const { data: comparison } = useQuery({
    queryKey: ['dashboard-prediction-comparison'],
    queryFn: () => predictionService.getComparison(30),
    staleTime: 10 * 60 * 1000,
  })

  const mlAccuracy = comparison
    ? `${comparison.accuracy_distribution.good_pct.toFixed(0)}%`
    : '—'

  const kpiItems = [
    {
      label: 'Aktif Sefer',
      value: stats?.toplam_sefer ?? '—',
      icon: Activity,
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: 'Aktif Araç',
      value: stats?.aktif_arac ?? stats?.toplam_arac ?? '—',
      icon: Truck,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
    {
      label: 'Yakıt Sapması',
      value: insights?.leakage.length ?? '—',
      icon: AlertTriangle,
      color: 'text-amber-500',
      bgColor: 'bg-amber-500/10',
    },
    {
      label: 'ML Doğruluk',
      value: mlAccuracy,
      icon: Target,
      color: 'text-emerald-500',
      bgColor: 'bg-emerald-500/10',
    },
  ]

  return (
    <div data-testid="dashboard-page" className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">Dashboard</h1>
        <p className="text-sm text-secondary">Filo genel durumu ve özeti</p>
      </div>

      <KpiRow items={kpiItems} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ConsumptionChart data={trend} isLoading={trendLoading} />
        <AnomalyWidget items={insights?.leakage ?? []} isLoading={insightsLoading} />
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Testi çalıştır — PASS bekleniyor**
```bash
cd frontend && npx vitest --run src/pages/__tests__/DashboardPage.test.tsx
```

- [ ] **Step 8: Commit**
```bash
git add frontend/src/components/dashboard/ frontend/src/pages/DashboardPage.tsx \
  frontend/src/pages/__tests__/DashboardPage.test.tsx
git commit -m "feat: add Dashboard page with KPI, chart, anomaly widget"
```

---

## Task 5: Monitoring Sayfası (WebSocket Bildirimler)

**Files:**
- Create: `frontend/src/components/monitoring/useMonitoringSocket.ts`
- Create: `frontend/src/components/monitoring/ConnectionStatus.tsx`
- Create: `frontend/src/components/monitoring/NotificationFeed.tsx`
- Create: `frontend/src/pages/MonitoringPage.tsx` (stub'u değiştir)

WebSocket endpoint: `ws://<host>/api/v1/admin/ws/live?token=<JWT>`
Mesaj formatı: `{type: "notification", data: {id, baslik, icerik, olay_tipi, olusturma_tarihi}}`
Token: `tokenStorage.get()` (auth-service.ts'den)

- [ ] **Step 1: useMonitoringSocket hook testini yaz**

```ts
// frontend/src/components/monitoring/__tests__/useMonitoringSocket.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMonitoringSocket } from '../useMonitoringSocket'

// WebSocket mock
class MockWebSocket {
  static OPEN = 1
  static CONNECTING = 0
  static CLOSING = 2
  static CLOSED = 3
  readyState = MockWebSocket.CONNECTING
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onclose: ((e: CloseEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  close = vi.fn()
  send = vi.fn()
  simulateOpen() { this.readyState = MockWebSocket.OPEN; this.onopen?.(new Event('open')) }
  simulateMessage(data: unknown) { this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) })) }
  simulateClose() { this.readyState = MockWebSocket.CLOSED; this.onclose?.(new CloseEvent('close')) }
}

let mockWs: MockWebSocket
vi.stubGlobal('WebSocket', vi.fn(() => { mockWs = new MockWebSocket(); return mockWs }))

vi.mock('../../../services/api/auth-service', () => ({
  tokenStorage: { get: vi.fn().mockReturnValue('test-jwt-token') },
}))

describe('useMonitoringSocket', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.restoreAllMocks())

  it('starts as disconnected', () => {
    const { result } = renderHook(() => useMonitoringSocket())
    expect(result.current.status).toBe('connecting')
  })

  it('becomes connected after open', () => {
    const { result } = renderHook(() => useMonitoringSocket())
    act(() => mockWs.simulateOpen())
    expect(result.current.status).toBe('connected')
  })

  it('appends notification on message', () => {
    const { result } = renderHook(() => useMonitoringSocket())
    act(() => mockWs.simulateOpen())
    act(() => mockWs.simulateMessage({
      type: 'notification',
      data: { id: 1, baslik: 'Test', icerik: 'İçerik', olay_tipi: 'fuel', olusturma_tarihi: '2026-05-17T10:00:00' },
    }))
    expect(result.current.notifications).toHaveLength(1)
    expect(result.current.notifications[0].baslik).toBe('Test')
  })
})
```

- [ ] **Step 2: Testi çalıştır — FAIL bekleniyor**
```bash
cd frontend && npx vitest --run src/components/monitoring/__tests__/useMonitoringSocket.test.ts
```
Beklenen: FAIL — module not found

- [ ] **Step 3: useMonitoringSocket hook'u yaz**

```ts
// frontend/src/components/monitoring/useMonitoringSocket.ts
import { useEffect, useRef, useState, useCallback } from 'react'
import { tokenStorage } from '@/services/api/auth-service'

export interface WsNotification {
  id: number
  baslik: string
  icerik: string
  olay_tipi: string
  olusturma_tarihi: string
}

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

const MAX_RETRIES = 5
const BASE_DELAY_MS = 3000

function buildWsUrl(token: string): string {
  const base = (import.meta.env.VITE_API_URL ?? '/api/v1') as string
  const wsBase = base.startsWith('http')
    ? base.replace(/^http/, 'ws')
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}${base}`
  return `${wsBase}/admin/ws/live?token=${token}`
}

export function useMonitoringSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [notifications, setNotifications] = useState<WsNotification[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const token = tokenStorage.get()
    if (!token) { setStatus('error'); return }

    const ws = new WebSocket(buildWsUrl(token))
    wsRef.current = ws
    setStatus('connecting')

    ws.onopen = () => {
      setStatus('connected')
      retryCountRef.current = 0
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string; data: WsNotification }
        if (msg.type === 'notification') {
          setNotifications((prev) => [msg.data, ...prev].slice(0, 100))
        }
      } catch { /* ignore malformed messages */ }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = BASE_DELAY_MS * Math.pow(2, retryCountRef.current)
        retryCountRef.current += 1
        retryTimerRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => setStatus('error')
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const clearNotifications = useCallback(() => setNotifications([]), [])

  return { status, notifications, clearNotifications }
}
```

- [ ] **Step 4: Testi çalıştır — PASS bekleniyor**
```bash
cd frontend && npx vitest --run src/components/monitoring/__tests__/useMonitoringSocket.test.ts
```

- [ ] **Step 5: ConnectionStatus bileşenini yaz**

```tsx
// frontend/src/components/monitoring/ConnectionStatus.tsx
import { Wifi, WifiOff, Loader2 } from 'lucide-react'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface Props {
  status: ConnectionStatus
  notificationCount: number
}

export function ConnectionStatus({ status, notificationCount }: Props) {
  const config = {
    connecting: { icon: Loader2, label: 'Bağlanıyor...', color: 'text-amber-500', spin: true },
    connected: { icon: Wifi, label: `Bağlı — ${notificationCount} bildirim`, color: 'text-emerald-500', spin: false },
    disconnected: { icon: WifiOff, label: 'Bağlantı kesildi, yeniden bağlanıyor...', color: 'text-amber-500', spin: false },
    error: { icon: WifiOff, label: 'Bağlantı hatası', color: 'text-danger', spin: false },
  }[status]

  const Icon = config.icon

  return (
    <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
      <Icon className={`h-4 w-4 ${config.color} ${config.spin ? 'animate-spin' : ''}`} />
      <span className={`text-sm font-medium ${config.color}`}>{config.label}</span>
    </div>
  )
}
```

- [ ] **Step 6: NotificationFeed bileşenini yaz**

```tsx
// frontend/src/components/monitoring/NotificationFeed.tsx
import { AnimatePresence, motion } from 'framer-motion'
import type { WsNotification } from './useMonitoringSocket'

function formatTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString('tr-TR') } catch { return iso }
}

export function NotificationFeed({ notifications }: { notifications: WsNotification[] }) {
  if (notifications.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-border text-sm text-secondary">
        Henüz bildirim yok
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
      <AnimatePresence initial={false}>
        {notifications.map((n) => (
          <motion.div
            key={`${n.id}-${n.olusturma_tarihi}`}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-xl border border-border/60 bg-surface px-4 py-3"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-primary">{n.baslik}</p>
                <p className="mt-0.5 text-xs text-secondary">{n.icerik}</p>
              </div>
              <span className="shrink-0 text-[10px] text-tertiary">{formatTime(n.olusturma_tarihi)}</span>
            </div>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-tertiary">{n.olay_tipi}</p>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
```

- [ ] **Step 7: MonitoringPage'i yaz**

```tsx
// frontend/src/pages/MonitoringPage.tsx
import { usePageTitle } from '@/hooks/usePageTitle'
import { Button } from '@/components/ui/Button'
import { useMonitoringSocket } from '@/components/monitoring/useMonitoringSocket'
import { ConnectionStatus } from '@/components/monitoring/ConnectionStatus'
import { NotificationFeed } from '@/components/monitoring/NotificationFeed'
import { Trash2 } from 'lucide-react'

export default function MonitoringPage() {
  usePageTitle('Canlı Takip')
  const { status, notifications, clearNotifications } = useMonitoringSocket()

  return (
    <div data-testid="monitoring-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary">Canlı Takip</h1>
          <p className="text-sm text-secondary">Gerçek zamanlı sistem bildirimleri</p>
        </div>
        <Button variant="ghost" size="sm" onClick={clearNotifications}>
          <Trash2 className="h-4 w-4 mr-2" />
          Temizle
        </Button>
      </div>

      <ConnectionStatus status={status} notificationCount={notifications.length} />
      <NotificationFeed notifications={notifications} />
    </div>
  )
}
```

- [ ] **Step 8: Testleri çalıştır**
```bash
cd frontend && npx vitest --run src/components/monitoring/__tests__/
```
Beklenen: PASS

- [ ] **Step 9: Commit**
```bash
git add frontend/src/components/monitoring/ frontend/src/pages/MonitoringPage.tsx
git commit -m "feat: add Monitoring page with WebSocket notification feed"
```

---

## Task 6: Anomaliler Sayfası

**Files:**
- Create: `frontend/src/components/alerts/SeverityFilter.tsx`
- Create: `frontend/src/components/alerts/AnomalyTable.tsx`
- Create: `frontend/src/pages/AlertsPage.tsx` (stub'u değiştir)
- Create: `frontend/src/pages/__tests__/AlertsPage.test.tsx`

- [ ] **Step 1: Test dosyasını yaz**

```tsx
// frontend/src/pages/__tests__/AlertsPage.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import AlertsPage from '../AlertsPage'

vi.mock('../../services/api/anomaly-service', () => ({
  anomalyService: {
    getFleetInsights: vi.fn().mockResolvedValue({
      leakage: [
        { arac_id: 1, plaka: '34 ABC 001', ortalama_sapma: 3.2, sefer_sayisi: 5, tahmini_kayip_lt: 16 },
      ],
      maintenance: [
        { arac_id: 2, plaka: '06 XYZ 002', toplam_km: 120000, son_bakim_km: 100000, fark_km: 20000 },
      ],
    }),
  },
}))

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>)
}

describe('AlertsPage', () => {
  it('renders alerts page heading', () => {
    wrap(<AlertsPage />)
    expect(screen.getByTestId('alerts-page')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Testi çalıştır — PASS (stub)**
```bash
cd frontend && npx vitest --run src/pages/__tests__/AlertsPage.test.tsx
```

- [ ] **Step 3: SeverityFilter bileşenini yaz**

```tsx
// frontend/src/components/alerts/SeverityFilter.tsx
import { cn } from '@/lib/utils'

export type AlertTab = 'all' | 'leakage' | 'maintenance'

interface Props {
  active: AlertTab
  onChange: (tab: AlertTab) => void
  leakageCount: number
  maintenanceCount: number
}

const tabs: { id: AlertTab; label: string }[] = [
  { id: 'all', label: 'Tümü' },
  { id: 'leakage', label: 'Yakıt Sapması' },
  { id: 'maintenance', label: 'Bakım Adayı' },
]

export function SeverityFilter({ active, onChange, leakageCount, maintenanceCount }: Props) {
  const counts: Record<AlertTab, number> = {
    all: leakageCount + maintenanceCount,
    leakage: leakageCount,
    maintenance: maintenanceCount,
  }

  return (
    <div className="flex gap-1 rounded-xl border border-border bg-surface p-1 w-fit">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
            active === tab.id
              ? 'bg-accent text-white shadow-sm'
              : 'text-secondary hover:text-primary',
          )}
        >
          {tab.label}
          <span
            className={cn(
              'rounded-full px-1.5 py-0.5 text-[10px] font-bold',
              active === tab.id ? 'bg-white/20 text-white' : 'bg-elevated text-secondary',
            )}
          >
            {counts[tab.id]}
          </span>
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: AnomalyTable bileşenini yaz**

```tsx
// frontend/src/components/alerts/AnomalyTable.tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import type { LeakageItem, MaintenanceCandidate } from '@/services/api/anomaly-service'

interface LeakageTableProps { items: LeakageItem[] }
interface MaintenanceTableProps { items: MaintenanceCandidate[] }

export function LeakageTable({ items }: LeakageTableProps) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-secondary">Yakıt sapması tespit edilmedi</p>
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Araç</TableHead>
          <TableHead>Ort. Sapma</TableHead>
          <TableHead>Sefer Sayısı</TableHead>
          <TableHead>Tahmini Kayıp</TableHead>
          <TableHead>Durum</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.arac_id}>
            <TableCell className="font-medium">{item.plaka ?? `#${item.arac_id}`}</TableCell>
            <TableCell>{item.ortalama_sapma != null ? `+${item.ortalama_sapma.toFixed(1)} L` : '—'}</TableCell>
            <TableCell>{item.sefer_sayisi ?? '—'}</TableCell>
            <TableCell>{item.tahmini_kayip_lt != null ? `${item.tahmini_kayip_lt.toFixed(0)} L` : '—'}</TableCell>
            <TableCell>
              <Badge variant={(item.ortalama_sapma ?? 0) > 5 ? 'danger' : 'warning'}>
                {(item.ortalama_sapma ?? 0) > 5 ? 'Kritik' : 'Uyarı'}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function MaintenanceTable({ items }: MaintenanceTableProps) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-secondary">Bakım adayı araç yok</p>
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Araç</TableHead>
          <TableHead>Toplam KM</TableHead>
          <TableHead>Son Bakım</TableHead>
          <TableHead>Fark</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.arac_id}>
            <TableCell className="font-medium">{item.plaka ?? `#${item.arac_id}`}</TableCell>
            <TableCell>{item.toplam_km?.toLocaleString('tr-TR') ?? '—'} km</TableCell>
            <TableCell>{item.son_bakim_km?.toLocaleString('tr-TR') ?? '—'} km</TableCell>
            <TableCell>
              <Badge variant={(item.fark_km ?? 0) > 30000 ? 'danger' : 'warning'}>
                {item.fark_km?.toLocaleString('tr-TR') ?? '—'} km
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

- [ ] **Step 5: AlertsPage'i yaz**

```tsx
// frontend/src/pages/AlertsPage.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card } from '@/components/ui/Card'
import { SeverityFilter, type AlertTab } from '@/components/alerts/SeverityFilter'
import { LeakageTable, MaintenanceTable } from '@/components/alerts/AnomalyTable'
import { anomalyService } from '@/services/api/anomaly-service'
import { AlertTriangle, Wrench, Droplets } from 'lucide-react'

export default function AlertsPage() {
  usePageTitle('Anomaliler')
  const [activeTab, setActiveTab] = useState<AlertTab>('all')

  const { data: insights, isLoading } = useQuery({
    queryKey: ['alerts-fleet-insights'],
    queryFn: () => anomalyService.getFleetInsights(30),
    staleTime: 5 * 60 * 1000,
  })

  const leakage = insights?.leakage ?? []
  const maintenance = insights?.maintenance ?? []

  const kpis = [
    { label: 'Yakıt Sapması', value: leakage.length, icon: Droplets, color: 'text-amber-500', bg: 'bg-amber-500/10' },
    { label: 'Bakım Adayı', value: maintenance.length, icon: Wrench, color: 'text-blue-500', bg: 'bg-blue-500/10' },
    { label: 'Toplam Uyarı', value: leakage.length + maintenance.length, icon: AlertTriangle, color: 'text-rose-500', bg: 'bg-rose-500/10' },
  ]

  return (
    <div data-testid="alerts-page" className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">Anomaliler</h1>
        <p className="text-sm text-secondary">Filo yakıt sapmaları ve bakım ihtiyaçları</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label} padding="md" className="flex items-center gap-4">
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${kpi.bg}`}>
              <kpi.icon className={`h-6 w-6 ${kpi.color}`} />
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-secondary">{kpi.label}</p>
              <p className={`text-2xl font-bold ${kpi.color}`}>{isLoading ? '…' : kpi.value}</p>
            </div>
          </Card>
        ))}
      </div>

      <SeverityFilter
        active={activeTab}
        onChange={setActiveTab}
        leakageCount={leakage.length}
        maintenanceCount={maintenance.length}
      />

      <Card padding="lg">
        {isLoading ? (
          <div className="h-48 animate-pulse rounded-xl bg-elevated/50" />
        ) : (
          <>
            {(activeTab === 'all' || activeTab === 'leakage') && (
              <div className="mb-6">
                <h3 className="mb-3 text-sm font-semibold text-primary">Yakıt Sapması</h3>
                <LeakageTable items={leakage} />
              </div>
            )}
            {(activeTab === 'all' || activeTab === 'maintenance') && (
              <div>
                <h3 className="mb-3 text-sm font-semibold text-primary">Bakım Adayları</h3>
                <MaintenanceTable items={maintenance} />
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
```

- [ ] **Step 6: Testi çalıştır**
```bash
cd frontend && npx vitest --run src/pages/__tests__/AlertsPage.test.tsx
```

- [ ] **Step 7: Commit**
```bash
git add frontend/src/components/alerts/ frontend/src/pages/AlertsPage.tsx \
  frontend/src/pages/__tests__/AlertsPage.test.tsx
git commit -m "feat: add Alerts page with leakage and maintenance tables"
```

---

## Task 7: ML Tahminler Sayfası

**Files:**
- Create: `frontend/src/components/predictions/MetricCards.tsx`
- Create: `frontend/src/components/predictions/EnsembleStatusCard.tsx`
- Create: `frontend/src/components/predictions/AccuracyChart.tsx`
- Create: `frontend/src/components/predictions/XaiPanel.tsx`
- Create: `frontend/src/pages/PredictionsPage.tsx` (stub'u değiştir)
- Create: `frontend/src/pages/__tests__/PredictionsPage.test.tsx`

- [ ] **Step 1: Test dosyasını yaz**

```tsx
// frontend/src/pages/__tests__/PredictionsPage.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import PredictionsPage from '../PredictionsPage'

vi.mock('../../services/api/prediction-service', () => ({
  predictionService: {
    getEnsembleStatus: vi.fn().mockResolvedValue({
      models: { physics: true, lightgbm: false, xgboost: false, gradient_boosting: true, random_forest: true },
      weights: { physics: 0.8, lightgbm: 0.05, xgboost: 0.05, gradient_boosting: 0.05, random_forest: 0.05 },
      total_models: 3,
      sklearn_available: true, lightgbm_available: false, xgboost_available: false,
    }),
    getComparison: vi.fn().mockResolvedValue({
      mae: 1.2, rmse: 2.1, total_compared: 50,
      accuracy_distribution: { good: 40, warning: 7, error: 3, good_pct: 80, warning_pct: 14, error_pct: 6 },
      trend: [{ date: '2026-01-01', actual: 28, predicted: 27.5 }],
    }),
    explain: vi.fn().mockResolvedValue({ tahmini_tuketim: 29.5, components: {} }),
  },
}))
vi.mock('../../services/api/vehicle-service', () => ({
  vehicleService: { getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
}))

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>)
}

describe('PredictionsPage', () => {
  it('renders page container', () => {
    wrap(<PredictionsPage />)
    expect(screen.getByTestId('predictions-page')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Testi çalıştır — PASS (stub)**
```bash
cd frontend && npx vitest --run src/pages/__tests__/PredictionsPage.test.tsx
```

- [ ] **Step 3: MetricCards bileşenini yaz**

```tsx
// frontend/src/components/predictions/MetricCards.tsx
import { Card } from '@/components/ui/Card'

interface Props {
  mae: number
  rmse: number
  totalCompared: number
  goodPct: number
}

export function MetricCards({ mae, rmse, totalCompared, goodPct }: Props) {
  const metrics = [
    { label: 'MAE', value: mae.toFixed(2), unit: 'L/100km', color: 'text-blue-500' },
    { label: 'RMSE', value: rmse.toFixed(2), unit: 'L/100km', color: 'text-purple-500' },
    { label: 'Doğruluk', value: `${goodPct.toFixed(0)}%`, unit: 'iyi tahmin', color: 'text-emerald-500' },
    { label: 'Karşılaştırılan', value: totalCompared.toString(), unit: 'sefer', color: 'text-secondary' },
  ]

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {metrics.map((m) => (
        <Card key={m.label} padding="md">
          <p className="text-[11px] font-bold uppercase tracking-wider text-secondary">{m.label}</p>
          <p className={`mt-1 text-2xl font-bold ${m.color}`}>{m.value}</p>
          <p className="text-xs text-tertiary">{m.unit}</p>
        </Card>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: EnsembleStatusCard bileşenini yaz**

Recharts: `BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell`

```tsx
// frontend/src/components/predictions/EnsembleStatusCard.tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Card } from '@/components/ui/Card'
import type { EnsembleStatusResponse } from '@/services/api/prediction-service'

const MODEL_LABELS: Record<string, string> = {
  physics: 'Fizik',
  lightgbm: 'LightGBM',
  xgboost: 'XGBoost',
  gradient_boosting: 'Grad. Boost',
  random_forest: 'Rand. Forest',
}

export function EnsembleStatusCard({ data }: { data: EnsembleStatusResponse }) {
  const chartData = Object.entries(data.weights).map(([key, weight]) => ({
    name: MODEL_LABELS[key] ?? key,
    weight: Math.round(weight * 100),
    available: data.models[key] ?? false,
  }))

  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">Ensemble Model Ağırlıkları</h2>
        <p className="text-xs text-secondary">{data.total_models} aktif model</p>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} layout="vertical">
          <XAxis type="number" unit="%" tick={{ fontSize: 11 }} domain={[0, 100]} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
          <Tooltip formatter={(v: number) => [`${v}%`, 'Ağırlık']} />
          <Bar dataKey="weight" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.available ? 'var(--color-accent)' : 'var(--color-border)'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}
```

- [ ] **Step 5: AccuracyChart bileşenini yaz**

Recharts: `AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer`

```tsx
// frontend/src/components/predictions/AccuracyChart.tsx
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card } from '@/components/ui/Card'

interface TrendPoint { date: string; actual: number; predicted: number }

export function AccuracyChart({ data }: { data: TrendPoint[] }) {
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold text-primary">Gerçek vs Tahmin</h2>
        <p className="text-xs text-secondary">Son 30 gün, L/100km</p>
      </div>
      {data.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-secondary">Veri yok</div>
      ) : (
        <ResponsiveContainer width="100%" height={192}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="predictedGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} unit=" L" />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey="actual" name="Gerçek" stroke="#3B82F6" fill="url(#actualGrad)" strokeWidth={2} dot={false} />
            <Area type="monotone" dataKey="predicted" name="Tahmin" stroke="#10B981" fill="url(#predictedGrad)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
```

- [ ] **Step 6: XaiPanel bileşenini yaz**

```tsx
// frontend/src/components/predictions/XaiPanel.tsx
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { predictionService, type PredictionExplainRequest } from '@/services/api/prediction-service'
import { vehicleService } from '@/services/api/vehicle-service'
import { BrainCircuit } from 'lucide-react'

export function XaiPanel() {
  const [form, setForm] = useState<PredictionExplainRequest>({
    arac_id: 0,
    mesafe_km: 100,
    ton: 0,
    ascent_m: 0,
    descent_m: 0,
    flat_distance_km: 100,
  })

  const { data: vehicles } = useQuery({
    queryKey: ['xai-vehicles'],
    queryFn: () => vehicleService.getAll({ aktif_only: true, limit: 100 }),
    staleTime: 10 * 60 * 1000,
  })

  const { mutate, data: result, isPending, isError } = useMutation({
    mutationFn: () => predictionService.explain(form),
  })

  return (
    <Card padding="lg" className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <BrainCircuit className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-primary">XAI — Tahmin Açıklama</h2>
          <p className="text-xs text-secondary">Tüketim tahmininin faktörlerini görün</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-secondary">Araç</label>
          <select
            className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-primary focus:outline-none focus:ring-2 focus:ring-accent/30"
            value={form.arac_id}
            onChange={(e) => setForm((f) => ({ ...f, arac_id: Number(e.target.value) }))}
          >
            <option value={0}>Araç seçin</option>
            {(vehicles?.items ?? []).map((v: any) => (
              <option key={v.id} value={v.id}>{v.plaka}</option>
            ))}
          </select>
        </div>

        {[
          { key: 'mesafe_km', label: 'Mesafe (km)', min: 1 },
          { key: 'ton', label: 'Yük (ton)', min: 0 },
          { key: 'ascent_m', label: 'Tırmanış (m)', min: 0 },
          { key: 'descent_m', label: 'İniş (m)', min: 0 },
          { key: 'flat_distance_km', label: 'Düz Yol (km)', min: 0 },
        ].map(({ key, label, min }) => (
          <div key={key}>
            <label className="mb-1 block text-xs font-medium text-secondary">{label}</label>
            <Input
              type="number"
              min={min}
              value={(form as any)[key]}
              onChange={(e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) }))}
            />
          </div>
        ))}
      </div>

      <Button
        onClick={() => mutate()}
        disabled={isPending || form.arac_id === 0}
        className="w-fit"
      >
        {isPending ? 'Hesaplanıyor...' : 'Tahmin Et + Açıkla'}
      </Button>

      {isError && (
        <p className="text-sm text-danger">Tahmin hesaplanamadı. Araç verisi yeterli olmayabilir.</p>
      )}

      {result && (
        <div className="rounded-xl border border-border/60 bg-elevated/30 p-4 space-y-3">
          <p className="text-sm font-semibold text-primary">
            Tahmini Tüketim:{' '}
            <span className="text-accent">{Number(result.tahmini_tuketim ?? 0).toFixed(1)} L/100km</span>
          </p>
          {result.components && Object.keys(result.components).length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-bold uppercase tracking-wider text-tertiary">Etki Faktörleri</p>
              {Object.entries(result.components as Record<string, number>).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between text-sm">
                  <span className="text-secondary">{k}</span>
                  <span className="font-medium text-primary">{(v * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
```

- [ ] **Step 7: PredictionsPage'i yaz**

```tsx
// frontend/src/pages/PredictionsPage.tsx
import { useQuery } from '@tanstack/react-query'
import { usePageTitle } from '@/hooks/usePageTitle'
import { MetricCards } from '@/components/predictions/MetricCards'
import { EnsembleStatusCard } from '@/components/predictions/EnsembleStatusCard'
import { AccuracyChart } from '@/components/predictions/AccuracyChart'
import { XaiPanel } from '@/components/predictions/XaiPanel'
import { predictionService } from '@/services/api/prediction-service'

export default function PredictionsPage() {
  usePageTitle('ML Tahminler')

  const { data: ensemble } = useQuery({
    queryKey: ['predictions-ensemble'],
    queryFn: () => predictionService.getEnsembleStatus(),
    staleTime: 5 * 60 * 1000,
  })

  const { data: comparison } = useQuery({
    queryKey: ['predictions-comparison'],
    queryFn: () => predictionService.getComparison(30),
    staleTime: 10 * 60 * 1000,
  })

  return (
    <div data-testid="predictions-page" className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary">ML Tahminler</h1>
        <p className="text-sm text-secondary">Ensemble model durumu ve yakıt tüketim tahmini açıklama</p>
      </div>

      {comparison && (
        <MetricCards
          mae={comparison.mae}
          rmse={comparison.rmse}
          totalCompared={comparison.total_compared}
          goodPct={comparison.accuracy_distribution.good_pct}
        />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {ensemble && <EnsembleStatusCard data={ensemble} />}
        <AccuracyChart data={comparison?.trend ?? []} />
      </div>

      <XaiPanel />
    </div>
  )
}
```

- [ ] **Step 8: Testleri çalıştır**
```bash
cd frontend && npx vitest --run src/pages/__tests__/PredictionsPage.test.tsx
```

- [ ] **Step 9: Commit**
```bash
git add frontend/src/components/predictions/ frontend/src/pages/PredictionsPage.tsx \
  frontend/src/pages/__tests__/PredictionsPage.test.tsx
git commit -m "feat: add ML Predictions page with ensemble, accuracy, XAI"
```

---

## Task 8: Yakıt Sayfası Derinleştirme

**Files:**
- Modify: `frontend/src/pages/FuelPage.tsx`

Mevcut FuelPage'e tüketim trendi LineChart ekle (sayfanın üstüne, filtrelerden önce).
Veri kaynağı: `reportService.getConsumptionTrend()` — zaten `report-service.ts`'de var.

- [ ] **Step 1: Mevcut FuelPage testlerini çalıştır — başlangıç durumu**
```bash
cd frontend && npx vitest --run src/pages/__tests__/FuelPage.test.tsx
```
Not al: kaç test var, hepsi geçiyor mu?

- [ ] **Step 2: FuelPage'in başına tüketim chart'ı ekle**

`frontend/src/pages/FuelPage.tsx` dosyasını aç.

Import ekle (dosyanın üstüne):
```tsx
import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { reportService } from '../services/api/report-service'
import { Card } from '../components/ui/Card'
```

Bileşen içinde (JSX return'ün en üstüne, diğer içeriklerden önce) ekle:

```tsx
const { data: trend = [], isLoading: trendLoading } = useQuery({
  queryKey: ['fuel-consumption-trend'],
  queryFn: () => reportService.getConsumptionTrend(),
  staleTime: 10 * 60 * 1000,
})

// JSX'te sayfanın en üstüne:
<div className="mb-6">
  <Card padding="lg">
    <div className="mb-4">
      <h2 className="text-sm font-semibold text-primary">Aylık Tüketim Trendi</h2>
      <p className="text-xs text-secondary">L/100km ortalaması</p>
    </div>
    {trendLoading ? (
      <div className="h-36 animate-pulse rounded-xl bg-elevated/50" />
    ) : (
      <ResponsiveContainer width="100%" height={144}>
        <LineChart data={trend}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 11 }} unit=" L" />
          <Tooltip formatter={(v: number) => [`${v.toFixed(1)} L/100km`, 'Ort. Tüketim']} />
          <Line type="monotone" dataKey="consumption" stroke="var(--color-accent)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )}
  </Card>
</div>
```

- [ ] **Step 3: Mevcut testleri çalıştır — hâlâ geçmeli**
```bash
cd frontend && npx vitest --run src/pages/__tests__/FuelPage.test.tsx
```
Beklenen: Önceki test sayısı kadar PASS — hiçbiri bozulmamalı.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/pages/FuelPage.tsx
git commit -m "feat: add consumption trend chart to Fuel page"
```

---

## Task 9: Raporlar ve Admin Overview Chart

**Files:**
- Modify: `frontend/src/pages/admin/OverviewPage.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx`

### OverviewPage: Liste → LineChart

- [ ] **Step 1: OverviewPage'i güncelle**

`frontend/src/pages/admin/OverviewPage.tsx` dosyasını aç.

Import ekle:
```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
```

Consumption trend bölümünü bul (satır ~120-140, `consumptionTrend.length > 0` bloğu). Metin listesini Recharts ile değiştir:

```tsx
// ESKİ: consumptionTrend.slice(-6).map(item => <div>...</div>)
// YENİ:
{consumptionTrend.length > 0 ? (
  <ResponsiveContainer width="100%" height={160}>
    <LineChart data={consumptionTrend.slice(-12)}>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
      <YAxis tick={{ fontSize: 10 }} unit=" L" />
      <Tooltip formatter={(v: number) => [`${v.toFixed(1)} L`, 'Tüketim']} />
      <Line type="monotone" dataKey="consumption" stroke="var(--color-accent)" strokeWidth={2} dot={false} />
    </LineChart>
  </ResponsiveContainer>
) : (
  <div className="rounded-xl border border-dashed border-border/60 bg-elevated/20 px-4 py-8 text-sm text-secondary">
    {adminOverviewText.consumptionTrend.empty}
  </div>
)}
```

### ReportsPage: Vehicle Comparison BarChart Ekle

- [ ] **Step 2: ReportsPage'e araç karşılaştırma tab'ı ekle**

`frontend/src/pages/ReportsPage.tsx` dosyasını aç.

`reportPageText` / `reportDownloadOptions` import'larına `BarChart2` lucide icon ekle:
```tsx
import { BarChart2, FileText, PieChart, TrendingUp } from 'lucide-react'
```

Recharts import ekle:
```tsx
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
```

`activeTab` state'ini `'pdf' | 'cost' | 'vehicle'` olarak genişlet.

Tab bar'a yeni tab ekle:
```tsx
{
  id: 'vehicle',
  icon: BarChart2,
  label: 'Araç Karşılaştırma'
}
```

Yeni query ekle:
```tsx
const { data: vehicleComparison = [], isLoading: vehicleLoading } = useQuery({
  queryKey: ['vehicleComparison'],
  queryFn: () => reportsApi.getVehicleComparison(3),
  enabled: activeTab === 'vehicle',
  staleTime: 10 * 60 * 1000,
})
```

Tab içeriği ekle (mevcut tab render bölümünün sonuna):
```tsx
{activeTab === 'vehicle' && (
  <div className="space-y-4">
    <div>
      <h2 className="text-base font-semibold text-primary">Araç Tüketim Karşılaştırması</h2>
      <p className="text-sm text-secondary">Son 3 ay ortalaması, L/100km</p>
    </div>
    {vehicleLoading ? (
      <div className="h-64 animate-pulse rounded-xl bg-elevated/50" />
    ) : vehicleComparison.length === 0 ? (
      <p className="py-12 text-center text-sm text-secondary">Karşılaştırma verisi yok</p>
    ) : (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={vehicleComparison}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="plaka" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 11 }} unit=" L" />
          <Tooltip formatter={(v: number) => [`${v.toFixed(1)} L/100km`, 'Ort. Tüketim']} />
          <Bar dataKey="average_consumption" name="Tüketim" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )}
  </div>
)}
```

- [ ] **Step 3: Mevcut testleri çalıştır**
```bash
cd frontend && npx vitest --run src/pages/__tests__/ --run src/components/reports/__tests__/
```
Beklenen: Mevcut testler PASS.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/pages/admin/OverviewPage.tsx frontend/src/pages/ReportsPage.tsx
git commit -m "feat: replace text lists with Recharts charts in Reports and Admin"
```

---

## Task 10: Final Test Suite

- [ ] **Step 1: Tüm testleri çalıştır**
```bash
cd frontend && npx vitest --run
```
Beklenen: Tüm testler PASS. Hiçbiri bozulmamalı.

- [ ] **Step 2: TypeScript derleme kontrolü**
```bash
cd frontend && npx tsc --noEmit
```
Beklenen: Hata yok.

- [ ] **Step 3: Lint**
```bash
cd frontend && npm run lint
```

- [ ] **Step 4: Backend testlerini çalıştır (regression kontrolü)**
```bash
cd D:/PROJECT/LOJINEXT && pytest -m "not integration" -q
```
Beklenen: Backend testleri bozulmamış.

- [ ] **Step 5: Final commit**
```bash
git add -A
git commit -m "feat: frontend full rewrite complete — dashboard, monitoring, alerts, predictions, charts"
```

---

## Self-Review

**Spec coverage:**
- ✅ EliteLayout branding → Task 1
- ✅ Sidebar gruplandırma → Task 1
- ✅ App.tsx yeni route'lar → Task 1
- ✅ Dashboard sayfası (KPI + chart + anomali widget) → Task 4
- ✅ Monitoring sayfası (WebSocket bildirimler) → Task 5
- ✅ Anomaliler sayfası → Task 6
- ✅ ML Tahminler sayfası (ensemble + accuracy + XAI) → Task 7
- ✅ Yakıt sayfası chart → Task 8
- ✅ Raporlar araç karşılaştırma → Task 9
- ✅ Admin Overview chart → Task 9
- ✅ anomaly-service.ts → Task 2
- ✅ prediction-service.ts getEnsembleStatus → Task 3

**Placeholder kontrolü:** Tüm task'larda gerçek kod var, "TBD" yok.

**Tip tutarlılığı:**
- `LeakageItem`, `MaintenanceCandidate`, `FleetInsightsData` → Task 2'de tanımlandı, Task 4/6'da kullanıldı ✅
- `EnsembleStatusResponse`, `PredictionExplainRequest` → Task 3'te tanımlandı, Task 7'de kullanıldı ✅
- `WsNotification` → Task 5'te `useMonitoringSocket`'te tanımlandı, `NotificationFeed`'de kullanıldı ✅

**Eksik bulgu:**
- `vehicleService.getAll()` response type `{items: any[], total: number}` — XaiPanel Task 7'de `vehicles?.items ?? []` ile güvenli erişim yapıldı ✅
- Badge variant'ları: 'warning' ve 'danger' — mevcut `Badge.tsx`'te `variant` prop'u kontrol edilmeli. Eğer desteklemiyorsa className ile yazılmalı. Task 6 ve Task 7'de kullanılıyor.

**Badge uyarısı:** Implementation öncesi `frontend/src/components/ui/Badge.tsx` açılıp hangi variant'ları desteklediği kontrol edilmeli. Eğer 'warning' / 'danger' yoksa ilgili task'lar güncellenmeli.
