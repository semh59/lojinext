import { test, expect } from '../fixtures/auth'

const MOCK_FVI = {
    fvi: 81.2,
    fuel_score: 85,
    maintenance_score: 78,
    driver_score: 82,
    anomaly_quality_score: 74,
    confidence: 0.88,
    trend_30d: 1.5,
    reasons: ['İyi performans'],
    computed_at: '2025-01-15T10:00:00',
}

const MOCK_CASHFLOW = {
    horizon_days: 90,
    weeks: [{ week_start: '2025-01-01', fuel_tl: 42000, maintenance_tl: 8000, penalty_tl: 1000, total_tl: 51000 }],
    total_fuel_tl: 42000,
    total_maintenance_tl: 8000,
    total_penalty_tl: 1000,
    grand_total_tl: 51000,
    confidence: 0.75,
    assumptions: {},
}

const MOCK_BUS_FACTOR = {
    n: 3,
    top_n_drivers_loss_tl: 120000,
    top_n_drivers: [{ score: 0.95, yearly_km: 85000 }],
    bottlenecked_routes: [],
    risk_level: 'medium',
}

const MOCK_CROSS_FEATURE = {
    period_days: 90,
    maintenance_delay_loss_tl: 15000,
    coaching_savings_tl: 8500,
    theft_loss_tl: 3200,
    confidence: 0.72,
}

const MOCK_CARBON = {
    period_start: '2024-10-01',
    period_end: '2025-01-01',
    total_co2_kg: 42500,
    total_km: 285000,
    co2_per_km: 0.149,
    benchmark_co2_per_km: 0.155,
    delta_pct: -3.9,
    by_euro_class: { 'Euro 5': 40000, 'Euro 6': 2500 },
    top_emitters: [],
    vehicle_count: 8,
}

const MOCK_COMPLIANCE = {
    days_horizon: 90,
    total_items: 3,
    overdue_count: 1,
    soon_count: 2,
    items: [],
}

const MOCK_WHAT_IF = {
    scenario_type: 'training',
    inputs: {},
    yearly_savings_tl: 45000,
    upfront_cost_tl: 12000,
    payback_years: 0.27,
    five_year_roi_pct: 1775,
    co2_reduction_kg: 0,
    confidence: 0.7,
    monte_carlo: null,
    reasons: ['Yakıt tasarrufu'],
}

function json(body: unknown, status = 200) {
    return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('ExecutivePage — Strategic Cockpit', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/executive/**', r => {
            const url = r.request().url()
            if (url.includes('/kpi')) return r.fulfill(json(MOCK_FVI))
            if (url.includes('/cashflow')) return r.fulfill(json(MOCK_CASHFLOW))
            if (url.includes('/bus-factor')) return r.fulfill(json(MOCK_BUS_FACTOR))
            if (url.includes('/cross-feature')) return r.fulfill(json(MOCK_CROSS_FEATURE))
            if (url.includes('/carbon')) return r.fulfill(json(MOCK_CARBON))
            if (url.includes('/compliance')) return r.fulfill(json(MOCK_COMPLIANCE))
            if (url.includes('/pdf')) return r.fulfill({ status: 200, contentType: 'application/pdf', body: Buffer.from('PDF') })
            if (url.includes('/what-if') && r.request().method() === 'POST') return r.fulfill(json(MOCK_WHAT_IF))
            return r.continue()
        })
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
    })

    test('FVI kartı görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('Filo Verimliliği Endeksi').first()
        ).toBeVisible({ timeout: 8_000 })
        // fvi: 81.2 → toFixed(0) → "81"
        await expect(page.getByText('81').first()).toBeVisible()
    })

    test('Cashflow kartı görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('90 Gün Cashflow Projeksiyonu').first()
        ).toBeVisible({ timeout: 8_000 })
        // grand_total_tl: 51000 → toLocaleString("tr-TR") → "51.000", prefixed with ₺
        await expect(page.getByText('₺51.000').first()).toBeVisible()
    })

    test('Bus Factor widget görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText(/Bus Factor/).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('Cross-Feature kartı görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText(/Cross-Feature Etki/).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('PDF indir butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('CEO 1-pager PDF indir').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('WhatIf panel görünür ve senaryo çalıştırılabilir', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('What-If Simülatörü').first()
        ).toBeVisible({ timeout: 8_000 })

        // POST isteğini yakala — Must be registered before the submit click
        const whatIfRequestPromise = page.waitForRequest(
            r => r.url().includes('/what-if') && r.method() === 'POST'
        )

        // "Koçluk Programı ROI" butonuna tıkla
        const koçlukBtn = page.locator('button').filter({ hasText: 'Koçluk Programı ROI' }).first()
        await koçlukBtn.waitFor({ state: 'visible', timeout: 5_000 })
        await koçlukBtn.click()

        // "Senaryoyu Çalıştır" butonuna tıkla
        const runBtn = page.locator('button').filter({ hasText: 'Senaryoyu Çalıştır' }).first()
        await runBtn.waitFor({ state: 'visible', timeout: 5_000 })
        await runBtn.click()

        const whatIfRequest = await whatIfRequestPromise
        const body = JSON.parse(whatIfRequest.postData() ?? '{}')
        expect(body.scenario_type).toBe('training')
    })

    test('Filo Yenileme ROI ne-olurdu senaryosu çalıştırılabilir', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })

        const whatIfRequestPromise = page.waitForRequest(
            r => r.url().includes('/what-if') && r.method() === 'POST'
        )

        // "Filo Yenileme ROI" butonuna tıkla
        const btn = page.locator('button').filter({ hasText: 'Filo Yenileme ROI' }).first()
        await btn.waitFor({ state: 'visible', timeout: 5_000 })
        await btn.click()

        // "Senaryoyu Çalıştır" butonuna tıkla
        const runBtn = page.locator('button').filter({ hasText: 'Senaryoyu Çalıştır' }).first()
        await runBtn.click()

        const whatIfRequest = await whatIfRequestPromise
        const body = JSON.parse(whatIfRequest.postData() ?? '{}')
        expect(body.scenario_type).toBe('fleet_renewal')
    })

    test('Güzergah Portföy Optimizasyonu ne-olurdu senaryosu çalıştırılabilir', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })

        const whatIfRequestPromise = page.waitForRequest(
            r => r.url().includes('/what-if') && r.method() === 'POST'
        )

        // "Güzergah Portföy Optimizasyonu" butonuna tıkla
        const btn = page.locator('button').filter({ hasText: 'Güzergah Portföy Optimizasyonu' }).first()
        await btn.waitFor({ state: 'visible', timeout: 5_000 })
        await btn.click()

        // "Senaryoyu Çalıştır" butonuna tıkla
        const runBtn = page.locator('button').filter({ hasText: 'Senaryoyu Çalıştır' }).first()
        await runBtn.click()

        const whatIfRequest = await whatIfRequestPromise
        const body = JSON.parse(whatIfRequest.postData() ?? '{}')
        expect(body.scenario_type).toBe('route_portfolio')
    })

    test('Carbon kartı görünür', async ({ authedPage: page }) => {
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('Karbon Ayak İzi').first()
        ).toBeVisible({ timeout: 8_000 })
        // total_co2_kg: 42500 → toLocaleString("tr-TR") → "42.500"
        await expect(page.getByText('42.500').first()).toBeVisible()
    })

    test('backend 500 → sayfa çökmez', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/executive/**')
        await page.route('**/api/v1/reports/executive/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/executive')
        await expect(page.getByText('Strategic Cockpit').first()).toBeVisible({ timeout: 10_000 })
    })
})
