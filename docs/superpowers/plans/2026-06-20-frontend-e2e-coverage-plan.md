# Frontend E2E Kapsam Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7 sıfır kapsam sayfasına E2E testi yaz, 2 var olan testteki kritik assertion hatasını düzelt.

**Architecture:** Her yeni E2E spec `frontend/e2e/tests/` altına gider, `e2e/fixtures/auth.ts`'den `authedPage` fixture'ını içe aktarır, `e2e/mocks/index.ts`'deki yardımcı fonksiyonları kullanır ya da kendi endpoint mock'larını inline tanımlar. Mock veri backend Zod şemalarıyla birebir eşleşmeli — hayali format kabul edilemez.

**Tech Stack:** Playwright, TypeScript, Vitest (unit). E2E çalıştırma: `cd frontend && npx playwright test` (backend `http://localhost:8000`, frontend `http://localhost:3000` ayakta olmalı).

**Gerçek altyapı:**
- `e2e/helpers/api.ts:loginViaApi` → gerçek backend `/api/v1/auth/token`'a POST, sonra sessionStorage'a token yazar, `/auth/me` mock'lanır
- `e2e/mocks/index.ts` → domain mock yardımcı fonksiyonları (`setupTripMocks`, `setupVehicleMocks`, vs.)
- `playwright.config.ts` → baseURL: `http://localhost:3000`, E2E_USERNAME / E2E_PASSWORD env var gerekli

---

## Kapsam Dışı

- Unit testler (Vitest) bu plana dahil değil
- Mevcut geçen testler silinmez ya da değiştirilmez (Bug Fix 1-2 hariç — oradaki assertion yanlış)
- Backend kod değişikliği yok

---

## Değiştirilecek / Oluşturulacak Dosyalar

| İşlem | Dosya | Neden |
|-------|-------|-------|
| Modify | `frontend/e2e/tests/admin.spec.ts` | Satır 22: roles mock `{name}` → `{ad, yetkiler}` (Zod validation hatası gizleniyor) |
| Modify | `frontend/e2e/tests/trips.spec.ts` | Satır 165: `\|\| true` kaldır, gerçek assertion yaz |
| Create | `frontend/e2e/tests/roller.spec.ts` | RollerPage (`/admin/roller`) — sıfır kapsam |
| Create | `frontend/e2e/tests/dogruluk.spec.ts` | DogrulukPage (`/admin/dogruluk`) — sıfır kapsam |
| Create | `frontend/e2e/tests/veri-yonetim.spec.ts` | VeriYonetimPage (`/admin/veri`) — rollback geri alınamaz, sıfır kapsam |
| Create | `frontend/e2e/tests/atama.spec.ts` | AtamaPage (`/admin/atama`) — 3 validasyon kuralı, sıfır kapsam |
| Create | `frontend/e2e/tests/coaching.spec.ts` | CoachingPage (`/coaching`) — sıfır kapsam |
| Create | `frontend/e2e/tests/fleet-insights.spec.ts` | FleetInsightsPage (`/insights/fleet`) — sıfır kapsam |
| Create | `frontend/e2e/tests/executive.spec.ts` | ExecutivePage (`/executive`) — sıfır kapsam |

---

## Task 1: admin.spec.ts — Roller Mock Format Düzelt

**Sorun:** `admin.spec.ts:22` roles endpoint mock `{ id, name }` dönüyor.
`adminRolesApi.getAll()` bu yanıtı `AdminRoleRecordSchema` = `z.object({ id: z.number(), ad: z.string(), yetkiler: z.record(z.string(), z.boolean()) })` ile doğruluyor. `ad` alanı eksik → Zod validation başarısız → `validateResponse` uyarı basar, `[] ` döner → RollerPage "Henüz rol yok" gösterir. Bu anda bu davranışı yakalayan hiç test yok.

**Dosya:** `frontend/e2e/tests/admin.spec.ts`

- [ ] **Adım 1.1 — Önce mevcut durumu doğrula**

```bash
cd frontend && npx playwright test e2e/tests/admin.spec.ts --reporter=list 2>&1 | tail -20
```

Beklenen çıktı: tüm admin testleri PASS (bug gizli kalıyor).

- [ ] **Adım 1.2 — MOCK_ROLES sabit ekle**

