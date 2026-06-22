# Frontend Zod Validation — 7 Servis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `admin-service`, `ai-service`, `auth-service`, `prediction-service`, `report-service`, `preference-service`, `weather-service` servislerine mevcut projenin `validateResponse()` pattern'ini kullanarak Zod schema validation ekle.

**Architecture:** Mevcut pattern aynen uygulanır:
1. Zod schema'lar → `frontend/src/schemas/entities.ts` (mevcut) veya yeni `frontend/src/schemas/services.ts`
2. Response validation → `validateResponse(Schema, data, 'context')` — `frontend/src/lib/api-validator.ts`'ten import
3. Binary response'lar (PDF, Excel, Blob) ve fire-and-forget POST'lar validate edilmez — Zod sadece JSON response'lara uygulanır
4. `auth-service.ts` özel durum: `fetchWithAuth` kullanıyor, `axiosInstance` değil. Sadece `authApi.login` ve `authApi.getMe` response'larına schema ekle.

**Tech Stack:** TypeScript · Zod v3 · React · axiosInstance · `validateResponse` helper

---

## Mevcut Pattern Referansı

`trip-service.ts` şu pattern'i kullanıyor — tüm task'larda bunu birebir uygula:

```typescript
// 1. Schema tanımla (entities.ts veya services.ts'de)
const MySchema = z.object({ id: z.number(), name: z.string() })

// 2. Serviste kullan
import { validateResponse } from '../../lib/api-validator'
import { MySchema } from '../../schemas/services'

getItem: async (id: number) => {
    const response = await axiosInstance.get(`/items/${id}`)
    return validateResponse(MySchema, response.data, 'myService.getItem')
}
```

`validateResponse` production'da hata loglar ama UI'ı kırmaz (safe fallback). Development'da console.warn atar.

---

## Dosya Haritası

**Değiştirilecek:**
- `frontend/src/schemas/entities.ts` — mevcut entity schema'larına ek olarak yeni schema'lar ekle
- `frontend/src/services/api/ai-service.ts`
- `frontend/src/services/api/auth-service.ts`
- `frontend/src/services/api/prediction-service.ts`
- `frontend/src/services/api/report-service.ts`
- `frontend/src/services/api/preference-service.ts`
- `frontend/src/services/api/admin-service.ts`
- `frontend/src/services/api/weather-service.ts`

**Oluşturulacak:**
- `frontend/src/schemas/services.ts` — servis-specific schema'lar (entities.ts şişmesin diye ayrı dosya)

---

## GRUP 1 — Basit Servisler (küçük dosyalar)

### Task 1: `ai-service.ts` + `weather-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts` (create if not exists)
- Modify: `frontend/src/services/api/ai-service.ts`
- Modify: `frontend/src/services/api/weather-service.ts`

- [ ] **Step 1: `frontend/src/schemas/services.ts` dosyasını oluştur**

```typescript
import { z } from 'zod'

// ─── AI Service Schemas ───────────────────────────────────────────────────────

export const ChatMessageSchema = z.object({
    role: z.enum(['user', 'assistant', 'system']),
    content: z.string(),
})

export const ChatResponseSchema = z.object({
    response: z.string(),
    timestamp: z.string(),
})

export const AIStatusSchema = z.object({
    is_ready: z.boolean(),
    progress: z.object({
        status: z.string(),
        percent: z.number(),
        speed: z.string(),
    }),
})

// ─── Weather Service Schemas ──────────────────────────────────────────────────

export const WeatherForecastSchema = z.object({
    temperature: z.number().optional(),
    humidity: z.number().optional(),
    wind_speed: z.number().optional(),
    condition: z.string().optional(),
    forecast: z.array(z.record(z.unknown())).optional(),
}).passthrough()  // Backend'den ek alanlar gelebilir

export const WeatherTripImpactSchema = z.object({
    impact_score: z.number().optional(),
    recommendations: z.array(z.string()).optional(),
    weather_conditions: z.record(z.unknown()).optional(),
}).passthrough()

export const WeatherDashboardSummarySchema = z.object({
    current: z.record(z.unknown()).optional(),
    alerts: z.array(z.string()).optional(),
}).passthrough()
```

