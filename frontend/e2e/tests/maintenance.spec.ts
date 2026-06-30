import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_ALERT = {
    id: 1,
    arac_id: 3,
    tip: 'PERIYODIK',
    aciklama: 'Yağ değişimi',
    olusturma_tarihi: '2026-06-01T10:00:00',
    durum: 'yaklasiyor',
    bakim_tipi: 'PERIYODIK',
    bakim_tarihi: '2026-07-10T00:00:00',
    km_bilgisi: 145000,
}

const MOCK_PREDICTION = {
    arac_id: 3,
    plaka: '34ABC03',
    predicted_date: '2026-08-15',
    risk_level: 'soon',
    predictable: true,
    days_until: 55,
    last_maintenance_date: '2026-02-10',
    km_since_last: 12000,
}

async function setupMocks(page: import('@playwright/test').Page) {
    // LIFO: catch-all ÖNCE (en düşük öncelik), spesifik SONRA (en yüksek öncelik)
    await page.route('**/api/v1/vehicles**', r =>
        r.fulfill(json({ data: [{ id: 3, plaka: '34ABC03', marka: 'Mercedes', aktif: true }], meta: { total: 1, skip: 0, limit: 20 }, errors: null }))
    )
    await page.route('**/api/v1/admin/maintenance/**', r => r.fulfill(json({})))
    // Specific routes LAST = first match in LIFO
    await page.route('**/api/v1/admin/maintenance/alerts**', r => r.fulfill(json([MOCK_ALERT])))
    await page.route('**/api/v1/admin/maintenance/predictions**', r => r.fulfill(json([MOCK_PREDICTION])))
}

test.describe('AdminMaintenancePage — Bakım ve Onarım', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupMocks(page)
        await page.goto('/maintenance', { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'Bakım ve Onarım Merkezi' })).toBeVisible({ timeout: 15_000 })
    })

    test('sayfa başlığı ve açıklaması görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Araçların yaklaşan ve gecikmiş bakım görevlerini yönetin.')).toBeVisible()
    })

    test('tab butonları render edilir — Geçmiş, Liste, Takvim', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Geçmiş' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Liste' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Takvim' })).toBeVisible()
    })

    test('"Yeni Bakım / Arıza" butonu görünür', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Yeni Bakım / Arıza' })).toBeVisible()
    })

    test('varsayılan Geçmiş sekmesinde bakım uyarısı görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Acil ve Yaklaşan Bakımlar')).toBeVisible()
        await expect(page.getByText('Araç #3')).toBeVisible()
    })

    test('"Tamamlandı" butonu tablo satırında görünür', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Tamamlandı' }).first()).toBeVisible()
    })

    test('"Tamamlandı" tıklanınca PATCH isteği gönderilir', async ({ authedPage: page }) => {
        const [req] = await Promise.all([
            page.waitForRequest(
                r => r.url().includes('/admin/maintenance/') && r.method() === 'PATCH',
                { timeout: 10_000 }
            ),
            page.getByRole('button', { name: 'Tamamlandı' }).first().click(),
        ])
        expect(req.url()).toContain('/admin/maintenance/')
    })

    test('"Yeni Bakım / Arıza" butonu modal açar', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Yeni Bakım / Arıza' }).click()
        await expect(page.getByText('Yeni Bakım / Arıza Girişi')).toBeVisible({ timeout: 8_000 })
    })

    test('modal — araç seçilmeden kaydet tıklanınca validasyon hatası', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Yeni Bakım / Arıza' }).click()
        await expect(page.getByText('Yeni Bakım / Arıza Girişi')).toBeVisible({ timeout: 8_000 })
        await page.getByRole('button', { name: 'Kaydet' }).click()
        // Option "Araç seçin…" (üç nokta) vs error <p>"Araç seçin" → exact match option'u eler
        await expect(page.getByText('Araç seçin', { exact: true })).toBeVisible({ timeout: 5_000 })
    })

    test('modal — araç seçilip km boş bırakılınca hata mesajı', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Yeni Bakım / Arıza' }).click()
        await expect(page.getByText('Yeni Bakım / Arıza Girişi')).toBeVisible({ timeout: 8_000 })
        // Araç seçin select'inde ilk gerçek araç seçimi
        await page.locator('select').first().selectOption({ index: 1 })
        // KM boş — kaydet
        await page.getByRole('button', { name: 'Kaydet' }).click()
        await expect(page.getByText(/KM bilgisi zorunlu/i)).toBeVisible({ timeout: 5_000 })
    })

    test('Liste sekmesine geçiş — tahmin tablosu yüklenir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Liste' }).click()
        await expect(page.getByText('34ABC03')).toBeVisible({ timeout: 10_000 })
    })

    test('boş durum — uyarı yok mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/admin/maintenance/alerts**')
        await page.route('**/api/v1/admin/maintenance/alerts**', r => r.fulfill(json([])))
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Acil bakım uyarısı bulunmamaktadır')).toBeVisible({ timeout: 10_000 })
    })
})
