import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

// title/description burada gercekten onemsiz gibi gorunse de asagidaki
// REPORT_TEMPLATE_LABELS (frontend/src/lib/status-labels.ts) her zaman bu 6
// ID icin hardcoded Turkce/Ingilizce metni kullanip API'nin donduguu title/
// description'i TAMAMEN gormezden geliyor (backend'in 6 statik sablonu
// yalniz Turkce gonderdigi icin eklenen bir i18n override). Playwright
// locale'i 'tr-TR' oldugundan .tr degerleri render edilir — bu yuzden
// mock'taki title/description alanlari REPORT_TEMPLATE_LABELS'teki gercek
// degerlerle BIREBIR ayni olmali, yoksa asagidaki testler (ekranda gercekte
// gorunen metni degil, mock'un kendi metnini arayarak) hep FAIL eder.
const MOCK_TEMPLATES = [
    {
        id: 'ceo_1pager',
        title: 'CEO Aylık 1-Pager',
        description:
            'Tek sayfalık üst yönetim özeti — FVI, maliyet, anomali ve uyum metrikleri.',
        category: 'executive',
        formats: ['pdf'],
        endpoint_hint: '/reports/executive/pdf',
        supports_period: false,
        supports_vehicle: false,
    },
    {
        id: 'fleet_weekly',
        title: 'Filo Müdürü Haftalık',
        description:
            'Haftalık operasyon özeti — FVI, period karşılaştırma, cross-feature kazanım.',
        category: 'fleet',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/fleet',
        supports_period: true,
        supports_vehicle: true,
    },
    {
        id: 'fuel_cost_analysis',
        title: 'Yakıt Maliyet Analizi',
        description: 'Aylık yakıt maliyet trendi ve dönem karşılaştırması.',
        category: 'fuel',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/fuel',
        supports_period: true,
        supports_vehicle: false,
    },
    {
        id: 'vehicle_comparison',
        title: 'Araç Karşılaştırma',
        description:
            'Filodaki araçların ortalama tüketim ve maliyet karşılaştırması.',
        category: 'fleet',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/vehicle',
        supports_period: true,
        supports_vehicle: true,
    },
    {
        id: 'carbon_report',
        title: 'Karbon Raporu',
        description: '12 ay CO₂ emisyon özeti ve hedef sapması.',
        category: 'compliance',
        formats: ['pdf', 'excel'],
        endpoint_hint: '/reports/carbon',
        supports_period: true,
        supports_vehicle: false,
    },
    {
        id: 'what_if',
        title: 'What-If Sonucu',
        description:
            "Strategic Cockpit'te çalıştırılan senaryonun PDF olarak indirilmesi.",
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
        await expect(page.getByRole('button', { name: /CEO Aylık/i })).toBeVisible({ timeout: 8_000 })
        await expect(page.getByRole('button', { name: /Filo Müdürü Haftalık/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Yakıt Maliyet/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Araç Karşılaştırma/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /Karbon Raporu/i })).toBeVisible()
        await expect(page.getByRole('button', { name: /What-If/i })).toBeVisible()
    })

    test('şablon seçilmeden config paneli ipucu gösterir', async ({ authedPage: page }) => {
        await expect(page.getByTestId('config-empty')).toBeVisible()
    })

    test('şablona tıklayınca config paneli aktif olur', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Filo Müdürü Haftalık/i }).click()
        // Config panel - İndir butonu görünmeli
        await expect(page.getByRole('button', { name: /İndir/i })).toBeVisible({ timeout: 8_000 })
    })

    test('periyot seçim render edilir (şablon seçince)', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Filo Müdürü Haftalık/i }).click()
        // Periyot label'ı görünmeli
        await expect(page.getByText('Periyot')).toBeVisible({ timeout: 5_000 })
    })

    test('format seçimi PDF görünür (şablon seçince)', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /Filo Müdürü Haftalık/i }).click()
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