- [ ] **Step 2: `ai-service.ts` güncelle**

`ChatResponse` ve `AIStatus` response'larına validation ekle:

```typescript
import { validateResponse } from '../../lib/api-validator'
import { ChatResponseSchema, AIStatusSchema } from '../../schemas/services'

// chat metodunda:
chat: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await axiosInstance.post<ChatResponse>('/ai/chat', data)
    return validateResponse(ChatResponseSchema, response.data, 'aiApi.chat')
},

// getStatus metodunda:
getStatus: async (): Promise<AIStatus> => {
    const response = await axiosInstance.get<AIStatus>('/ai/status')
    return validateResponse(AIStatusSchema, response.data, 'aiApi.getStatus')
},
```

- [ ] **Step 3: `weather-service.ts` güncelle**

```typescript
import { validateResponse } from '../../lib/api-validator'
import {
    WeatherForecastSchema,
    WeatherTripImpactSchema,
    WeatherDashboardSummarySchema,
} from '../../schemas/services'

export const weatherApi = {
    getForecast: async (lat: number, lon: number) => {
        const { data } = await axiosInstance.post('/weather/forecast', { lat, lon })
        return validateResponse(WeatherForecastSchema, data, 'weatherApi.getForecast')
    },

    getTripImpact: async (params: { ... }) => {
        const { data } = await axiosInstance.post('/weather/trip-impact', params)
        return validateResponse(WeatherTripImpactSchema, data, 'weatherApi.getTripImpact')
    },

    getDashboardSummary: async () => {
        const { data } = await axiosInstance.get('/weather/dashboard-summary')
        return validateResponse(WeatherDashboardSummarySchema, data, 'weatherApi.getDashboardSummary')
    },
}
```

**NOT:** `params` tipini mevcut dosyadan kopyala — değiştirme.

- [ ] **Step 4: TypeScript kontrolü**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
```

- [ ] **Step 5: Build kontrolü**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/ai-service.ts frontend/src/services/api/weather-service.ts && git commit -m "feat(frontend): add Zod validation to ai-service and weather-service"
```

---

### Task 2: `auth-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts`
- Modify: `frontend/src/services/api/auth-service.ts`

> ⚠️ `auth-service.ts` özel durum: `authApi.login` raw `fetch` kullanıyor (axiosInstance değil). `validateResponse` için response JSON'ını önce parse et, sonra validate et. `getMe` ise `axiosInstance` kullanıyor — normal pattern geçerli.

- [ ] **Step 1: Schema'ları `services.ts`'e ekle**

```typescript
// ─── Auth Service Schemas ─────────────────────────────────────────────────────

export const LoginResponseSchema = z.object({
    access_token: z.string(),
    token_type: z.string(),
})

export const MeResponseSchema = z.object({
    id: z.number(),
    kullanici_adi: z.string(),
    email: z.string().optional().nullable(),
    ad_soyad: z.string(),
    aktif: z.boolean(),
    rol_id: z.number().optional().nullable(),
    rol: z.object({
        id: z.number().optional(),
        ad: z.string().optional(),
        yetkiler: z.record(z.boolean()).optional(),
    }).optional().nullable(),
}).passthrough()
```

- [ ] **Step 2: `auth-service.ts` güncelle**

`authApi.login` için — `fetch` response JSON'ını validate et:

```typescript
import { validateResponse } from '../../lib/api-validator'
import { LoginResponseSchema, MeResponseSchema } from '../../schemas/services'

// login metodunda (return satırını değiştir):
// Önce:
return response.json() as Promise<{ access_token: string; token_type: string }>

// Sonra:
const data = await response.json()
return validateResponse(LoginResponseSchema, data, 'authApi.login')
```

`authApi.getMe` için:

```typescript
getMe: async () => {
    const { data } = await axiosInstance.get('/auth/me')
    return validateResponse(MeResponseSchema, data, 'authApi.getMe')
},
```

