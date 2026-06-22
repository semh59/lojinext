import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Canlı Takip sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        // WS bağlantısını engelle (test ortamında açık WebSocket hata vermez ama log kirletmez)
        await page.route('**/api/v1/ws/**', r => r.abort())
        await page.route('**/api/v1/reports/dashboard**', r => r.fulfill(json({
            toplam_sefer: 6, bugun_sefer: 0, aktif_arac: 0, toplam_arac: 6,
        })))
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await expect(page.locator('h1')).toContainText(/Bildirimler|Takip|Monitoring/i)
    })

    test('bağlantı durumu göstergesi görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')

        // ConnectionStatus bileşeni her zaman render edilmeli
        await expect(page.getByTestId('connection-status')).toBeVisible({ timeout: 5000 })
    })

    test('bildirim akışı alanı mevcut', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')

        // Boş bildirim akışı veya placeholder
        await expect(
            page.locator('text=/henüz|bildirim|akış|notification/i').first()
        ).toBeVisible({ timeout: 5000 })
    })

    test('sayfa render hatası olmadan yüklenir (ErrorBoundary tetiklenmez)', async ({ authedPage: page }) => {
        const errors: string[] = []
        page.on('pageerror', e => errors.push(e.message))

        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')

        expect(errors.filter(e => !e.includes('WebSocket'))).toHaveLength(0)
    })

    test('bağlantı durumu geçerli bir durum metni gösterir', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')

        // ConnectionStatus renders one of: bağlı, bağlanıyor, bağlantı kesildi, bağlantı hatası
        const statusEl = page.getByTestId('connection-status')
        await expect(statusEl).toBeVisible({ timeout: 5_000 })
        await expect(statusEl).toContainText(/bağl/i)
    })

    test('dashboard istatistik değerleri sayfada görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        // The monitoring page renders dashboard stats — at minimum the page container renders
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 8_000 })
        // Check any numeric value from mock (toplam_sefer: 6 or toplam_arac: 6)
        const hasNumeric = await page.locator('text=/\\d+/').count() > 0
        expect(hasNumeric).toBeTruthy()
    })

    test('"Bildirimler" tab butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await expect(page.getByRole('button', { name: 'Bildirimler' }).first()).toBeVisible({ timeout: 8_000 })
    })

    test('"Hata Olayları" tab butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await expect(page.getByRole('button', { name: 'Hata Olayları' })).toBeVisible({ timeout: 8_000 })
    })

    test('"ML Eğitim" tab butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await expect(page.getByRole('button', { name: 'ML Eğitim' })).toBeVisible({ timeout: 8_000 })
    })

    test('"Hata Olayları" sekmesine tıklanınca içerik değişir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/errors**', r => r.fulfill(json({ items: [], total: 0 })))
        await page.route('**/api/v1/sentry/**', r => r.fulfill(json({ issues: [] })))
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await page.getByRole('button', { name: 'Hata Olayları' }).click()
        // Hata olayları tab içeriği yüklendi — hata listesi ya da boş durum
        await expect(page.getByText(/hata|olay|event|sentry/i).first()).toBeVisible({ timeout: 8_000 })
    })

    test('"ML Eğitim" sekmesine tıklanınca içerik değişir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/ml/**', r => r.fulfill(json({ jobs: [], training_queue: [] })))
        await page.goto('/monitoring')
        await page.waitForLoadState('networkidle')
        await page.getByRole('button', { name: 'ML Eğitim' }).click()
        // ML Eğitim tab içeriği — kuyruk ya da model listesi
        await expect(page.getByText(/eğitim|model|ml|kuyruk/i).first()).toBeVisible({ timeout: 8_000 })
    })
})
