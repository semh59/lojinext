import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const DASHBOARD_STATS = {
    toplam_sefer: 6, bugun_sefer: 0, aktif_arac: 0, toplam_arac: 6,
    toplam_km: 12500, toplam_yakit: 204109,
}

const TRIP_STATS = {
    total_count: 34, completed_count: 29, cancelled_count: 2,
    planned_count: 3, in_progress_count: 0,
    total_distance_km: 12500, avg_consumption: 31.5,
}

const CONSUMPTION_TREND = [
    { month: '2026-03', consumption: 1360.0 },
    { month: '2026-04', consumption: 3547.0 },
    { month: '2026-05', consumption: 394.5 },
]

// anomaly-service.ts reads response.data.data → must wrap in {status, data}
const FLEET_INSIGHTS_RAW = {
    leakage: {
        route_deviation_km: 210,
        route_deviation_cost: 12600,
        fuel_gap_liters: 20921.6,
        fuel_gap_cost: 805475.2,
    },
    maintenance: {
        urgent_count: 1,
        warning_count: 0,
        vehicles: [{ id: 2, plaka: '34XYZ02', reason: 'Yüksek tüketim', severity: 'high' }],
    },
}
const FLEET_INSIGHTS = { status: 'success', data: FLEET_INSIGHTS_RAW }

const PREDICTION_COMPARISON = {
    mae: 2.07, rmse: 2.57, total_compared: 29,
    accuracy_distribution: { good: 14, warning: 8, error: 7, good_pct: 50.0, warning_pct: 27.6, error_pct: 24.1 },
    trend: [],
}

async function setupDashboardMocks(page: any) {
    // LIFO: override fixture's super_admin user → operator so HomePage renders DashboardPage
    await page.route('**/auth/me', r => r.fulfill(json({
        id: 1,
        kullanici_adi: 'testuser',
        username: 'testuser',
        ad_soyad: 'Test User',
        full_name: 'Test User',
        rol: { ad: 'operator' },
        role: 'operator',
        aktif: true,
        is_active: true,
    })))
    await page.route('**/api/v1/reports/dashboard**', r => r.fulfill(json(DASHBOARD_STATS)))
    await page.route('**/api/v1/reports/consumption-trend**', r => r.fulfill(json(CONSUMPTION_TREND)))
    await page.route('**/api/v1/trips/stats**', r => r.fulfill(json(TRIP_STATS)))
    await page.route('**/api/v1/anomalies/fleet/insights**', r => r.fulfill(json(FLEET_INSIGHTS)))
    await page.route('**/api/v1/predictions/comparison**', r => r.fulfill(json(PREDICTION_COMPARISON)))
}

test.describe('Dashboard', () => {
    test('KPI — Toplam Sefer gerçek trips/stats değerini gösterir (34)', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        // "Toplam Sefer" KPI kartı 34 göstermeli (bugun_sefer:0 değil)
        await expect(page.getByText('Toplam Sefer')).toBeVisible()
        await expect(page.getByText('34', { exact: true }).first()).toBeVisible()
    })

    test('KPI — ML Doğruluk yüzdesi görünür', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('ML Doğruluk')).toBeVisible()
        await expect(page.getByText('50%')).toBeVisible()
    })

    test('Tüketim grafiği — birim L gösterir, L/100km değil', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Tüketim Trendi')).toBeVisible()
        // Yanlış birim L/100km içermemeli
        await expect(page.getByText('Aylık ortalama L/100km')).not.toBeVisible()
        // Doğru başlık
        await expect(page.getByText('Aylık toplam yakıt tüketimi')).toBeVisible()
    })

    test('Anomali widget — leakage > 0 olunca uyarı gösterir', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Filo Uyarıları')).toBeVisible()
        await expect(page.getByText('Yakıt Kaçağı')).toBeVisible()
        // 20.921 L rakamı görünmeli
        await expect(page.locator('text=/20.9|20921/')).toBeVisible()
    })

    test('Anomali widget — bakım adayı aracı listede görünür', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('34XYZ02')).toBeVisible()
        await expect(page.getByText('Acil').first()).toBeVisible()
    })

    test('Anomali widget — leakage 0 olunca "tespit edilmedi" mesajı', async ({ authedPage: page }) => {
        await page.route('**/auth/me', r => r.fulfill(json({
            id: 1, kullanici_adi: 'testuser', username: 'testuser',
            ad_soyad: 'Test User', full_name: 'Test User',
            rol: { ad: 'operator' }, role: 'operator', aktif: true, is_active: true,
        })))
        await page.route('**/api/v1/reports/dashboard**', r => r.fulfill(json(DASHBOARD_STATS)))
        await page.route('**/api/v1/reports/consumption-trend**', r => r.fulfill(json([])))
        await page.route('**/api/v1/trips/stats**', r => r.fulfill(json(TRIP_STATS)))
        await page.route('**/api/v1/predictions/comparison**', r => r.fulfill(json(PREDICTION_COMPARISON)))
        await page.route('**/api/v1/anomalies/fleet/insights**', r => r.fulfill(json({
            status: 'success',
            data: {
                leakage: { route_deviation_km: 0, route_deviation_cost: 0, fuel_gap_liters: 0, fuel_gap_cost: 0 },
                maintenance: { urgent_count: 0, warning_count: 0, vehicles: [] },
            },
        })))

        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Anormal tüketim tespit edilmedi')).toBeVisible()
        await expect(page.getByText('Bakım gerektiren araç yok')).toBeVisible()
    })

    test('Zil butonu tıklanınca bildirim paneli açılır', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        // Panel başlangıçta kapalı
        await expect(page.getByText('Henüz bildirim yok')).not.toBeVisible()

        // Zil butonuna tık
        await page.getByRole('button', { name: 'Bildirimler' }).click()

        // Panel açıldı — 'Tümünü okundu işaretle' yalnızca panelde bulunur
        await expect(page.getByText('Tümünü okundu işaretle')).toBeVisible()
        await expect(page.getByText('Henüz bildirim yok')).toBeVisible()
    })

    test('Zil paneli dışına tıklayınca kapanır', async ({ authedPage: page }) => {
        await setupDashboardMocks(page)
        await page.goto('/legacy-dashboard')
        await page.waitForLoadState('networkidle')

        await page.getByRole('button', { name: 'Bildirimler' }).click()
        await expect(page.getByText('Henüz bildirim yok')).toBeVisible()

        // Panel dışına tık
        await page.mouse.click(100, 100)
        await expect(page.getByText('Henüz bildirim yok')).not.toBeVisible()
    })
})
