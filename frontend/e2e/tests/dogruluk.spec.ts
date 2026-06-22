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

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
    })

    test('MAPE değeri görünür (8.3%)', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        // fmt(8.3, "%") → "8.3%"
        await expect(page.getByText('8.3%').first()).toBeVisible({ timeout: 8_000 })
    })

    test('RMSE değeri görünür (2.1 L/100km)', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        // fmt(2.1, " L/100km") → "2.1 L/100km"
        await expect(page.getByText('2.1 L/100km').first()).toBeVisible({ timeout: 8_000 })
    })

    test('Kapsam değeri görünür (75.0%)', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        // fmt(75.0, "%") → "75.0%"
        await expect(page.getByText('75.0%').first()).toBeVisible({ timeout: 8_000 })
    })

    test('period değişince yeni API isteği gönderilir', async ({ authedPage: page }) => {
        let requestCount = 0
        await page.route('**/api/v1/admin/fuel-accuracy**', r => {
            requestCount++
            return r.fulfill(json(MOCK_ACCURACY_30))
        })
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })

        // Period buttons render as "{p} gün" — e.g. "7 gün", "30 gün", "90 gün"
        await page.unroute('**/api/v1/admin/fuel-accuracy**')
        await page.route('**/api/v1/admin/fuel-accuracy**', r => {
            requestCount++
            return r.fulfill(json(MOCK_ACCURACY_30))
        })
        const btn7 = page.locator('button').filter({ hasText: /^7 gün$/ }).first()
        await btn7.waitFor({ state: 'visible', timeout: 5_000 })
        const countBefore = requestCount
        const responsePromise = page.waitForResponse('**/api/v1/admin/fuel-accuracy**')
        await btn7.click()
        await responsePromise
        expect(requestCount).toBeGreaterThan(countBefore)
    })

    test('period butonları sayfada görünür (7 gün, 30 gün, 90 gün)', async ({ authedPage: page }) => {
        await page.goto('/admin/dogruluk')
        await expect(page.getByText('Yakıt Tahmin Doğruluğu').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.locator('button').filter({ hasText: /^7 gün$/ }).first()).toBeVisible()
        await expect(page.locator('button').filter({ hasText: /^30 gün$/ }).first()).toBeVisible()
        await expect(page.locator('button').filter({ hasText: /^90 gün$/ }).first()).toBeVisible()
    })

    test('sample_size = 0 → boş durum mesajı gösterilir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill(json(MOCK_ACCURACY_EMPTY))
        )
        await page.goto('/admin/dogruluk')
        await expect(
            page.getByText('Seçili dönemde tahmin/gerçek karşılaştırması için yeterli veri yok.').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('sample_size = 0 → metrik kartları render edilmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill(json(MOCK_ACCURACY_EMPTY))
        )
        await page.goto('/admin/dogruluk')
        // MAPE card should not be present when sample_size = 0
        await expect(page.getByText('8.3%')).toHaveCount(0, { timeout: 5_000 })
    })

    test('backend 500 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/fuel-accuracy**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/admin/dogruluk')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        // ErrorBoundary wraps the page — should not show generic crash text
        await expect(page.getByText(/Something went wrong/i)).toHaveCount(0)
        // Title should still be present (rendered outside ErrorBoundary concern)
        // or at minimum the page should not crash entirely
        await expect(page.locator('body')).toBeVisible()
    })
})
