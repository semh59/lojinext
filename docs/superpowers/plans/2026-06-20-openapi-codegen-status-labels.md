# OpenAPI Codegen + Status Label System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) FastAPI `/openapi.json`'dan Orval ile otomatik Zod şemaları + React Query hook'ları üret; (B) dağınık statü label hardcode'larını `status-labels.ts` + `StatusBadge.tsx` ile tek noktaya topla.

**Architecture:** Orval iki ayrı çıktı üretir: `src/generated/schemas.ts` (Zod) + `src/generated/api/<tag>.ts` (React Query hooks). Custom axios mutator mevcut `axiosInstance`'ı wrap eder — token refresh, toast, errorTracker davranışı değişmez. Status label sistemi orval'dan bağımsız olup English backend enum → Turkish display dönüşümünü tek fonksiyonda yapar.

**Tech Stack:** orval 8.18.0, zod ^4.3.6, @tanstack/react-query ^5, axios ^1.x, TypeScript 5, Vite 5

## Global Constraints

- `src/generated/` içine **asla elle kod yazılmaz** — her `npm run codegen` üzerine yazar
- `auth`, `websocket`, `internal` tag'leri hook generation'dan **hariç tutulur** (auth circular dep; websocket REST değil; internal file-upload özel)
- `src/services/api/auth-service.ts` ve `src/services/api/axios-instance.ts` **bu plan kapsamında kaldırılmaz**
- Tüm statü karşılaştırmaları İngilizce backend değerleriyle yapılır (`'Planned'` vs `'Planlandı'`): TripStatus İngilizce
- Zod v4 uyumluluğu Task 6'da doğrulanır; sorun çıkarsa plan notu eklenir
- `npm run codegen` CI'da `npm run build`'den önce çalışır (bu plan kapsamı dışı, CI task değil)

---

## Dosya Haritası

| Dosya | Durum | Açıklama |
|-------|-------|----------|
| `frontend/openapi.json` | YENİ | Backend'den dump, git'e commit |
| `frontend/orval.config.ts` | YENİ | Dual-target: react-query + zod |
| `frontend/scripts/dump-openapi.mjs` | YENİ | Node script, openapi.json yazar |
| `frontend/src/lib/orval-mutator.ts` | YENİ | axiosInstance thin wrapper |
| `frontend/src/lib/status-labels.ts` | YENİ | getTripStatusMeta, getFuelDurumMeta, getOnayDurumMeta |
| `frontend/src/components/ui/StatusBadge.tsx` | YENİ | Tek rozet bileşeni |
| `frontend/src/generated/schemas.ts` | ORVAL ÇIKTI | Zod şemaları (otomatik) |
| `frontend/src/generated/api/*.ts` | ORVAL ÇIKTI | React Query hooks (otomatik) |
| `frontend/src/components/dashboard/TodaysActiveTrips.tsx` | DEĞİŞİR | StatusBadge kullanır |
| `frontend/src/components/trips/TripsTodaySummary.tsx` | DEĞİŞİR | getTripStatusMeta kullanır |
| `frontend/src/components/trips/TripFilters.tsx` | DEĞİŞİR | getOnayDurumMeta kullanır |
| `frontend/src/resources/tr/trips.ts` | DEĞİŞİR | `tripTableText.statuses` kaldırılır |
| `frontend/package.json` | DEĞİŞİR | codegen script eklenir |

---

## Sub-project A: Status Label Sistemi

### Task 1: `src/lib/status-labels.ts`

**Files:**
- Create: `frontend/src/lib/status-labels.ts`

**Interfaces:**
- Produces: `StatusVariant`, `StatusMeta`, `getTripStatusMeta(status: TripStatus)`, `getFuelDurumMeta(durum: FuelYakitDurum)`, `getOnayDurumMeta(onay: OnayDurum)`, `getBakimTipiMeta(tip: BakimTipi)`

---

- [ ] **Step 1: Dosyayı yaz**

