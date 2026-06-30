import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_TRAILER = {
    id: 1,
    plaka: '34TRL001',
    marka: 'Schmitz',
    model: 'S.CS',
    yil: 2021,
    aktif: true,
    kapasite_ton: 24,
    tip: 'TENTELI',
}

function setupMocks(page: import('@playwright/test').Page) {
    // LIFO — spesifik route'lar SONRA kayıt edilmeli (Playwright son kaydı ilk kontrol eder)
    return Promise.all([
        // Catch-all (önce kayıt = LIFO'da en son kontrol)
        page.route('**/api/v1/vehicles**', r =>
            r.fulfill(json({ items: [{ id: 1, plaka: '34ABC01', marka: 'Mercedes', aktif: true }], total: 1 }))
        ),
        // Daha spesifik (sonra kayıt = LIFO'da ilk kontrol)
        page.route('**/api/v1/vehicles/inspection-alerts**', r =>
            r.fulfill(json({ expiring: [], overdue: [] }))
        ),
        // Trailers: dorseService.getAll → data.data döndürür → { data: [...] } formatı şart
        page.route('**/api/v1/trailers/**', r => {
            const url = r.request().url()
            const method = r.request().method()
            if (url.includes('/fleet-stats')) return r.fulfill(json({ total: 1, active: 1 }))
            if (url.includes('/export')) return r.fulfill({ status: 200, contentType: 'application/octet-stream', body: '' })
            if (url.includes('/template')) return r.fulfill({ status: 200, contentType: 'application/octet-stream', body: '' })
            if (method === 'GET') return r.fulfill(json({ data: [MOCK_TRAILER] }))
            return r.fulfill(json({ data: MOCK_TRAILER }))
        }),
    ])
}

test.describe('FleetPage — Dorseler sekmesi', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        // framer-motion animasyonlarını devre dışı bırak — initial opacity:0 kalıcı olabilir
        await page.emulateMedia({ reducedMotion: 'reduce' })
        await setupMocks(page)
        // Dashboard stats — FleetInsights bileşeni çağırıyor
        await page.route('**/api/v1/reports/dashboard**', r =>
            r.fulfill(json({ total_vehicles: 1, active_vehicles: 1, total_drivers: 1, active_drivers: 1, total_trips: 0, total_fuel_cost: 0 }))
        )
        await page.route('**/api/v1/reports/**', r => r.fulfill(json({})))
        await page.goto('/fleet?tab=trailers', { waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Dorse Yönetimi').first()).toBeVisible({ timeout: 15_000 })
    })

    test('dorse listesi yüklenir ve plaka görünür', async ({ authedPage: page }) => {
        await expect(page.getByText(MOCK_TRAILER.plaka)).toBeVisible({ timeout: 10_000 })
    })

    test('"Yeni Dorse Ekle" butonu görünür', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Yeni Dorse Ekle' })).toBeVisible()
    })

    test('"Yeni Dorse Ekle" butonu modal açar', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Yeni Dorse Ekle' }).click()
        await expect(page.getByText('Dorse Plakası').or(page.getByPlaceholder(/plaka/i))).toBeVisible({ timeout: 8_000 })
    })

    test('"Aktif Dorseler" filtre butonu görünür', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Aktif Dorseler' })).toBeVisible({ timeout: 8_000 })
    })

    test('Dorseler sekmesi Araçlar sekmesine geçiş yapıldığında kaybolur', async ({ authedPage: page }) => {
        const vehiclesTab = page.getByRole('button', { name: /araçlar/i }).first()
        await vehiclesTab.click()
        await expect(page.getByText('Dorse Yönetimi')).not.toBeVisible({ timeout: 8_000 })
    })

    test('arama kutusu render edilir', async ({ authedPage: page }) => {
        const searchInput = page.getByPlaceholder(/ara|search/i).first()
        await expect(searchInput).toBeVisible({ timeout: 5_000 })
    })

    test('marka bilgisi dorse listesinde görünür', async ({ authedPage: page }) => {
        // h3.truncate Playwright'da visibility için sıkı ölçüt var; body metin kontrolü kullan
        await expect(page.locator('body')).toContainText(MOCK_TRAILER.marka, { timeout: 8_000 })
    })

    test('liste boş olduğunda boş durum mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/trailers**')
        await page.route('**/api/v1/trailers**', r => r.fulfill(json([])))
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Dorse Yönetimi').first()).toBeVisible({ timeout: 10_000 })
        // Boş liste → hiç dorse satırı yok
        await expect(page.getByText(MOCK_TRAILER.plaka)).not.toBeVisible()
    })

    test('500 hata — sayfada hata mesajı ya da boş liste gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/trailers**')
        await page.route('**/api/v1/trailers**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Sunucu hatası"}' })
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        // Hata boundary veya boş durum — kritik çöküş olmamalı; .first() strict mode ihlalini önler
        await expect(page.getByText('Dorse Yönetimi').or(page.getByText(/hata|yüklenemedi/i)).first()).toBeVisible({ timeout: 10_000 })
    })

    test('Excel işlemleri ve Detaylı filtre butonları tıklanabilir', async ({ authedPage: page }) => {
        // Excel İşlemleri butonu
        const excelBtn = page.getByRole('button', { name: 'Excel İşlemleri' }).first()
        await expect(excelBtn).toBeVisible()
        await excelBtn.click()

        // Detaylı Filtre butonu
        const filterBtn = page.getByRole('button', { name: 'Detaylı Filtre' }).first()
        await expect(filterBtn).toBeVisible()
        await filterBtn.click()
    })
})