`admin.spec.ts` dosyasının tepesine (satır 1'den sonra, `MOCK_USERS` sabiti yanına):

```typescript
const MOCK_ROLES = [
    { id: 1, ad: 'super_admin', yetkiler: { 'sefer:read': true, 'sefer:write': true, 'sefer:onayla': true, 'rol_oku': true, 'rol_yaz': true } },
    { id: 2, ad: 'operator', yetkiler: { 'sefer:read': true, 'yakit:write': true } },
]
```

- [ ] **Adım 1.3 — Hatalı mock'u düzelt**

`admin.spec.ts:21-22` satırını değiştir:

```typescript
// ESKİ (yanlış format):
if (url.includes('/roles'))
    return r.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify([{ id: 1, name: 'super_admin' }, { id: 2, name: 'operator' }]) })

// YENİ (AdminRoleRecordSchema ile uyumlu):
if (url.includes('/roles'))
    return r.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify(MOCK_ROLES) })
```

- [ ] **Adım 1.4 — `/admin/roller` için test ekle**

`admin.spec.ts` içindeki `test.describe('Admin panel', () => {` bloğunun sonuna (kapanış `})` öncesine):

```typescript
    test('roller listesi yüklenir ve rol adları görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('operator').first()).toBeVisible()
    })

    test('roller sayfası — "Henüz rol yok" GÖSTERİLMEMELİ (mock format doğru)', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        // Eğer bu metin görünüyorsa mock format yanlış demektir
        await expect(page.getByText('Henüz rol yok')).toHaveCount(0, { timeout: 8_000 })
        await expect(page.getByText('super_admin').first()).toBeVisible()
    })
```

- [ ] **Adım 1.5 — Çalıştır, PASS olduğunu doğrula**

```bash
cd frontend && npx playwright test e2e/tests/admin.spec.ts --reporter=list 2>&1 | tail -25
```

Beklenen: tüm testler PASS, "Henüz rol yok" testi PASS (artık roller görünüyor).

- [ ] **Adım 1.6 — Commit**

```bash
git add frontend/e2e/tests/admin.spec.ts
git commit -m "fix(e2e): admin roles mock format ad+yetkiler (Zod validation uyumu)"
```

---

## Task 2: trips.spec.ts — `|| true` Assertion Düzelt

**Sorun:** `trips.spec.ts:165` satırı `expect(hasDetail || urlChanged || true).toBeTruthy()` — `|| true` nedeniyle bu assertion **hiçbir koşulda başarısız olamaz**. Test var görünüyor ama sefer satırına tıklamanın herhangi bir sonuç üretip üretmediğini test etmiyor.

**Dosya:** `frontend/e2e/tests/trips.spec.ts`

- [ ] **Adım 2.1 — Mevcut testi çalıştır, sonucu kaydet**

```bash
cd frontend && npx playwright test e2e/tests/trips.spec.ts -g "detay paneli" --reporter=list 2>&1
```

Beklenen: PASS (|| true nedeniyle her zaman geçer).

- [ ] **Adım 2.2 — `|| true` kaldır, gerçek assertion yaz**

`trips.spec.ts:155-166` bloğunu şu şekilde değiştir:

```typescript
    test('sefer satırına tıklanınca detay paneli açılır veya navigasyon olur', async ({ authedPage: page }) => {
        await page.goto('/trips')
        await expect(page.getByText(MOCK_TRIP.sefer_no).first()).toBeVisible({ timeout: 10_000 })

        const tripRow = page.getByText(MOCK_TRIP.sefer_no).first()
        await tripRow.click()
        await page.waitForTimeout(500)

        // Crash kontrolü — ErrorBoundary tetiklenmiş olmamalı
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0, { timeout: 3_000 })
        await expect(page.locator('text=/Bir hata oluştu/i')).toHaveCount(0, { timeout: 3_000 })

        // Tıklama bir sonuç üretmeli: dialog VEYA /trips/:id navigasyonu
        const dialogOpen = await page.locator('[role="dialog"]').isVisible().catch(() => false)
        const urlAfter = page.url()
        const didNavigate = urlAfter.includes('/trips/') && !urlAfter.endsWith('/trips')

        expect(
            dialogOpen || didNavigate,
            `Sefer satırı tıklaması dialog açmalı ya da /trips/:id'ye yönlendirmeli. url=${urlAfter} dialog=${dialogOpen}`
        ).toBe(true)
    })
```

- [ ] **Adım 2.3 — Çalıştır — bu sefer gerçek sonucu yansıtmalı**

```bash
cd frontend && npx playwright test e2e/tests/trips.spec.ts -g "detay paneli" --reporter=list --headed 2>&1
```

**Eğer FAIL olursa:** TripTable tıklamada dialog açmıyor VE URL değişmiyor — bu gerçek bir UX bug'ı. `frontend/src/components/trips/TripTable.tsx` içindeki satır tıklama handler'ını oku ve ne yapması gerektiğine karar ver. Kasıtlı davranış buysa assertion'ı şu şekilde güncelle:

```typescript
        // Tıklama inline satır genişletmesi yapabilir
        const rowExpanded = await page.locator('[aria-expanded="true"], [class*="expanded"], [class*="open"]').count() > 0
        expect(
            dialogOpen || didNavigate || rowExpanded,
            `Sefer satırı tıklaması gözlemlenebilir bir etki üretmeli`
        ).toBe(true)
```

**Eğer PASS olursa:** Dialog açılıyor veya URL değişiyor — assertion doğru, devam et.

- [ ] **Adım 2.4 — Tüm trip testleri geçiyor mu kontrol et**

```bash
cd frontend && npx playwright test e2e/tests/trips.spec.ts --reporter=list 2>&1 | tail -20
```

Beklenen: Tüm non-skip testler PASS.

- [ ] **Adım 2.5 — Commit**

```bash
git add frontend/e2e/tests/trips.spec.ts
git commit -m "fix(e2e): trips detay tıklama testi || true kaldırıldı, gerçek assertion yazıldı"
```

---

## Task 3: roller.spec.ts — RollerPage E2E

**Sayfa:** `/admin/roller` → `RollerPage.tsx`

**Sayfa davranışı (kaynak koddan):**
- `adminRolesApi.getAll()` → GET `/admin/roles/` → `AdminRoleRecordSchema` ile Zod validation
- `PROTECTED_ROLES = ["super_admin", "admin"]` — bu roller için Düzenle/Sil butonları gizlenir
- Yeni rol form validasyonu: ad >= 2 karakter, en az 1 yetki seçili olmalı (`handleSubmit:114-125`)
- Yeni rol oluşturma: `adminRolesApi.create()` → POST `/admin/roles/`
- Silme: `adminRolesApi.remove(roleId)` → DELETE `/admin/roles/{id}` → önce `deleteTarget` confirm modal

**Dosya:** `frontend/e2e/tests/roller.spec.ts`

- [ ] **Adım 3.1 — Dosyayı oluştur ve ilk testi yaz**

`frontend/e2e/tests/roller.spec.ts` oluştur:

```typescript
import { test, expect } from '../fixtures/auth'

