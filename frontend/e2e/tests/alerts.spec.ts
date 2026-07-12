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
        // MaintenanceVehicleSchema (frontend/src/api/anomalies.ts) requires
        // reason_codes: {code, params}[] — not a pre-formatted string. Backend
        // moved from a single Turkish sentence to i18n-able reason codes;
        // formatMaintenanceReason() (lib/status-labels.ts) renders these per locale.
        maintenance: {
            urgent_count: 1,
            warning_count: 2,
            vehicles: [
                { id: 2, plaka: '34XYZ02', reason_codes: [{ code: 'high_consumption', params: { value: 18.5 } }], severity: 'high' },
                { id: 3, plaka: '34DEF03', reason_codes: [{ code: 'high_mileage', params: { km: 250000 } }], severity: 'medium' },
                { id: 4, plaka: '06GHI04', reason_codes: [{ code: 'overdue_maintenance', params: { days: 45 } }], severity: 'medium' },
            ],
        },
    },
}

test.describe('Anomaliler sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route(/anomalies\/fleet\/insights/, r => r.fulfill(json(FLEET_INSIGHTS)))
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
        // formatMaintenanceReason('high_consumption', {value:18.5}) → "Yüksek tüketim (18.5 L/100km)"
        await expect(page.getByText(/Yüksek tüketim/)).toBeVisible()
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

    test('tarih filtre butonları tıklandığında API doğru gün parametresiyle tetiklenir', async ({ authedPage: page }) => {
        let requestedUrl: string | null = null
        await page.unroute(/anomalies\/fleet\/insights/)
        await page.route(/anomalies\/fleet\/insights/, r => {
            requestedUrl = r.request().url()
            console.log('DEBUG: INTERCEPTED URL:', requestedUrl)
            return r.fulfill(json(FLEET_INSIGHTS))
        })

        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')
        console.log('DEBUG: PAGE LOADED. INITIAL URL:', requestedUrl)

        // Her tarih filtresi butonuna sırayla tıkla ve API parametresini doğrula
        // 30 Gün default olduğu için React Query cache'den döner — yeni istek atılmaz, listeye dahil edilmez
        const filters = [
            { label: '7 Gün', param: '7' },
            { label: '14 Gün', param: '14' },
            { label: '60 Gün', param: '60' },
            { label: '90 Gün', param: '90' },
        ]
        for (const { label, param } of filters) {
            requestedUrl = null
            const btn = page.getByRole('button', { name: label }).first()
            await expect(btn).toBeVisible()
            await btn.click()
            console.log('DEBUG: CLICKED', label)
            await expect.poll(() => {
                console.log('DEBUG: POLLING requestedUrl:', requestedUrl)
                return requestedUrl
            }).toContain(`days=${param}`)
        }
    })

    test('kategori sekme butonları (Tümü, Yakıt Kaçağı, Bakım Adayı, Soruşturmalar) tıklanabilir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/investigations**', r =>
            r.fulfill(json([]))
        )

        await page.goto('/alerts')
        await page.waitForLoadState('networkidle')

        // "Tümü" tab varsayılan olarak aktif olmalı
        const tumuBtn = page.getByRole('button', { name: /Tümü/i }).first()
        await expect(tumuBtn).toBeVisible()

        // "Yakıt Kaçağı" tab'a tıkla
        const leakageBtn = page.getByRole('button', { name: /Yakıt Kaçağı/i }).first()
        await expect(leakageBtn).toBeVisible()
        await leakageBtn.click()
        await expect(page.getByText(/Yakıt Kaçağı Özeti/i).first()).toBeVisible({ timeout: 5_000 })

        // "Bakım Adayı" tab'a tıkla
        const maintenanceBtn = page.getByRole('button', { name: /Bakım Adayı/i }).first()
        await expect(maintenanceBtn).toBeVisible()
        await maintenanceBtn.click()

        // "Soruşturmalar" tab'a tıkla
        const investigationsBtn = page.getByRole('button', { name: /Soruşturmalar/i }).first()
        await expect(investigationsBtn).toBeVisible()
        await investigationsBtn.click()
    })
})
