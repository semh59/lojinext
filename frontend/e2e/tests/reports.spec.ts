import { test, expect } from '../fixtures/auth'
import { setupReportsMocks } from '../mocks'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_TEMPLATES = [
    {
        id: 'fleet_weekly',
        title: 'Haftalık Filo Raporu',
        description: 'Araç bazlı haftalık performans.',
        category: 'fleet',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/fleet',
        supports_period: true,
        supports_vehicle: true,
    },
    {
        id: 'fuel_cost_analysis',
        title: 'Yakıt Maliyet Analizi',
        description: 'Yakıt gider kırılımı.',
        category: 'fuel',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/fuel',
        supports_period: true,
        supports_vehicle: false,
    },
    {
        id: 'vehicle_comparison',
        title: 'Araç Karşılaştırma',
        description: 'Araç bazlı verimlilik karşılaştırması.',
        category: 'fleet',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/vehicle',
        supports_period: true,
        supports_vehicle: true,
    },
]

test.describe('Raporlar sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupReportsMocks(page)
        await page.route('**/api/v1/reports/studio/templates**', r =>
            r.fulfill(json({ templates: MOCK_TEMPLATES, count: MOCK_TEMPLATES.length }))
        )
    })

    test('raporlar sayfası yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 15_000 })
    })

    test('rapor kartları görünür', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 10_000 })
        await expect(page.getByRole('button', { name: /Haftalık Filo/i })).toBeVisible({ timeout: 8_000 })
        await expect(page.getByRole('button', { name: /Yakıt Maliyet/i })).toBeVisible()
    })

    test('rapor kartına tıklayınca config paneli açılır', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /Haftalık Filo/i }).click()
        await expect(page.getByRole('button', { name: /İndir/i })).toBeVisible({ timeout: 8_000 })
    })

    test('maliyet analizi şablonu seçilince periyot seçimi görünür', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /Yakıt Maliyet/i }).click()
        await expect(page.getByText('Periyot')).toBeVisible({ timeout: 5_000 })
        await expect(page.getByRole('button', { name: /İndir/i })).toBeVisible()
    })

    test('ROI — şablon seçilmeden yapılandırma paneli görünür', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('Yapılandırma')).toBeVisible({ timeout: 5_000 })
    })

    test('araç raporu şablonu seçince format seçimi (PDF/Excel) görünür', async ({ authedPage: page }) => {
        await page.goto('/reports')
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /Haftalık Filo/i }).click()
        await expect(page.getByText('PDF').first()).toBeVisible({ timeout: 5_000 })
    })
})