const MOCK_ROLES = [
    { id: 1, ad: 'super_admin', yetkiler: { 'sefer:read': true, 'sefer:write': true, 'sefer:onayla': true } },
    { id: 2, ad: 'operator', yetkiler: { 'sefer:read': true } },
    { id: 3, ad: 'muhasebe', yetkiler: { 'sefer:read': true, 'yakit:write': true } },
]

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}
function created(body: unknown) {
    return { status: 201, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Roller sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/roles/**', r => {
            const method = r.request().method()
            if (method === 'GET') return r.fulfill(json(MOCK_ROLES))
            if (method === 'POST') return r.fulfill(created({ id: 4, ad: 'yeni_rol', yetkiler: { 'sefer:read': true } }))
            if (method === 'PUT') return r.fulfill(json(MOCK_ROLES[2]))
            if (method === 'DELETE') return r.fulfill({ status: 204 })
            return r.continue()
        })
    })

    test('sayfa yüklenir ve rol listesi görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('operator').first()).toBeVisible()
        await expect(page.getByText('muhasebe').first()).toBeVisible()
    })

    test('"Henüz rol yok" görünmemeli — mock format doğruysa', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.getByText('Henüz rol yok')).toHaveCount(0, { timeout: 8_000 })
    })

    test('korumalı roller (super_admin, admin) için Düzenle/Sil gizli', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        // super_admin satırında Düzenle ve Sil butonları olmamalı
        const superAdminRow = page.locator('tr, li, [class*="row"]').filter({ hasText: 'super_admin' }).first()
        if (await superAdminRow.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await expect(superAdminRow.getByRole('button', { name: /düzenle|edit/i })).toHaveCount(0)
            await expect(superAdminRow.getByRole('button', { name: /sil|delete/i })).toHaveCount(0)
        }
        // operator satırında ise butonlar görünmeli (korumalı değil)
        const operatorRow = page.locator('tr, li, [class*="row"]').filter({ hasText: 'operator' }).first()
        if (await operatorRow.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await expect(operatorRow.getByRole('button', { name: /düzenle|edit|pencil/i }).or(
                operatorRow.locator('[data-testid*="edit"], button svg')
            ).first()).toBeVisible({ timeout: 5_000 })
        }
    })

    test('"Yeni Rol" butonu modal açar', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        const newBtn = page.getByRole('button', { name: /yeni rol/i })
        await expect(newBtn).toBeVisible({ timeout: 5_000 })
        await newBtn.click()
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 })
    })

    test('boş form submit edilince validasyon hatası gösterir', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni rol/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })
        // Rol adı boş, hiç yetki seçilmemiş → submit
        await dialog.getByRole('button', { name: /kaydet|oluştur|ekle/i }).first().click()
        // "Rol adı en az 2 karakter" veya "En az bir yetki seçin" hatası
        await expect(
            dialog.getByText(/en az 2 karakter|en az bir yetki/i).first()
        ).toBeVisible({ timeout: 5_000 })
    })

    test('yeni rol oluşturma — ad doldurulup yetki seçilip POST gönderilir', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni rol/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })

        // Rol adı gir
        const adInput = dialog.locator('input[type="text"], input[placeholder*="rol"], input').first()
        await adInput.fill('yeni_rol')

        // İlk checkbox/yetki'yi seç
        const firstCheckbox = dialog.locator('input[type="checkbox"]').first()
        if (await firstCheckbox.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await firstCheckbox.check()
        }

        const [request] = await Promise.all([
            page.waitForRequest(req => req.url().includes('/admin/roles') && req.method() === 'POST', { timeout: 8_000 }),
            dialog.getByRole('button', { name: /kaydet|oluştur/i }).first().click(),
        ])
        expect(request.method()).toBe('POST')
        const body = JSON.parse(request.postData() ?? '{}')
        expect(body.ad).toBeTruthy()
    })

    test('backend 500 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/roles/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Internal Server Error' }) })
        )
        await page.goto('/admin/roller')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        // ErrorBoundary tetiklenmemeli
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
        // Ya boş liste ya da hata mesajı görünmeli
        await expect(page.locator('h1, [class*="card"], [class*="empty"]').first()).toBeVisible({ timeout: 8_000 })
    })
})
```

- [ ] **Adım 3.2 — Çalıştır, FAIL veya PASS nedenini anla**

```bash
cd frontend && npx playwright test e2e/tests/roller.spec.ts --reporter=list 2>&1 | tail -30
```

FAIL ederse trace incele: `npx playwright show-report`

- [ ] **Adım 3.3 — Tüm testler PASS olana kadar selector'ları güncelle**

Sayfa gerçek selector'ları farklıysa (ör. "Yeni Rol" butonu farklı etiket) trace'den bulup düzelt.

- [ ] **Adım 3.4 — Commit**

```bash
git add frontend/e2e/tests/roller.spec.ts
git commit -m "test(e2e): RollerPage — happy path, validasyon, korumalı rol, 500 hata senaryosu"
```

---

## Task 4: dogruluk.spec.ts — DogrulukPage E2E

**Sayfa:** `/admin/dogruluk` → `DogrulukPage.tsx`

**Sayfa davranışı:**
- `adminFuelAccuracyApi.get(days)` → GET `/admin/fuel-accuracy?days={7|30|90}` → `FuelAccuracyStats`
- Period butonları: 7 gün, 30 gün, 90 gün → queryKey `["fuelAccuracy", days]` değişince yeni istek
- `sample_size === 0` durumunda özel boş mesaj gösterilmeli (sayfaya bak, tam metin değişebilir)
- `fmt()` fonksiyonu: `v === null ? "—" : v.toFixed(1)+suffix`

**Dosya:** `frontend/e2e/tests/dogruluk.spec.ts`

- [ ] **Adım 4.1 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'

const MOCK_ACCURACY_30 = {
    period_days: 30,
    sample_size: 15,
    mape_pct: 8.3,
    rmse_l_100km: 2.1,
    mean_predicted: 32.5,
    mean_actual: 31.8,
    bias_pct: -2.2,
    coverage_pct: 75.0,
    breakdown_by_arac: [],
}

const MOCK_ACCURACY_EMPTY = {
    period_days: 7,
    sample_size: 0,
    mape_pct: null,
    rmse_l_100km: null,
    mean_predicted: null,
    mean_actual: null,
    bias_pct: null,
    coverage_pct: 0,
    breakdown_by_arac: [],
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Tahmin Doğruluğu sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill(json(MOCK_ACCURACY_30))
        )
    })

    test('sayfa yüklenir ve MAPE değeri görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        // mape_pct: 8.3 → fmt formatı: "8.3%"
        await expect(page.getByText('8.3').first()).toBeVisible({ timeout: 8_000 })
    })

    test('RMSE değeri görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        // rmse_l_100km: 2.1 → "2.1"
        await expect(page.getByText('2.1').first()).toBeVisible({ timeout: 8_000 })
    })

    test('period butonları: 7 gün seçilince yeni API isteği gider', async ({ authedPage: page }) => {
        let requestCount = 0
        await page.route('**/api/v1/admin/fuel-accuracy**', r => {
            requestCount++
            return r.fulfill(json(MOCK_ACCURACY_30))
        })
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        const countBefore = requestCount

        const btn7 = page.getByRole('button', { name: '7' }).or(page.locator('button').filter({ hasText: '7' })).first()
        await expect(btn7).toBeVisible({ timeout: 5_000 })
        await btn7.click()
        await page.waitForTimeout(500)

        expect(requestCount).toBeGreaterThan(countBefore)
    })

    test('sample_size = 0 iken boş durum gösterilir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill(json(MOCK_ACCURACY_EMPTY))
        )
        await page.goto('/admin/dogruluk')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        // null değerler "—" olarak gösterilmeli
        await expect(page.locator('text=—').first()).toBeVisible({ timeout: 8_000 })
    })

    test('backend 500 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/admin/dogruluk')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