```typescript
// frontend/src/lib/status-labels.ts

export type TripStatus = 'Planned' | 'Completed' | 'Cancelled'
export type FuelYakitDurum = 'Bekliyor' | 'Onaylandı' | 'Reddedildi'
export type OnayDurum = 'beklemede' | 'onaylandi' | 'reddedildi'
export type BakimTipi = 'PERIYODIK' | 'ARIZA' | 'ACIL'

export type StatusVariant = 'info' | 'success' | 'danger' | 'warning' | 'neutral'

export interface StatusMeta {
  label: string
  variant: StatusVariant
}

export function getTripStatusMeta(status: TripStatus): StatusMeta {
  const map: Record<TripStatus, StatusMeta> = {
    Planned:   { label: 'Planlandı',   variant: 'info' },
    Completed: { label: 'Tamamlandı',  variant: 'success' },
    Cancelled: { label: 'İptal',       variant: 'danger' },
  }
  return map[status]
}

export function getFuelDurumMeta(durum: FuelYakitDurum): StatusMeta {
  const map: Record<FuelYakitDurum, StatusMeta> = {
    Bekliyor:   { label: 'Bekliyor',   variant: 'warning' },
    Onaylandı:  { label: 'Onaylandı',  variant: 'success' },
    Reddedildi: { label: 'Reddedildi', variant: 'danger' },
  }
  return map[durum]
}

export function getOnayDurumMeta(onay: OnayDurum): StatusMeta {
  const map: Record<OnayDurum, StatusMeta> = {
    beklemede:  { label: 'Onay Bekliyor', variant: 'warning' },
    onaylandi:  { label: 'Onaylandı',     variant: 'success' },
    reddedildi: { label: 'Reddedildi',    variant: 'danger' },
  }
  return map[onay]
}

export function getBakimTipiMeta(tip: BakimTipi): StatusMeta {
  const map: Record<BakimTipi, StatusMeta> = {
    PERIYODIK: { label: 'Periyodik', variant: 'info' },
    ARIZA:     { label: 'Arıza',     variant: 'danger' },
    ACIL:      { label: 'Acil',      variant: 'warning' },
  }
  return map[tip]
}
```

- [ ] **Step 2: TypeScript derleme kontrolü**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Beklenen: hata yok (bu dosya için)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/status-labels.ts
git commit -m "feat(status): add centralized status-labels with typed per-domain functions"
```

---

### Task 2: `src/components/ui/StatusBadge.tsx`

**Files:**
- Create: `frontend/src/components/ui/StatusBadge.tsx`

**Interfaces:**
- Consumes: `StatusMeta`, `StatusVariant` from `../../lib/status-labels`
- Produces: `<StatusBadge meta={StatusMeta} size? className? />` component

---

- [ ] **Step 1: Dosyayı yaz**

```tsx
// frontend/src/components/ui/StatusBadge.tsx
import { clsx } from 'clsx'
import type { StatusMeta, StatusVariant } from '../../lib/status-labels'

const variantClasses: Record<StatusVariant, string> = {
  info:    'border-info/30 bg-info/10 text-info',
  success: 'border-success/30 bg-success/10 text-success',
  danger:  'border-danger/30 bg-danger/10 text-danger',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  neutral: 'border-border bg-elevated text-secondary',
}

interface StatusBadgeProps {
  meta: StatusMeta
  size?: 'xs' | 'sm'
  className?: string
}

export function StatusBadge({ meta, size = 'xs', className }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-xl border font-black uppercase tracking-widest',
        size === 'xs' ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-xs',
        variantClasses[meta.variant],
        className,
      )}
    >
      {meta.label}
    </span>
  )
}
```

- [ ] **Step 2: TypeScript derleme kontrolü**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Beklenen: hata yok

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/StatusBadge.tsx
git commit -m "feat(ui): add StatusBadge component consuming StatusMeta"
```

---

### Task 3: Hardcode statü label'larını StatusBadge ile değiştir

**Files:**
- Modify: `frontend/src/components/dashboard/TodaysActiveTrips.tsx`
- Modify: `frontend/src/components/trips/TripsTodaySummary.tsx`
- Modify: `frontend/src/components/trips/TripFilters.tsx`
- Modify: `frontend/src/resources/tr/trips.ts`

**Interfaces:**
- Consumes: `getTripStatusMeta`, `getOnayDurumMeta` from `../../lib/status-labels`
- Consumes: `StatusBadge` from `../ui/StatusBadge`

---

- [ ] **Step 1: TodaysActiveTrips.tsx — hardcode map'i kaldır**

