import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

// anomaly-service.ts reads response.data.data → wrap in {status, data}
const FLEET_INSIGHTS = {
    status: 'success',
    data: {
        leakage: {
            route_deviation_km: 210,
            route_deviation_cost: 12600,
            fuel_gap_liters: 20921.6,
            fuel_gap_cost: 805475.2,
        },
        maintenance: {
            urgent_count: 1,
            warning_count: 2,
            vehicles: [
                { id: 2, plaka: '34XYZ02', reason: 'Yüksek yakıt tüketimi', severity: 'high' },
                { id: 3, plaka: '34DEF03', reason: 'Km bazlı bakım', severity: 'medium' },
                { id: 4, plaka: '06GHI04', reason: 'Periyodik bakım', severity: 'medium' },
            ],
        },
    },
}

test.describe('Anomaliler sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/anomalies/fleet/insights**', r => r.fulfill(json(FLEET_INSIGHTS)))
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')
        await expect(page.locator('h1')).toContainText('Anomali')
    })

    test('KPI — Yakıt Açığı doğru litre gösterir', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Yakıt Açığı').first()).toBeVisible()
        // Math.floor(20921.6) = 20921
        await expect(page.locator('text=/20921/').first()).toBeVisible()
    })

    test('KPI — Bakım Adayı sayısı doğru (urgent + warning = 3)', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Bakım Adayı').first()).toBeVisible()
        // urgent_count:1 + warning_count:2 = 3
        await expect(page.getByText('3', { exact: true }).first()).toBeVisible()
    })

    test('KPI — Güzergah Sapması km gösterir', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Güzergah Sapması').first()).toBeVisible()
        await expect(page.locator('text=/210/').first()).toBeVisible()
    })

    test('Bakım tablosunda araçlar listelenir', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('34XYZ02')).toBeVisible()
        await expect(page.getByText('34DEF03')).toBeVisible()
        await expect(page.getByText('Yüksek yakıt tüketimi')).toBeVisible()
    })

    test('Acil ve Uyarı badge\'leri doğru', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('Acil').first()).toBeVisible()
        await expect(page.getByText('Uyarı').first()).toBeVisible()
    })

    test('Filtre — Yakıt Kaçağı sekmesi sadece leakage gösterir', async ({ authedPage: page }) => {
        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        const fuelTab = page.getByRole('button', { name: /Yakıt Kaçağı/i }).first()
        if (await fuelTab.count() > 0) {
            await fuelTab.click()
            // Leakage özeti başlığı görünmeli
            await expect(page.getByText(/Yakıt Kaçağı Özeti|kaçak|Sapma/i).first()).toBeVisible()
        }
    })

    test('Veri yok durumu — sıfır leakage "tespit edilmedi" + bakım sekmesi boş', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/anomalies/fleet/insights**')
        await page.route('**/api/v1/anomalies/fleet/insights**', r => r.fulfill(json({
            status: 'success',
            data: {
                leakage: { route_deviation_km: 0, route_deviation_cost: 0, fuel_gap_liters: 0, fuel_gap_cost: 0 },
                maintenance: { urgent_count: 0, warning_count: 0, vehicles: [] },
            },
        })))

        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        // 'all' tab default: LeakageSummary sıfır → "tespit edilmedi"
        await expect(page.getByText(/tespit edilmedi/i).first()).toBeVisible()

        // 'maintenance' tab'a geç → MaintenanceTable boş state mesajı
        // (RV2.9 sonrası AlertsPage tab'lı; bakım ayrı sekmede)
        const maintenanceTab = page.getByRole('button', { name: /bakım/i }).first()
        if (await maintenanceTab.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await maintenanceTab.click()
            // AlertsPage.tsx boş durumda "Bakım gerektiren araç bulunmuyor"
            // gösteriyor (MaintenanceTable çağrılmıyor — short-circuit).
            await expect(page.getByText(/bakım gerektiren araç bulunmuyor/i)).toBeVisible({ timeout: 5_000 })
        }
    })
})
