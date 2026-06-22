import { test, expect } from '../fixtures/auth'

const MOCK_FVI = {
    fvi: 78.5,
    fuel_score: 82,
    maintenance_score: 75,
    driver_score: 79,
    anomaly_quality_score: 71,
    confidence: 0.85,
    trend_30d: 2.3,
    reasons: ['Yakıt verimliliği iyi'],
    computed_at: '2025-01-15T10:00:00',
}

const MOCK_COMPARISON = {
    period: 'month',
    current: { fuel_l: 5200, fuel_cost_tl: 182000, anomaly_count: 3, trip_count: 42 },
    previous: { fuel_l: 5600, fuel_cost_tl: 196000, anomaly_count: 5, trip_count: 40 },
    fuel_l_delta_pct: -7.1,
    fuel_cost_delta_pct: -7.1,
    anomaly_delta_pct: -40.0,
    trip_delta_pct: 5.0,
    current_start: '2025-01-01',
    current_end: '2025-01-31',
    previous_start: '2024-12-01',
    previous_end: '2024-12-31',
}

const MOCK_CROSS_FEATURE = {
    period_days: 90,
    maintenance_delay_loss_tl: 15000,
    coaching_savings_tl: 8500,
    theft_loss_tl: 3200,
    confidence: 0.72,
}

function json(body: unknown, status = 200) {
    return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Filo İçgörü sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/kpi**', r =>
            r.fulfill(json(MOCK_FVI))
        )
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r =>
            r.fulfill(json(MOCK_COMPARISON))
        )
        await page.route('**/api/v1/reports/executive/cross-feature**', r =>
            r.fulfill(json(MOCK_CROSS_FEATURE))
        )
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
    })

    test('FVI kartı yüklenir', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('Filo Verimliliği Endeksi').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('period karşılaştırma kartı yüklenir — varsayılan Bu Ay vs Geçen', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        // default period=month → heading "BU AY VS GEÇEN" (uppercase via CSS, text-content is mixed case)
        await expect(
            page.getByText(/Bu Ay vs Geçen/).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('Yakıt satırı görünür', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        // MetricRow label rendered as uppercase via CSS but DOM text is "Yakıt"
        await expect(
            page.getByText('Yakıt', { exact: true }).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('period "Bu Hafta" seçilince yeni istek gönderilir', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        // Wait for initial comparison card to load
        await expect(page.getByText(/Bu Ay vs Geçen/).first()).toBeVisible({ timeout: 8_000 })

        // Set up mock for week request
        await page.unroute('**/api/v1/reports/insights/fleet/comparison**')
        const weekComparison = { ...MOCK_COMPARISON, period: 'week' }
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r =>
            r.fulfill(json(weekComparison))
        )

        const weekResponsePromise = page.waitForResponse(
            r => r.url().includes('/comparison') && r.url().includes('period=week')
        )

        const buHaftaBtn = page.locator('button').filter({ hasText: /^Bu Hafta$/ }).first()
        await buHaftaBtn.waitFor({ state: 'visible', timeout: 5_000 })
        await buHaftaBtn.click()

        await weekResponsePromise

        await expect(
            page.getByText(/Bu Hafta vs Geçen/).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('period "Bu Ay" seçilince başlık değişir', async ({ authedPage: page }) => {
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText(/Bu Ay vs Geçen/).first()).toBeVisible({ timeout: 8_000 })

        // Switch to Bu Hafta first
        await page.unroute('**/api/v1/reports/insights/fleet/comparison**')
        const weekComparison = { ...MOCK_COMPARISON, period: 'week' }
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r =>
            r.fulfill(json(weekComparison))
        )
        const buHaftaBtn = page.locator('button').filter({ hasText: /^Bu Hafta$/ }).first()
        await buHaftaBtn.waitFor({ state: 'visible', timeout: 5_000 })
        const weekRespPromise = page.waitForResponse(
            r => r.url().includes('/comparison') && r.url().includes('period=week')
        )
        await buHaftaBtn.click()
        await weekRespPromise
        await expect(page.getByText(/Bu Hafta vs Geçen/).first()).toBeVisible({ timeout: 8_000 })

        // Now switch back to Bu Ay — React Query may serve from cache,
        // so don't wait for a network response; the heading update is driven
        // purely by the period prop changing in component state.
        const buAyBtn = page.locator('button').filter({ hasText: /^Bu Ay$/ }).first()
        await buAyBtn.click()

        await expect(
            page.getByText(/Bu Ay vs Geçen/).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('karşılaştırma API 503 → hata mesajı', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/insights/fleet/comparison**')
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"service unavailable"}' })
        )
        await page.goto('/insights/fleet')
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('Karşılaştırma yüklenemedi').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('backend 500 → sayfa çökmez', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/executive/kpi**')
        await page.unroute('**/api/v1/reports/insights/fleet/comparison**')
        await page.unroute('**/api/v1/reports/executive/cross-feature**')
        await page.route('**/api/v1/reports/executive/kpi**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.route('**/api/v1/reports/insights/fleet/comparison**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.route('**/api/v1/reports/executive/cross-feature**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/insights/fleet')
        // Heading should still render regardless of API errors
        await expect(page.getByText('Filo İçgörü').first()).toBeVisible({ timeout: 10_000 })
    })
})