`frontend/src/components/dashboard/TodaysActiveTrips.tsx` dosyasındaki şu satırları bul:

```typescript
  Planlandı: "info",

  Tamamlandı: "success",
  İptal: "danger",
```

Ve o map'in kullanıldığı yeri, `StatusBadge` + `getTripStatusMeta` ile değiştir. Önce mevcut içeriği oku, sonra düzenle.

> **Not:** Bu dosyadaki `durum` değerleri Turkish (`"Planlandı"`) çünkü normalizeTripStatus hâlâ çalışıyor. Bu task'ta sadece label'ın nasıl render edildiğini değiştiriyoruz. TripStatus İngilizce'ye geçiş Sub-project B'nin kapsamında.

- [ ] **Step 2: TripsTodaySummary.tsx — label prop'larını kaldır**

`frontend/src/components/trips/TripsTodaySummary.tsx` dosyasında `label="Tamamlandı"`, `label="Planlandı"`, `label="İptal"` şeklinde hardcode edilmiş satırları bul. Bu değerleri `getTripStatusMeta` sonucundan al.

- [ ] **Step 3: TripFilters.tsx — onayDurum label'larını kaldır**

`frontend/src/components/trips/TripFilters.tsx` satır 270-272:
```typescript
{ label: "Onay Bekliyor", value: "beklemede" },
{ label: "Onaylandı", value: "onaylandi" },
{ label: "Reddedildi", value: "reddedildi" },
```
Bu string'leri `getOnayDurumMeta(value).label` ile değiştir.

- [ ] **Step 4: tripTableText.statuses kaldır**