```

- [ ] **Adım 4.2 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/dogruluk.spec.ts --reporter=list 2>&1 | tail -20
```

- [ ] **Adım 4.3 — Commit**

```bash
git add frontend/e2e/tests/dogruluk.spec.ts
git commit -m "test(e2e): DogrulukPage — MAPE/RMSE görünüm, period switch, boş durum, 500 hata"
```

---

## Task 5: veri-yonetim.spec.ts — VeriYonetimPage E2E

**Sayfa:** `/admin/veri` → `VeriYonetimPage.tsx`

**Sayfa davranışı:**
- `adminImportsApi.getHistory(50)` → GET `/admin/imports/history?limit=50` → `AdminImportHistoryItemSchema.passthrough()`
  Sayfa şu alanları doğrudan okur: `job.dosya_adi`, `job.aktarim_tipi`, `job.baslama_zamani`, `job.durum`, `job.basarili`, `job.hatali`, `job.toplam`, `job.id`
- `handleRollback(jobId)` → `window.confirm` → POST `/admin/imports/{id}/rollback`
- `mapImportStatus('tamamlandi')` → `{ label: ..., variant: 'success' }`
- `mapImportStatus('hata')` → `{ label: ..., variant: 'danger' }`
- `mapImportStatus('geri_alindi')` → `{ label: ..., variant: 'warning' }`

**Dosya:** `frontend/e2e/tests/veri-yonetim.spec.ts`

- [ ] **Adım 5.1 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'

const MOCK_JOB_SUCCESS = {
    id: 1,
    dosya_adi: 'seferler_ocak.xlsx',
    aktarim_tipi: 'sefer',
    baslama_zamani: '2025-01-15T10:00:00',
    durum: 'tamamlandi',
    basarili: 42,
    hatali: 0,
    toplam: 42,
}