- [ ] **Step 3: TypeScript kontrolü**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
```

- [ ] **Step 4: Build kontrolü**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/auth-service.ts && git commit -m "feat(frontend): add Zod validation to auth-service login and getMe"
```

---

## GRUP 2 — Orta Karmaşıklık

### Task 3: `report-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts`
- Modify: `frontend/src/services/api/report-service.ts`

> ⚠️ `downloadPdf` ve `downloadExcel` metodları `Blob` döndürüyor — validate etme. Sadece JSON response'ları validate et.

- [ ] **Step 1: Schema'ları `services.ts`'e ekle**

```typescript
// ─── Report Service Schemas ───────────────────────────────────────────────────

export const ConsumptionTrendPointSchema = z.object({
    month: z.string(),
    consumption: z.number(),
})

export const MonthlyCostTrendSchema = z.object({
    month: z.number(),
    year: z.number(),
    label: z.string(),
    fuel_cost: z.number(),
    fuel_liters: z.number(),
    trip_count: z.number(),
    total_distance: z.number(),
    cost_per_km: z.number(),
    fuel: z.number().optional(),
    maintenance: z.number().optional(),
}).passthrough()

export const VehicleCostComparisonSchema = z.object({
    arac_id: z.number(),
    plaka: z.string(),
    fuel_cost: z.number(),
    avg_consumption: z.number(),
    average_consumption: z.number().optional(),
    trip_count: z.number(),
    total_distance: z.number(),
    unavailable: z.boolean().optional(),
    error_code: z.string().optional(),
}).passthrough()

export const RoiStatsSchema = z.object({
    roi_years: z.number().optional(),
    annual_savings: z.number().optional(),
    payback_months: z.number().optional(),
}).passthrough()

export const SavingsPotentialSchema = z.object({
    current_avg: z.number().optional(),
    target_avg: z.number().optional(),
    potential_savings_liters: z.number().optional(),
    potential_savings_tl: z.number().optional(),
}).passthrough()
```

`DashboardStats` zaten `frontend/src/types/index.ts`'de tanımlı — schema'sı `entities.ts`'e taşınmışsa orayı kullan; yoksa yeni oluştur:

```typescript
// DashboardStats için (types/index.ts'deki interface ile eşleşmeli):
export const DashboardStatsSchema = z.object({
    total_vehicles: z.number().optional(),
    active_trips: z.number().optional(),
    fuel_efficiency: z.number().optional(),
    total_distance: z.number().optional(),
}).passthrough()  // Backend'den ek alanlar gelebilir
```

- [ ] **Step 2: `report-service.ts` güncelle**

```typescript
import { validateResponse } from '../../lib/api-validator'
import {
    DashboardStatsSchema,
    ConsumptionTrendPointSchema,
    MonthlyCostTrendSchema,
    VehicleCostComparisonSchema,
    RoiStatsSchema,
    SavingsPotentialSchema,
} from '../../schemas/services'

// getDashboardStats:
return validateResponse(DashboardStatsSchema, response.data, 'reportService.getDashboardStats')

// getConsumptionTrend:
return validateResponse(z.array(ConsumptionTrendPointSchema), response.data, 'reportService.getConsumptionTrend')

// getCostAnalysis — raw mapping sonrası validate et:
const validated = validateResponse(z.array(MonthlyCostTrendSchema), raw, 'reportService.getCostAnalysis')
return validated.map(item => ({ ...item, fuel: item.fuel_cost ?? 0, maintenance: 0 }))

// getVehicleComparison:
const validated = validateResponse(z.array(VehicleCostComparisonSchema), raw, 'reportService.getVehicleComparison')

// getRoiStats:
return validateResponse(RoiStatsSchema, response.data, 'reportService.getRoiStats')

// getSavingsPotential:
return validateResponse(SavingsPotentialSchema, response.data, 'reportService.getSavingsPotential')

// downloadPdf ve downloadExcel: Blob döndürüyor — DOKUNMA
```