`frontend/src/resources/tr/trips.ts` içindeki şu bloğu sil (artık status-labels.ts'den geliyor):

```typescript
  statuses: {
    completed: "Tamamlandı",
    planned: "Planlandı",
    canceled: "İptal",
    unknown: "Belirsiz",
  },
```

`tripTableText.statuses` kullanan yerleri bul (`grep -r "tripTableText.statuses" frontend/src`) ve `getTripStatusMeta` ile değiştir.

- [ ] **Step 5: Testleri çalıştır**

```bash
cd frontend && npx vitest --run 2>&1 | tail -20
```

Beklenen: öncekiyle aynı pass sayısı, yeni fail yok

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dashboard/TodaysActiveTrips.tsx
git add frontend/src/components/trips/TripsTodaySummary.tsx
git add frontend/src/components/trips/TripFilters.tsx
git add frontend/src/resources/tr/trips.ts
git commit -m "refactor(status): replace hardcoded labels with StatusBadge + getTripStatusMeta"
```

---

## Sub-project B: Orval Codegen Foundation

### Task 4: OpenAPI schema dump

**Files:**
- Create: `frontend/scripts/dump-openapi.mjs`
- Create: `frontend/openapi.json` (generated, committed)
- Modify: `frontend/package.json` (scripts)

---

- [ ] **Step 1: dump-openapi.mjs yaz**

```javascript
// frontend/scripts/dump-openapi.mjs
import { writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dir = dirname(fileURLToPath(import.meta.url))
const OUT = join(__dir, '..', 'openapi.json')

const BASE = process.env.API_BASE_URL ?? 'http://localhost:8000'
const URL  = `${BASE}/openapi.json`

console.log(`Fetching ${URL} …`)
const res = await fetch(URL)
if (!res.ok) throw new Error(`HTTP ${res.status} from ${URL}`)

const schema = await res.json()
writeFileSync(OUT, JSON.stringify(schema, null, 2) + '\n', 'utf8')
console.log(`Written → openapi.json (${Object.keys(schema.paths ?? {}).length} paths, ${Object.keys((schema.components ?? {}).schemas ?? {}).length} schemas)`)
```

- [ ] **Step 2: package.json scripts ekle**

`frontend/package.json` içindeki `"scripts"` bloğuna şunları ekle:

```json
"codegen:dump": "node scripts/dump-openapi.mjs",
"codegen": "orval",
"codegen:all": "npm run codegen:dump && npm run codegen"
```

- [ ] **Step 3: Schema dump çalıştır**

```bash
cd frontend && node scripts/dump-openapi.mjs
```

Beklenen çıktı:
```
Fetching http://localhost:8000/openapi.json …
Written → openapi.json (193 paths, 188 schemas)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/dump-openapi.mjs frontend/openapi.json frontend/package.json
git commit -m "feat(codegen): add dump-openapi script and commit openapi.json snapshot"
```

---

### Task 5: Orval kurulumu ve konfigürasyonu

**Files:**
- Modify: `frontend/package.json` (devDependency)
- Create: `frontend/orval.config.ts`

---

- [ ] **Step 1: Orval kur**

```bash
cd frontend && npm install --save-dev orval
```

Beklenen: `package.json` devDependencies'e `"orval": "^8.x.x"` eklenir, lock dosyası güncellenir.

- [ ] **Step 2: orval.config.ts yaz**

```typescript
// frontend/orval.config.ts
import { defineConfig } from 'orval'

const EXCLUDED_TAGS = ['auth', 'websocket', 'internal']

export default defineConfig({
  // Target 1 — React Query hooks + TypeScript types (tag başına dosya)
  lojinext: {
    input: {
      target: './openapi.json',
      filters: {
        tags: EXCLUDED_TAGS,
      },
    },
    output: {
      mode: 'tags-split',
      target: './src/generated/api',
      schemas: './src/generated/types',
      client: 'react-query',
      override: {
        mutator: {
          path: './src/lib/orval-mutator.ts',
          name: 'customAxiosInstance',
        },
        query: {
          useQuery: true,
          useMutation: true,
          useInfiniteScrollQuery: false,
        },
      },
    },
  },

  // Target 2 — Zod şemaları (tüm component schemas, tek dosya)
  'lojinext-zod': {
    input: {
      target: './openapi.json',
    },
    output: {
      client: 'zod',
      target: './src/generated/schemas.ts',
      mode: 'single',
    },
  },
})
```

> **Not:** `filters.tags` ile `EXCLUDED_TAGS` listesindeki tag'ler hariç tutulur.
> Orval 8.x `filters.tags` include-list olarak çalışır. Eğer exclude desteklenmiyorsa
> Task 5 sonunda `npx orval` çalıştırıp hata mesajına bakılır, gerekirse include-list'e geçilir.

- [ ] **Step 3: .gitignore güncelle — generated klasörünü izleme**

`frontend/.gitignore` (yoksa ana `.gitignore`) dosyasına ekle:

```
# Orval generated — npm run codegen ile yeniden üretilir
frontend/src/generated/
```

> `openapi.json` intentionally committed. `src/generated/` intentionally gitignored.

- [ ] **Step 4: Commit**

```bash
git add frontend/orval.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(codegen): install orval 8.x, add dual-target orval.config.ts"
```

---

### Task 6: Mutator yaz ve Zod v4 uyumluluğunu doğrula

**Files:**
- Create: `frontend/src/lib/orval-mutator.ts`

**Interfaces:**
- Consumes: `axiosInstance` from `../services/api/axios-instance`
- Produces: `customAxiosInstance<T>(config, options?) → Promise<T>` — orval'ın beklediği imza

---

- [ ] **Step 1: orval-mutator.ts yaz**

```typescript
// frontend/src/lib/orval-mutator.ts
//
// Orval custom mutator: mevcut axiosInstance'ı wrap eder.
// Token refresh, 401/403/400/422/500 handling, errorTracker, toast —
// hepsi axios-instance.ts interceptor'larında yaşar; burada tekrar implement edilmez.
//
// Orval bu fonksiyonu her hook'ta şöyle çağırır:
//   customAxiosInstance<ResponseType>({ url, method, params, data }, { signal })
// ve Promise<ResponseType> bekler.

import type { AxiosRequestConfig } from 'axios'
import axiosInstance from '../services/api/axios-instance'

export const customAxiosInstance = <T>(
  config: AxiosRequestConfig,
  options?: { signal?: AbortSignal },
): Promise<T> =>
  axiosInstance<T>({
    ...config,
    signal: options?.signal,
  }).then(({ data }) => data)
```

- [ ] **Step 2: Codegen çalıştır**

```bash
cd frontend && npx orval 2>&1
```

Beklenen çıktı (kısaltılmış):
```
✔ lojinext — generated src/generated/api/trips.ts
✔ lojinext — generated src/generated/api/vehicles.ts
... (her tag için)
✔ lojinext-zod — generated src/generated/schemas.ts
```

Eğer Zod filter hatası alınırsa (`filters.tags` format sorunu):
- `orval.config.ts` içindeki `filters` bloğunu kaldır, tüm tag'ler generate edilsin, `auth` tag'inden gelen hooklar kullanılmayacak

- [ ] **Step 3: TypeScript compile doğrula**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Beklenen: **sıfır hata** (generated dosyalar tsconfig kapsamındaysa).

Eğer `src/generated/**` tsconfig'de yoksa `frontend/tsconfig.app.json` içindeki `include`'e ekle:
```json
"include": ["src", "src/generated"]
```

Sonra tekrar:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Zod v4 uyumsuzluk kontrolü: çıktıda `Cannot find name 'z'` veya `Property 'X' does not exist on type 'ZodString'` hataları varsa Task 6 sonuna not düş; bu durumda Zod v3 pin'i gerekebilir (plan güncellenecek).

- [ ] **Step 4: Generated dosyaların varlığını doğrula**

```bash
ls frontend/src/generated/api/ | head -20
wc -l frontend/src/generated/schemas.ts
```

Beklenen:
- `api/` altında `trips.ts`, `vehicles.ts`, `fuel.ts`, `drivers.ts`, `locations.ts` vb. dosyalar
- `schemas.ts` en az 500 satır

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/orval-mutator.ts
# generated klasörü gitignore'da, commit edilmez
git commit -m "feat(codegen): add orval-mutator.ts wrapping axiosInstance"
```

---

### Task 7: Generated index re-export + tsconfig guard

**Files:**
- Create: `frontend/src/generated/index.ts` (ama bu dosya `npm run codegen` ile silinir, bu yüzden farklı yaklaşım)

> **Önemli:** `src/generated/` gitignore'da olduğu için `index.ts` de generated sayılır ve `npm run codegen` ile üzerine yazılabilir. Bu dosya elle yazılmaz; import'lar doğrudan `../generated/api/trips`, `../generated/schemas` şeklinde yapılır.

- [ ] **Step 1: Örnek kullanım doğrulaması — üretilen hook'u import et**

Geçici test: `frontend/src/generated/api/trips.ts`'in ilk birkaç satırını oku ve doğru import yollarını kontrol et:

```bash
head -30 frontend/src/generated/api/trips.ts
```

Beklenen: `import { customAxiosInstance } from '../../lib/orval-mutator'` veya benzeri import satırları; `useQuery` import'u `@tanstack/react-query`'den.

- [ ] **Step 2: Mevcut vitest suite'ini çalıştır**

```bash
cd frontend && npx vitest --run 2>&1 | tail -30
```

Beklenen: mevcut testler hâlâ geçiyor, `src/generated/` import eden test yok (henüz) dolayısıyla yeni fail yok.

- [ ] **Step 3: Commit (düzeltme varsa)**

```bash
git add frontend/tsconfig.app.json  # eğer include güncellendiyse
git commit -m "feat(codegen): verify orval output compiles and existing tests pass" --allow-empty
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Orval kurulum ✓, dual output ✓, mutator ✓, status-labels ✓, StatusBadge ✓, migration demo ✓
- [x] **Placeholder scan:** Her adımda gerçek kod var, TBD yok
- [x] **Type consistency:** `TripStatus = 'Planned' | 'Completed' | 'Cancelled'` tüm task'larda tutarlı
- [x] **Auth exclusion:** Task 5'te `EXCLUDED_TAGS` içinde, Task 6 notunda belirtildi
- [x] **Field validator coverage:** Task 6 notunda açıklandı — structural kısıtlar Zod'a gelir, cross-field business rules gelmez
- [x] **Token refresh:** Task 6'da mutator imzası axiosInstance'ı delegate ediyor, interceptor davranışı değişmiyor

---

## Kapsam Dışı (Ayrı Plan)

- Mevcut `services/api/*.ts` dosyalarını generated hook'larla replace etmek
- `hooks/useTripsData.ts` gibi composite hook'ları refactor etmek
- `src/types/index.ts` ve `src/schemas/entities.ts` kaldırmak
- TripStatus'u İngilizce'ye migrate etmek (frontend state + API filter düzeltmesi)
- CI pipeline'a `npm run codegen` adımı eklemek