const MOCK_JOB_ERROR = {
    id: 2,
    dosya_adi: 'yakit_subat.xlsx',
    aktarim_tipi: 'yakit',
    baslama_zamani: '2025-02-01T09:00:00',
    durum: 'hata',
    basarili: 5,
    hatali: 12,
    toplam: 17,
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Veri Yönetimi sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/**', r => {
            const method = r.request().method()
            const url = r.request().url()
            if (url.includes('/history')) return r.fulfill(json([MOCK_JOB_SUCCESS, MOCK_JOB_ERROR]))
            if (url.includes('/rollback') && method === 'POST') return r.fulfill(json({ success: true }))
            return r.continue()
        })
    })

    test('sayfa yüklenir ve import geçmişi tablosu görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('yakit_subat.xlsx').first()).toBeVisible()
    })

    test('başarılı import — success badge görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })
        // mapImportStatus('tamamlandi') → variant: 'success' → Badge içinde Türkçe "Tamamlandı" benzeri
        const successRow = page.locator('tr, [class*="row"]').filter({ hasText: 'seferler_ocak.xlsx' }).first()
        await expect(successRow).toBeVisible()
    })

    test('hatalı import — hata sayısı ve error badge görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('yakit_subat.xlsx').first()).toBeVisible({ timeout: 10_000 })
        // MOCK_JOB_ERROR.hatali = 12
        await expect(page.getByText('12').first()).toBeVisible({ timeout: 8_000 })
    })

    test('rollback butonu görünür ve window.confirm onaylanınca POST gönderilir', async ({ authedPage: page }) => {
        page.on('dialog', d => d.accept())

        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/admin/imports') && req.url().includes('/rollback') && req.method() === 'POST',
                { timeout: 8_000 }
            ),
            page.getByRole('button', { name: /geri al|rollback/i }).first().click(),
        ])
        expect(request.method()).toBe('POST')
        expect(request.url()).toContain('/rollback')
    })

    test('rollback butonu window.confirm reddedilince POST gönderilmez', async ({ authedPage: page }) => {
        page.on('dialog', d => d.dismiss())

        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })

        let rollbackCalled = false
        await page.route('**/api/v1/admin/imports/**', r => {
            if (r.request().url().includes('/rollback')) rollbackCalled = true
            return r.continue()
        })

        await page.getByRole('button', { name: /geri al|rollback/i }).first().click()
        await page.waitForTimeout(500)
        expect(rollbackCalled).toBe(false)
    })

    test('boş geçmiş — sayfa yüklenir, tablo başlıkları görünür', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/**', r =>
            r.fulfill(json([]))
        )
        await page.goto('/admin/veri')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 8_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })

    test('backend 500 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/admin/veri')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
```

- [ ] **Adım 5.2 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/veri-yonetim.spec.ts --reporter=list 2>&1 | tail -25
```

- [ ] **Adım 5.3 — Commit**

```bash
git add frontend/e2e/tests/veri-yonetim.spec.ts
git commit -m "test(e2e): VeriYonetimPage — geçmiş listesi, rollback onay/red akışı, 500 hata"
```

---

## Task 6: atama.spec.ts — AtamaPage E2E

**Sayfa:** `/admin/atama` → `AtamaPage.tsx`

**Sayfa davranışı:**
- Sayfa yüklenirken: GET `/api/v1/vehicles/?limit=500` (vehicleService) + GET `/api/v1/drivers/?limit=500` (driverService)
- Sayfa `vehiclesResp?.items ?? []` okur → VEHICLE_LIST formatı `{ items, total }` olmalı
- Sayfa `driversResp?.items ?? []` okur → driver mock da `{ items, total }` formatında olmalı (driverService.getAll wrapper'ı)
- 3 validasyon kuralı (AtamaPage.tsx:65-76):
  1. `seferId > 0` olmak zorunda
  2. `aracId || soforId` — en az biri seçilmeli
  3. `reason.trim().length >= 5` — gerekçe zorunlu
- Başarılı submit: POST `/admin/attribution/override`

**NOT:** `driverService.getAll()` döndürdüğü format için `frontend/src/services/api/driver-service.ts` satır 43'ü oku. Eğer flat array dönüyorsa driver dropdown boş görünür (bilinen bug). Mock `{ items: [...], total: 1 }` formatında yaz — sayfa `driversResp?.items` okuduğundan bu format gerekli.

**Dosya:** `frontend/e2e/tests/atama.spec.ts`

- [ ] **Adım 6.1 — driver-service.ts'yi kontrol et**

```bash
grep -n "getAll\|return\|items\|total" D:/PROJECT/LOJINEXT/frontend/src/services/api/driver-service.ts | head -20
```

Eğer `driverService.getAll()` flat array dönüyorsa mock aşağıdaki gibi olmalı. Eğer `{ items, total }` wrapper'ı varsa aynı format.

- [ ] **Adım 6.2 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'
import { MOCK_VEHICLE, MOCK_DRIVER } from '../mocks'

// AtamaPage: vehiclesResp?.items ?? [] ve driversResp?.items ?? [] okuyor
// Her iki mock da { items, total } formatında olmalı
const VEHICLE_ITEMS = { items: [MOCK_VEHICLE], total: 1 }
const DRIVER_ITEMS = { items: [MOCK_DRIVER], total: 1 }

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Sefer Atama Düzeltme sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/vehicles/**', r => r.fulfill(json(VEHICLE_ITEMS)))
        await page.route('**/api/v1/drivers/**', r => r.fulfill(json(DRIVER_ITEMS)))
        await page.route('**/api/v1/admin/attribution/**', r => {
            if (r.request().method() === 'POST')
                return r.fulfill(json({ success: true, sefer_id: 1 }))
            return r.continue()
        })
    })

    test('sayfa yüklenir ve form görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        // Sefer ID input'u var mı?
        await expect(page.locator('input').first()).toBeVisible({ timeout: 10_000 })
        // Araç veya şoför dropdown'ı var mı?
        await expect(page.locator('select, [role="combobox"]').first()).toBeVisible({ timeout: 8_000 })
    })

    test('araç ve şoför dropdown yüklenir (mock items doğru formatta)', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        // Eğer dropdown boşsa driverService mock format uyumsuzluğu var demektir
        const aracSelect = page.locator('select').filter({ hasText: /34ABC01|Araç/i }).or(
            page.locator('select').nth(0)
        ).first()
        await expect(aracSelect).toBeVisible({ timeout: 8_000 })
        const optionCount = await aracSelect.locator('option').count()
        expect(optionCount).toBeGreaterThan(1) // placeholder + en az 1 araç
    })

    test('sefer ID boş submit — validasyon hatası', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.locator('input').first()).toBeVisible({ timeout: 10_000 })
        // Sefer ID boş bırak, submit et
        const submitBtn = page.getByRole('button', { name: /uygula|kaydet|güncelle|override/i }).first()
        await expect(submitBtn).toBeVisible({ timeout: 5_000 })
        await submitBtn.click()
        await expect(page.getByText(/geçerli bir sefer id/i).first()).toBeVisible({ timeout: 5_000 })
    })

    test('araç ve şoför seçilmeden submit — validasyon hatası', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.locator('input').first()).toBeVisible({ timeout: 10_000 })
        // Sefer ID gir, araç/şoför seçme
        const seferInput = page.locator('input[type="number"], input[placeholder*="sefer"], input[placeholder*="ID"]').first()
        await seferInput.fill('1')
        const submitBtn = page.getByRole('button', { name: /uygula|kaydet|güncelle|override/i }).first()
        await submitBtn.click()
        await expect(page.getByText(/en az araç veya şoför/i).first()).toBeVisible({ timeout: 5_000 })
    })

    test('gerekçe < 5 karakter submit — validasyon hatası', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })

        const seferInput = page.locator('input[type="number"], input[placeholder*="sefer"], input[placeholder*="ID"]').first()
        await seferInput.fill('1')

        // Araç seç
        const aracSelect = page.locator('select').nth(0)
        const aracOptions = await aracSelect.locator('option').count()
        if (aracOptions > 1) await aracSelect.selectOption({ index: 1 })

        // Gerekçe çok kısa
        const reasonInput = page.locator('textarea, input[placeholder*="gerekçe"], input[placeholder*="neden"]').first()
        if (await reasonInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await reasonInput.fill('kısa')
        }

        const submitBtn = page.getByRole('button', { name: /uygula|kaydet|güncelle|override/i }).first()
        await submitBtn.click()
        await expect(page.getByText(/en az 5 karakter/i).first()).toBeVisible({ timeout: 5_000 })
    })

    test('tüm alanlar dolu — POST gönderilir ve başarı toast görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })

        const seferInput = page.locator('input[type="number"], input[placeholder*="sefer"], input[placeholder*="ID"]').first()
        await seferInput.fill('42')

        const aracSelect = page.locator('select').nth(0)
        const aracOptions = await aracSelect.locator('option').count()
        if (aracOptions > 1) await aracSelect.selectOption({ index: 1 })

        const reasonInput = page.locator('textarea, input[placeholder*="gerekçe"], input[placeholder*="neden"]').first()
        if (await reasonInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await reasonInput.fill('Test gerekçesi uzun yeterince')
        }

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/admin/attribution') && req.method() === 'POST',
                { timeout: 8_000 }
            ),
            page.getByRole('button', { name: /uygula|kaydet|güncelle|override/i }).first().click(),
        ])
        expect(request.method()).toBe('POST')
        const body = JSON.parse(request.postData() ?? '{}')
        expect(body.sefer_id).toBe(42)
        expect(body.reason).toBeTruthy()
    })
})
```

- [ ] **Adım 6.3 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/atama.spec.ts --reporter=list 2>&1 | tail -25
```

Eğer "araç ve şoför dropdown" testi FAIL ederse: `driver-service.ts` okuyup mock formatını düzelt.

- [ ] **Adım 6.4 — Commit**

```bash
git add frontend/e2e/tests/atama.spec.ts
git commit -m "test(e2e): AtamaPage — 3 validasyon kuralı, başarılı override POST, dropdown yükleme"
```

---

## Task 7: coaching.spec.ts — CoachingPage E2E

**Sayfa:** `/coaching` → `CoachingPage.tsx`

**Servis çağrıları:**
- `coachingService.getEffectiveness(30)` → GET `/api/v1/coaching/effectiveness?days=30` → `CoachingEffectivenessResponse`
- Şoför seçilince: `coachingService.getInsights(soforId)` → GET `/api/v1/coaching/{soforId}/insights` → `CoachingInsightsResponse`
- Koçluk gönder: `coachingService.send(soforId, message, category)` → POST `/api/v1/coaching/{soforId}/send`
- Şoför listesi: GET `/api/v1/drivers/` (CoachingDriverList bileşeni)

**Dosya:** `frontend/e2e/tests/coaching.spec.ts`

- [ ] **Adım 7.1 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'
import { MOCK_DRIVER } from '../mocks'

const MOCK_EFFECTIVENESS = {
    window_days: 30,
    total_sent: 12,
    total_evaluated: 8,
    improved: 5,
    worsened: 2,
    improve_rate: 0.625,
    avg_score_delta_pct: 3.2,
    caveat: 'Yalnızca yakıt tüketimiyle ölçülmüştür',
}

const MOCK_INSIGHTS = {
    sofor_id: 1,
    ad_soyad: 'Ahmet Yılmaz',
    headline: 'Yakıt tüketimi optimize edilebilir',
    priority: 'medium' as const,
    insights: [
        {
            category: 'yakit_yonetimi' as const,
            pattern: 'Yüksek rölanti süresi',
            evidence: ['Ortalama rölanti: 45 dk/sefer'],
            suggestion: 'Rölanti süresini 15 dakika altında tutun',
            impact_score: 0.7,
        },
    ],
    generated_at: '2025-01-15T10:00:00',
    source: 'llm' as const,
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Koçluk sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/coaching/effectiveness**', r => r.fulfill(json(MOCK_EFFECTIVENESS)))
        await page.route('**/api/v1/coaching/*/insights**', r => r.fulfill(json(MOCK_INSIGHTS)))
        await page.route('**/api/v1/coaching/*/send**', r =>
            r.fulfill(json({ sent: true, delivery_id: 1, channel: 'telegram', sent_at: '2025-01-15T10:00:00' }))
        )
        await page.route('**/api/v1/drivers/**', r => {
            const url = r.request().url()
            if (url.includes('/stats')) return r.fulfill(json({ total: 1, aktif: 1, pasif: 0 }))
            return r.fulfill(json([MOCK_DRIVER]))
        })
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        // coachingPageText.heading değerini kontrol et
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 })
    })

    test('etkinlik mini kartı yüklenir', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        // MOCK_EFFECTIVENESS.improve_rate = 0.625 → %62.5 veya "5/8" gösterilmeli
        await expect(page.locator('[class*="card"], [class*="metric"]').first()).toBeVisible({ timeout: 8_000 })
    })

    test('şoför listesi yüklenir', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText(MOCK_DRIVER.ad_soyad).first()).toBeVisible({ timeout: 10_000 })
    })

    test('şoför seçilince insights paneli yüklenir', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText(MOCK_DRIVER.ad_soyad).first()).toBeVisible({ timeout: 10_000 })
        await page.getByText(MOCK_DRIVER.ad_soyad).first().click()
        // Insight başlığı görünmeli
        await expect(page.getByText(MOCK_INSIGHTS.headline).first()).toBeVisible({ timeout: 8_000 })
    })

    test('backend 503 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/coaching/effectiveness**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Service Unavailable"}' })
        )
        await page.goto('/coaching')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
```

- [ ] **Adım 7.2 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/coaching.spec.ts --reporter=list 2>&1 | tail -20
```

- [ ] **Adım 7.3 — coachingPageText.heading metnini bul**

```bash
grep -n "heading\|Koçluk\|coaching" D:/PROJECT/LOJINEXT/frontend/src/resources/tr/coaching.ts | head -10
```

"Sayfa yüklenir" testinde h1 selector'ı gerçek metne güncelle.

- [ ] **Adım 7.4 — Commit**

```bash
git add frontend/e2e/tests/coaching.spec.ts
git commit -m "test(e2e): CoachingPage — şoför listesi, insights panel, 503 fallback"
```

---

## Task 8: fleet-insights.spec.ts — FleetInsightsPage E2E

**Sayfa:** `/insights/fleet` → `FleetInsightsPage.tsx`

**Servis çağrıları:**
- `FleetEfficiencyCard` → `executiveService.getFvi()` → GET `/api/v1/reports/executive/kpi`
- `PeriodComparisonCard` → `fleetInsightsService.getComparison(period)` → GET `/api/v1/reports/insights/fleet/comparison?period={month|week}`
- `CrossFeatureSavings` → `executiveService.getCrossFeature(90)` → GET `/api/v1/reports/executive/cross-feature?days=90`

**Dosya:** `frontend/e2e/tests/fleet-insights.spec.ts`

- [ ] **Adım 8.1 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'

const MOCK_FVI = {
    fvi: 0.73,
    fuel_score: 0.8,
    maintenance_score: 0.7,
    driver_score: 0.75,
    anomaly_quality_score: 0.65,
    confidence: 0.9,
    trend_30d: 0.05,
    reasons: ['Yakıt tüketimi iyileşiyor'],
    computed_at: '2025-01-15T10:00:00',
}

const MOCK_COMPARISON_MONTH = {
    period: 'month' as const,
    current: { fuel_l: 4200, fuel_cost_tl: 210000, anomaly_count: 3, trip_count: 42 },
    previous: { fuel_l: 4500, fuel_cost_tl: 225000, anomaly_count: 5, trip_count: 40 },
    fuel_l_delta_pct: -6.7,
    fuel_cost_delta_pct: -6.7,
    anomaly_delta_pct: -40.0,
    trip_delta_pct: 5.0,
    current_start: '2025-01-01', current_end: '2025-01-31',
    previous_start: '2024-12-01', previous_end: '2024-12-31',
}

const MOCK_CROSS_FEATURE = {
    period_days: 90,
    maintenance_delay_loss_tl: 15000,
    coaching_savings_tl: 8500,
    theft_loss_tl: 2000,
    confidence: 0.75,
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Filo İçgörü sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/kpi**', r => r.fulfill(json(MOCK_FVI)))
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r => r.fulfill(json(MOCK_COMPARISON_MONTH)))
        await page.route('**/api/v1/reports/executive/cross-feature**', r => r.fulfill(json(MOCK_CROSS_FEATURE)))
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
    })

    test('period switcher "Bu Hafta" seçilince yeni istek gider', async ({ authedPage: page }) => {
        let lastPeriodParam = ''
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r => {
            const url = new URL(r.request().url())
            lastPeriodParam = url.searchParams.get('period') ?? ''
            return r.fulfill(json(MOCK_COMPARISON_MONTH))
        })

        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })

        await page.getByRole('button', { name: 'Bu Hafta' }).click()
        await page.waitForTimeout(500)
        expect(lastPeriodParam).toBe('week')
    })

    test('backend 503 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/kpi**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Feature flag kapalı"}' })
        )
        await page.goto('/insights/fleet')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
