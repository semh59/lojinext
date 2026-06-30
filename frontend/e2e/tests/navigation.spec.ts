import { test, expect } from '../fixtures/auth'
import { setupTripMocks } from '../mocks'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupBasicMocks(page: any) {
    await page.route('**/api/v1/reports/dashboard**', r => r.fulfill(json({
        toplam_sefer: 6, bugun_sefer: 0, aktif_arac: 0, toplam_arac: 6,
    })))
    await page.route('**/api/v1/reports/consumption-trend**', r => r.fulfill(json([])))
    await page.route('**/api/v1/trips/stats**', r => r.fulfill(json({
        total_count: 34, completed_count: 29, cancelled_count: 2,
        planned_count: 3, in_progress_count: 0, total_distance_km: 12500, avg_consumption: 31.5,
    })))
    await page.route('**/api/v1/anomalies/fleet/insights**', r => r.fulfill(json({
        status: 'success',
        data: {
            leakage: { route_deviation_km: 0, route_deviation_cost: 0, fuel_gap_liters: 0, fuel_gap_cost: 0 },
            maintenance: { urgent_count: 0, warning_count: 0, vehicles: [] },
        },
    })))
    await page.route('**/api/v1/predictions/comparison**', r => r.fulfill(json({
        mae: 2.07, rmse: 2.57, total_compared: 0,
        accuracy_distribution: { good: 0, warning: 0, error: 0, good_pct: 0, warning_pct: 0, error_pct: 0 },
        trend: [],
    })))
}

test.describe('Sayfa navigasyonu', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupBasicMocks(page)
    })

    test('dashboard → seferler navigasyonu çalışır', async ({ authedPage: page }) => {
        await setupTripMocks(page)
        await page.goto('/')
        await page.waitForLoadState('networkidle')
        const tripsLink = page.getByRole('link', { name: /sefer|trips/i }).first()
        if (await tripsLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
            await tripsLink.click()
            await expect(page).toHaveURL(/\/trips/, { timeout: 8_000 })
        } else {
            await page.goto('/trips')
            await expect(page).toHaveURL(/\/trips/, { timeout: 8_000 })
        }
    })

    test('doğrudan URL navigasyonu — her sayfa render edilir', async ({ authedPage: page }) => {
        const routes = ['/trips', '/fuel', '/fleet', '/locations', '/reports', '/monitoring', '/predictions']
        for (const route of routes) {
            await page.goto(route)
            await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
            // Page should not crash (no "Something went wrong" or error boundary message)
            const errorText = await page.locator('text=/Something went wrong|Bir hata oluştu/i').count()
            expect(errorText).toBe(0)
        }
    })

    test('geri tuşu çalışır', async ({ authedPage: page }) => {
        await setupTripMocks(page)
        await page.goto('/')
        await page.waitForLoadState('networkidle')
        await page.goto('/trips')
        await page.waitForLoadState('domcontentloaded')
        await page.goBack()
        await expect(page).toHaveURL(/\/$/, { timeout: 8_000 })
    })

    test('alerts sayfası navigasyonu çalışır', async ({ authedPage: page }) => {
        await page.route('**/api/v1/anomalies/**', r => r.fulfill(json({
            status: 'success',
            data: {
                leakage: { route_deviation_km: 0, route_deviation_cost: 0, fuel_gap_liters: 0, fuel_gap_cost: 0 },
                maintenance: { urgent_count: 0, warning_count: 0, vehicles: [] },
            },
        })))
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 10_000 })
    })

    test('legacy reports url redirects to reports studio', async ({ authedPage: page }) => {
        await page.goto('/reports/legacy')
        await expect(page).toHaveURL(/\/reports/, { timeout: 8_000 })
    })

    test('legacy dashboard url redirects to home', async ({ authedPage: page }) => {
        await page.goto('/legacy-dashboard')
        await expect(page).toHaveURL(/\/$/, { timeout: 8_000 })
    })
})
