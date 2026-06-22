import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_TEMPLATES = [
    {
        id: 'ceo_1pager',
        title: 'CEO 1-Sayfa Özet',
        description: 'Yönetim için kısa özet raporu.',
        category: 'executive',
        formats: ['pdf'],
        endpoint_hint: '/reports/executive/pdf',
        supports_period: false,
        supports_vehicle: false,
    },
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
    {
        id: 'carbon_report',
        title: 'Karbon Ayak İzi',
        description: 'CO₂ emisyon raporu.',
        category: 'compliance',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/carbon',
        supports_period: true,
        supports_vehicle: false,
    },
    {
        id: 'what_if',
        title: 'What-If Senaryosu',
        description: 'Senaryo bazlı analiz.',
        category: 'executive',
        formats: ['pdf'],
        endpoint_hint: '/reports/executive/pdf',
        supports_period: false,
        supports_vehicle: false,
    },
]

test.describe('ReportsStudioPage — Rapor Stüdyosu', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        // LIFO: catch-all önce kayıt (son kontrol), spesifik sonra kayıt (ilk kontrol)
        await page.route('**/api/v1/reports/**', r => r.fulfill(json({})))
        await page.route('**/api/v1/executive/**', r => r.fulfill(json({})))
        // Bu iki route spesifik — LIFO'da ilk eşleşir
        await page.route('**/api/v1/reports/studio/templates**', r =>
            r.fulfill(json({ templates: MOCK_TEMPLATES, count: MOCK_TEMPLATES.length }))
        )
        await page.goto('/reports', { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'Rapor Stüdyosu' })).toBeVisible({ timeout: 15_000 })
    })

    test('sayfa başlığı ve açıklaması görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Hazır şablonlardan rapor oluşturun.')).toBeVisible()
    })

    test('şablon galerisi başlığı görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Şablon Kütüphanesi')).toBeVisible()
    })

    test('tüm 6 şablon kartı render edilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: /CEO 1-Sayfa/i })).toBeVisible({ timeout: 8_000 })
        await expect(page.getByRole('button', { name: /Haftalık Filo/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Yakıt Maliyet/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Araç Karşılaştırma/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Karbon Ayak/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /What-If/i })).toBeVisible()
    })

    test('şablon seçilmeden config paneli ipucu gösterir', async ({ authedPage: page }) => {
        await expect(page.getByTestId('config-empty')).toBeVisible()
    })

    test('şablona tıklayınca config paneli aktif olur', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Haftalık Filo/i }).click()
        // Config panel - İndir butonu görünmeli
        await expect(page.getByRole('button', { name: /İndir/i })).toBeVisible({ timeout: 8_000 })
    })

    test('periyot seçim render edilir (şablon seçince)', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Haftalık Filo/i }).click()
        // Periyot label'ı görünmeli
        await expect(page.getByText('Periyot')).toBeVisible({ timeout: 5_000 })
    })

    test('format seçimi PDF görünür (şablon seçince)', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Haftalık Filo/i }).click()
        await expect(page.getByText('PDF').first()).toBeVisible({ timeout: 5_000 })
    })

    test('şablonlar yüklenemediğinde hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/studio/templates**')
        await page.route('**/api/v1/reports/studio/templates**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"hata"}' })
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByTestId('gallery-error').or(page.getByText('Şablonlar yüklenemedi.'))).toBeVisible({ timeout: 10_000 })
    })

    test('şablon listesi boş ise boş durum mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/studio/templates**')
        await page.route('**/api/v1/reports/studio/templates**', r =>
            r.fulfill(json({ templates: [], count: 0 }))
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Henüz şablon yüklenmedi.')).toBeVisible({ timeout: 10_000 })
    })

    test('Yapılandırma panel başlığı her zaman görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Yapılandırma')).toBeVisible()
    })
})