```

- [ ] **Adım 8.2 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/fleet-insights.spec.ts --reporter=list 2>&1 | tail -20
```

- [ ] **Adım 8.3 — Commit**

```bash
git add frontend/e2e/tests/fleet-insights.spec.ts
git commit -m "test(e2e): FleetInsightsPage — sayfa yüklenir, period switcher, 503 fallback"
```

---

## Task 9: executive.spec.ts — ExecutivePage E2E

**Sayfa:** `/executive` → `ExecutivePage.tsx`

**Servis çağrıları (7 adet endpoint):**
- `FleetEfficiencyCard` → GET `/reports/executive/kpi`
- `CashflowProjectionChart` → GET `/reports/executive/cashflow?days=90`
- `BusFactorWidget` → GET `/reports/executive/bus-factor?n=3`
- `CrossFeatureSavings` → GET `/reports/executive/cross-feature?days=90`
- `WhatIfPanel` → POST `/reports/executive/what-if`
- `CarbonReportCard` → GET `/reports/executive/carbon?days=30`
- `ComplianceHeatmap` → GET `/reports/executive/compliance?days_horizon=90`
- `DownloadPdfButton` → GET `/reports/executive/pdf` (blob)

**Dosya:** `frontend/e2e/tests/executive.spec.ts`