- [ ] **Step 3: TypeScript kontrolü + build**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/report-service.ts && git commit -m "feat(frontend): add Zod validation to report-service"
```

---

### Task 4: `preference-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts`
- Modify: `frontend/src/services/api/preference-service.ts`

> ⚠️ `deger` alanı genuinely polymorphic (`any` backend'de) — `z.unknown()` kullan (type-safe ama içeriği doğrulamaz).

- [ ] **Step 1: Schema'ları `services.ts`'e ekle**

```typescript
// ─── Preference Service Schemas ───────────────────────────────────────────────

export const PreferenceSchema = z.object({
    id: z.number(),
    modul: z.string(),
    ayar_tipi: z.string(),
    deger: z.unknown(),  // Backend Any schema — polymorphic
    ad: z.string().optional().nullable(),
    is_default: z.boolean(),
    created_at: z.string(),
    updated_at: z.string(),
})
```

- [ ] **Step 2: `preference-service.ts` güncelle**

```typescript
import { validateResponse } from '../../lib/api-validator'
import { PreferenceSchema } from '../../schemas/services'

// getPreferences:
const { data } = await axiosInstance.get(...)
return validateResponse(z.object({ items: z.array(PreferenceSchema) }), data, 'preferenceService.getPreferences').items

// setPreference — POST, response validate et:
const { data } = await axiosInstance.post(...)
return validateResponse(PreferenceSchema, data, 'preferenceService.setPreference')
```

**İlk olarak dosyayı tam oku** — `setPreference`, `deletePreference` gibi metodların imzalarına dokunma.

- [ ] **Step 3: TypeScript kontrolü + build**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/preference-service.ts && git commit -m "feat(frontend): add Zod validation to preference-service"
```

---

### Task 5: `prediction-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts`
- Modify: `frontend/src/services/api/prediction-service.ts`

> Bu serviste response interface'leri zaten tanımlı — sadece Zod schema'ları ekle ve `validateResponse` ile sar.

- [ ] **Step 1: Schema'ları `services.ts`'e ekle**

```typescript
// ─── Prediction Service Schemas ───────────────────────────────────────────────

export const PredictionComparisonSchema = z.object({
    mae: z.number(),
    rmse: z.number(),
    accuracy_distribution: z.object({
        good: z.number(),
        warning: z.number(),
        error: z.number(),
        good_pct: z.number(),
        warning_pct: z.number(),
        error_pct: z.number(),
    }),
    trend: z.array(z.object({
        date: z.string(),
        actual: z.number(),
        predicted: z.number(),
    })),
    total_compared: z.number(),
})

export const PredictionEnqueueResponseSchema = z.object({
    task_id: z.string(),
    status: z.string(),
})

export const PredictionStatusResponseSchema = z.object({
    task_id: z.string(),
    status: z.string(),
    answer: z.string().optional(),
    error: z.string().optional(),
    finished_at: z.string().optional(),
})

export const EnsembleStatusResponseSchema = z.object({
    models: z.record(z.boolean()),
    weights: z.record(z.number()),
    sklearn_available: z.boolean(),
    lightgbm_available: z.boolean(),
    xgboost_available: z.boolean(),
    total_models: z.number(),
})

// predict ve explain — backend response'u karmaşık, passthrough kullan
export const PredictionResultSchema = z.object({
    tahmini_tuketim: z.number().optional(),
    prediction_liters: z.number().optional(),
    confidence_score: z.number().optional(),
    model_used: z.string().optional(),
}).passthrough()
```

- [ ] **Step 2: `prediction-service.ts` güncelle**

```typescript
import { validateResponse } from '../../lib/api-validator'
import {
    PredictionComparisonSchema,
    PredictionResultSchema,
    PredictionEnqueueResponseSchema,
    PredictionStatusResponseSchema,
    EnsembleStatusResponseSchema,
} from '../../schemas/services'

// getComparison:
return validateResponse(PredictionComparisonSchema, response.data, 'predictionService.getComparison')

// predict:
return validateResponse(PredictionResultSchema, response.data, 'predictionService.predict')

// explain:
return validateResponse(PredictionResultSchema, response.data, 'predictionService.explain')

// enqueue:
return validateResponse(PredictionEnqueueResponseSchema, response.data, 'predictionService.enqueue')

// status:
return validateResponse(PredictionStatusResponseSchema, response.data, 'predictionService.status')

// getEnsembleStatus:
return validateResponse(EnsembleStatusResponseSchema, response.data, 'predictionService.getEnsembleStatus')
```

