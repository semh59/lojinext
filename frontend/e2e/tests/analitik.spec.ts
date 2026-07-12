import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_ANALYTICS = {
    period_days: 30,
    total_views: 1_240,
    top_routes: [
        { route: '/trips', count: 450 },
        { route: '/fuel', count: 310 },
        { route: '/fleet', count: 220 },
    ],
    bottom_routes: [
        { route: '/route-lab', count: 5 },
        { route: '/admin/analitik', count: 8 },
        { route: '/admin/ml', count: 12 },
    ],
}

test.describe('AdminAnalyticsPage — Kullanım Analitiği', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/analytics**', r => r.fulfill(json(MOCK_ANALYTICS)))
        await page.goto('/admin/analitik', { waitUntil: 'domcontentloaded' })
        // AdminLayout'un üst çubuğu (h2) VE sayfanın kendi başlığı (h1) aynı
        // metni ("Kullanım Analitiği") gösteriyor — level:1 ile sayfanın kendi
        // h1'i hedeflenir, strict-mode çift-eşleşme önlenir.
        await expect(page.getByRole('heading', { name: 'Kullanım Analitiği', level: 1 })).toBeVisible({ timeout: 15_000 })
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await expect(page.getByRole('heading', { name: 'Kullanım Analitiği', level: 1 })).toBeVisible()
    })

    test('periyot ve toplam görüntüleme bilgisi gösterilir', async ({ authedPage: page }) => {
        await expect(page.getByText(/30 gün/)).toBeVisible()
        await expect(page.getByText(/1.240|1240/)).toBeVisible()
    })

    test('"En çok kullanılan" bölümü render edilir', async ({ authedPage: page }) => {
        await expect(page.getByText('En çok kullanılan')).toBeVisible()
        await expect(page.getByText('/trips')).toBeVisible()
        await expect(page.getByText('450')).toBeVisible()
    })

    test('"En az kullanılan" bölümü render edilir', async ({ authedPage: page }) => {
        await expect(page.getByText('En az kullanılan')).toBeVisible()
        await expect(page.getByText('/route-lab')).toBeVisible()
        // '5' birden fazla elementte eşleşebilir → .first() ile strict mode ihlali önlenir
        await expect(page.getByText('5').first()).toBeVisible()
    })

    test('tüm top route satırları render edilir', async ({ authedPage: page }) => {
        await expect(page.getByText('/fuel')).toBeVisible()
        await expect(page.getByText('/fleet')).toBeVisible()
        await expect(page.getByText('310')).toBeVisible()
    })

    test('yükleniyor durumu — sayfa veri yükler ve render eder', async ({ authedPage: page }) => {
        // Yeniden yükleme sonrası veriler görünmeli
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('/trips')).toBeVisible({ timeout: 10_000 })
    })

    test('boş veri — sıfır görüntüleme doğru render edilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/admin/analytics**')
        await page.route('**/api/v1/admin/analytics**', r =>
            r.fulfill(json({ period_days: 30, total_views: 0, top_routes: [], bottom_routes: [] }))
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('0')).toBeVisible({ timeout: 10_000 })
    })
})