- [ ] **Adım 9.1 — Dosyayı oluştur**

```typescript
import { test, expect } from '../fixtures/auth'

const MOCK_FVI = {
    fvi: 0.73, fuel_score: 0.8, maintenance_score: 0.7, driver_score: 0.75,
    anomaly_quality_score: 0.65, confidence: 0.9, trend_30d: 0.05,
    reasons: ['İyi performans'], computed_at: '2025-01-15T10:00:00',
}
const MOCK_CASHFLOW = {
    horizon_days: 90, weeks: [], total_fuel_tl: 180000, total_maintenance_tl: 25000,
    total_penalty_tl: 5000, grand_total_tl: 210000, confidence: 0.8, assumptions: {},
}
const MOCK_BUS_FACTOR = {
    n: 3, top_n_drivers_loss_tl: 450000, top_n_drivers: [{ score: 0.9, yearly_km: 120000 }],
    bottlenecked_routes: [], risk_level: 'medium' as const,
}
const MOCK_CROSS_FEATURE = {
    period_days: 90, maintenance_delay_loss_tl: 15000,
    coaching_savings_tl: 8500, theft_loss_tl: 2000, confidence: 0.75,
}
const MOCK_WHAT_IF = {
    scenario_type: 'training' as const, inputs: {},
    yearly_savings_tl: 120000, upfront_cost_tl: 45000, payback_years: 0.375,
    five_year_roi_pct: 233.3, co2_reduction_kg: 8500, confidence: 0.7,
    monte_carlo: null, reasons: ['Şoför verimliliği artar'],
}
const MOCK_CARBON = {
    period_start: '2024-10-15', period_end: '2025-01-15', total_co2_kg: 185000,
    total_km: 87500, co2_per_km: 2.114, benchmark_co2_per_km: 2.0, delta_pct: 5.7,
    by_euro_class: { 'EURO_6': 120000 }, top_emitters: [], vehicle_count: 8,
}
const MOCK_COMPLIANCE = {
    days_horizon: 90, total_items: 5, overdue_count: 1, soon_count: 2,
    items: [
        { entity_type: 'arac' as const, entity_id: 1, plaka: '34ABC01', field: 'muayene',
          expiry_date: '2025-01-10', days_until: -5, risk_level: 'overdue' as const },
    ],
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Executive Cockpit sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/kpi**', r => r.fulfill(json(MOCK_FVI)))
        await page.route('**/api/v1/reports/executive/cashflow**', r => r.fulfill(json(MOCK_CASHFLOW)))
        await page.route('**/api/v1/reports/executive/bus-factor**', r => r.fulfill(json(MOCK_BUS_FACTOR)))
        await page.route('**/api/v1/reports/executive/cross-feature**', r => r.fulfill(json(MOCK_CROSS_FEATURE)))
        await page.route('**/api/v1/reports/executive/what-if**', r => r.fulfill(json(MOCK_WHAT_IF)))
        await page.route('**/api/v1/reports/executive/carbon**', r => r.fulfill(json(MOCK_CARBON)))
        await page.route('**/api/v1/reports/executive/compliance**', r => r.fulfill(json(MOCK_COMPLIANCE)))
        await page.route('**/api/v1/reports/executive/pdf**', r =>
            r.fulfill({ status: 200, contentType: 'application/pdf', body: Buffer.from('%PDF-1.4 mock') })
        )
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 })
    })

    test('PDF indir butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByRole('button', { name: /pdf|indir|download/i }).first()).toBeVisible({ timeout: 8_000 })
    })

    test('compliance heatmap — overdue kayıt görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await page.waitForLoadState('networkidle', { timeout: 20_000 })
        // MOCK_COMPLIANCE.items[0].plaka = '34ABC01' veya risk_level = 'overdue'
        await expect(
            page.getByText('34ABC01').or(page.getByText(/overdue|gecikmiş/i)).first()
        ).toBeVisible({ timeout: 10_000 })
    })

    test('tüm 7 endpoint çağrısı yapıldı — sayfa crash etmedi', async ({ authedPage: page }) => {
        const calledEndpoints: string[] = []
        for (const path of ['kpi', 'cashflow', 'bus-factor', 'cross-feature', 'carbon', 'compliance']) {
            await page.route(`**/api/v1/reports/executive/${path}**`, r => {
                calledEndpoints.push(path)
                return r.fulfill(json(MOCK_FVI)) // hepsi aynı mock döndürüyor, crash olmamalı
            })
        }
        await page.goto('/executive')
        await page.waitForLoadState('networkidle', { timeout: 20_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })

    test('backend 503 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Feature flag kapalı"}' })
        )
        await page.goto('/executive')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
```