- [ ] **Step 3: TypeScript kontrolü + build**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/prediction-service.ts && git commit -m "feat(frontend): add Zod validation to prediction-service"
```

---

## GRUP 3 — En Büyük Servis

### Task 6: `admin-service.ts` Zod Validation

**Files:**
- Modify: `frontend/src/schemas/services.ts`
- Modify: `frontend/src/services/api/admin-service.ts`

> ⚠️ Bu dosya 6 ayrı API export içeriyor (`adminApi`, `adminUsersApi`, `adminRolesApi`, `adminMlApi`, `adminImportsApi`, `adminMaintenanceApi`, `adminHealthApi`, `adminNotificationsApi`). Her birini sırayla işle.

> ⚠️ `adminApi.updateConfig` ve POST fire-and-forget'lar validate etme — sadece GET + CREATE + LIST response'larını validate et.

- [ ] **Step 1: Schema'ları `services.ts`'e ekle**

```typescript
// ─── Admin Service Schemas ────────────────────────────────────────────────────

export const AdminConfigItemSchema = z.object({
    anahtar: z.string(),
    deger: z.unknown(),
    tip: z.string(),
    birim: z.string().optional().nullable(),
    min_deger: z.number().optional().nullable(),
    max_deger: z.number().optional().nullable(),
    grup: z.string(),
    aciklama: z.string().optional().nullable(),
    yeniden_baslat: z.boolean(),
})

export const AdminUserRecordSchema = z.object({
    id: z.number(),
    email: z.string().optional().nullable(),
    ad_soyad: z.string(),
    aktif: z.boolean(),
    rol_id: z.number().optional().nullable(),
    son_giris: z.string().optional().nullable(),
    rol: z.object({
        id: z.number().optional(),
        ad: z.string().optional(),
        yetkiler: z.record(z.boolean()).optional(),
    }).optional().nullable(),
}).passthrough()

export const AdminRoleRecordSchema = z.object({
    id: z.number(),
    ad: z.string(),
    yetkiler: z.record(z.boolean()),
})

export const AdminTrainingQueueItemSchema = z.object({
    id: z.number(),
    arac_id: z.number().optional().nullable(),
    durum: z.string().optional().nullable(),
    metrics: z.object({
        algorithm: z.string().optional(),
        rmse: z.number().optional(),
    }).optional().nullable(),
    training_time_seconds: z.number().optional().nullable(),
    error_message: z.string().optional().nullable(),
    trigger_reason: z.string().optional().nullable(),
    created_at: z.string(),
})

export const AdminImportHistoryItemSchema = z.object({
    id: z.number().optional(),
    status: z.string().optional(),
    created_at: z.string().optional(),
    file_name: z.string().optional(),
}).passthrough()

export const AdminMaintenanceAlertSchema = z.object({
    id: z.number().optional(),
    arac_id: z.number().optional(),
    tip: z.string().optional(),
    aciklama: z.string().optional(),
    olusturma_tarihi: z.string().optional(),
}).passthrough()

export const AdminHealthSchema = z.object({
    status: z.string().optional(),
    services: z.record(z.unknown()).optional(),
    uptime: z.number().optional(),
}).passthrough()

export const AdminNotificationRuleSchema = z.object({
    id: z.number().optional(),
    olay_tipi: z.string(),
    kanallar: z.array(z.string()),
    alici_rol_id: z.number(),
    aktif: z.boolean().optional(),
}).passthrough()
```

- [ ] **Step 2: `admin-service.ts` güncelle — `adminApi`**

```typescript
import { validateResponse } from '../../lib/api-validator'
import {
    AdminConfigItemSchema,
    AdminUserRecordSchema,
    AdminRoleRecordSchema,
    AdminTrainingQueueItemSchema,
    AdminImportHistoryItemSchema,
    AdminMaintenanceAlertSchema,
    AdminHealthSchema,
    AdminNotificationRuleSchema,
} from '../../schemas/services'