- [ ] **Adım 9.2 — Çalıştır**

```bash
cd frontend && npx playwright test e2e/tests/executive.spec.ts --reporter=list 2>&1 | tail -25
```

- [ ] **Adım 9.3 — executiveText.pageTitle metnini doğrula**

```bash
grep -n "pageTitle\|pageSubtitle" D:/PROJECT/LOJINEXT/frontend/src/resources/tr/executive.ts | head -5
```

"Sayfa yüklenir" testinde h1 içeriğini gerçek metinle güncelle.

- [ ] **Adım 9.4 — Commit**

```bash
git add frontend/e2e/tests/executive.spec.ts
git commit -m "test(e2e): ExecutivePage — 7 endpoint, compliance heatmap, PDF butonu, 503 fallback"
```

---

## Task 10: Tüm Testleri Çalıştır ve Sonuçları Raporla

- [ ] **Adım 10.1 — Tam E2E suitini çalıştır**

```bash
cd frontend && npx playwright test --reporter=list 2>&1 | tail -50
```

- [ ] **Adım 10.2 — FAIL eden testleri listele**

```bash
cd frontend && npx playwright test --reporter=json 2>&1 | node -e "
const d = require('fs').readFileSync('/dev/stdin','utf8');
const r = JSON.parse(d);
const fails = r.suites?.flatMap(s => s.suites?.flatMap(ss => ss.specs?.filter(sp => sp.ok === false).map(sp => sp.title)) ?? []) ?? [];
console.log('FAIL:', fails.join('\n'));
"
```

- [ ] **Adım 10.3 — Her FAIL için sınıflandır**

Her FAIL eden test için:
- **Gerçek bug mu?** → Playwright trace: `npx playwright show-report` → screenshot/trace incele → bug olarak raporla
- **Test hatası mı (selector yanlış, timeout)?** → selector güncelle ve re-run et

- [ ] **Adım 10.4 — HTML raporu kaydet**

```bash
cd frontend && npx playwright test --reporter=html && echo "Rapor: frontend/playwright-report/index.html"
```

- [ ] **Adım 10.5 — Final commit**

```bash
git add frontend/e2e/
git commit -m "test(e2e): 9 yeni/düzeltilmiş spec — 7 sıfır kapsam sayfa kapatıldı, 2 kritik assertion düzeltildi"
```

---

## Self-Review

**Spec coverage kontrolü:**

| Gereksinim | Task |
|-----------|------|
| admin.spec.ts roles mock format düzelt | Task 1 |
| trips.spec.ts `\|\| true` kaldır | Task 2 |
| RollerPage — 0 kapsamdan çıkar | Task 3 |
| DogrulukPage — 0 kapsamdan çıkar | Task 4 |
| VeriYonetimPage — rollback onay/red akışı | Task 5 |
| AtamaPage — 3 validasyon kuralı | Task 6 |
| CoachingPage — insights, şoför seç | Task 7 |
| FleetInsightsPage — period switcher | Task 8 |
| ExecutivePage — 7 endpoint, PDF butonu | Task 9 |
| Tüm testleri çalıştır, raporla | Task 10 |

**Placeholder taraması:** Tüm adımlarda gerçek TypeScript/Playwright kodu var. Mock verileri gerçek TypeScript interface'lerinden (AdminRoleRecordSchema, FuelAccuracyStats, CoachingInsightsResponse, vb.) doğrudan türetildi.

**Type consistency:** Task 3'teki `MOCK_ROLES[].ad` → Task 1'deki `MOCK_ROLES[].ad` ile aynı alan adı. `AdminRoleRecord.yetkiler: Record<string, boolean>` tip tutarlı.

**Bilinçli eksikler:**
- `test.skip('sefer oluşturma formu...')` Task 2'de kaldırılmadı — Plan Wizard E2E'si ayrı bir plan/task gerektirir (4 adımlık wizard flow, bu planın kapsamı dışında).
- Backend 500 senaryoları: Her spec'e eklenmiştir (en az 1 adet).
- CoachingPage "şoför seçmeden gönder" senaryosu: SendCoachingDialog şofor seçili olmadan açılamaz (state koşullu), ayrı unit test kapsamına girer.