// adminApi.getConfigs:
return validateResponse(z.array(AdminConfigItemSchema), data, 'adminApi.getConfigs')

// adminApi.getConfig:
return validateResponse(AdminConfigItemSchema, data, 'adminApi.getConfig')

// adminApi.updateConfig — mutation, validate etme (sadece error handling)
```

- [ ] **Step 3: `admin-service.ts` güncelle — diğer API'ler**

```typescript
// adminUsersApi.getAll:
return validateResponse(z.array(AdminUserRecordSchema), data, 'adminUsersApi.getAll')

// adminUsersApi.create:
return validateResponse(AdminUserRecordSchema, data, 'adminUsersApi.create')

// adminUsersApi.update:
return validateResponse(AdminUserRecordSchema, data, 'adminUsersApi.update')

// adminRolesApi.getAll:
return validateResponse(z.array(AdminRoleRecordSchema), data, 'adminRolesApi.getAll')

// adminMlApi.getQueue:
return validateResponse(z.array(AdminTrainingQueueItemSchema), data, 'adminMlApi.getQueue')

// adminImportsApi.getHistory:
return validateResponse(z.array(AdminImportHistoryItemSchema), data, 'adminImportsApi.getHistory')

// adminMaintenanceApi.getAlerts:
return validateResponse(z.array(AdminMaintenanceAlertSchema), data, 'adminMaintenanceApi.getAlerts')

// adminHealthApi.getHealth:
return validateResponse(AdminHealthSchema, data, 'adminHealthApi.getHealth')

// adminNotificationsApi.getRules:
return validateResponse(z.array(AdminNotificationRuleSchema), data, 'adminNotificationsApi.getRules')

// Mutation'lar (triggerTraining, rollback, markComplete, resetCircuitBreaker,
// triggerBackup, createRule, delete) — validate etme
```

- [ ] **Step 4: TypeScript kontrolü + build**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS" | head -20
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd D:\PROJECT\LOJINEXT && git add frontend/src/schemas/services.ts frontend/src/services/api/admin-service.ts && git commit -m "feat(frontend): add Zod validation to admin-service"
```

---

## Son Doğrulama

- [ ] **Tüm build temiz çalışıyor**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npm run build 2>&1 | tail -5
```

- [ ] **TypeScript sıfır hata**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx tsc --noEmit 2>&1 | grep -v node_modules | grep "error TS"
```

- [ ] **Vitest geçiyor**

```bash
cd D:\PROJECT\LOJINEXT\frontend && npx vitest --run 2>&1 | tail -10
```

---

## Özet Tablo

| Task | Servis | Endpoint sayısı | Zorluk |
|------|--------|-----------------|--------|
| 1 | ai-service + weather-service | 5 | Kolay |
| 2 | auth-service | 2 | Kolay |
| 3 | report-service | 7 (2 Blob hariç) | Orta |
| 4 | preference-service | 2 | Kolay |
| 5 | prediction-service | 6 | Orta |
| 6 | admin-service | 14 (6 mutation hariç) | Karmaşık |

**Toplam:** ~36 endpoint, 7 servis

---

## Genel Kurallar (Tüm Task'lar İçin)

1. **Blob response'ları validate etme** — `downloadPdf`, `downloadExcel`, binary return'lar
2. **Mutation'ları validate etme** — POST/PUT/PATCH/DELETE fire-and-forget'lar (sadece 200/error önemli)
3. **`.passthrough()`** — Backend'den ek alanlar gelebiliyorsa ekle; Zod bilinmeyen alanları tamamen kesmez
4. **`z.unknown()`** — `any` yerine; tip-safe ama içeriği doğrulamaz
5. **Her task'tan sonra** `tsc --noEmit` ve `npm run build` çalıştır
6. **Schema'ları** `services.ts`'e ekle, her task kendi bloğunu ekler (birbirinin üstüne yazar değil)
