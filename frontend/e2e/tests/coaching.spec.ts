import { test, expect } from '../fixtures/auth'

const MOCK_DRIVER = {
    id: 1,
    ad_soyad: 'Ahmet Yılmaz',
    aktif: true,
    score: 0.85,
    ehliyet_sinifi: 'E',
}

const MOCK_EFFECTIVENESS = {
    window_days: 30,
    total_sent: 12,
    total_evaluated: 8,
    improved: 5,
    worsened: 2,
    improve_rate: 0.625,
    avg_score_delta_pct: 3.2,
    caveat: 'Yalnızca koçluk etkisini yansıtmaz.',
}

const MOCK_INSIGHTS = {
    sofor_id: 1,
    ad_soyad: 'Ahmet Yılmaz',
    headline: 'Yakıt verimliliği düşük',
    priority: 'high',
    insights: [{
        category: 'yakit_yonetimi',
        pattern: 'Boş viteste bekleme',
        evidence: ['12 sefer ortalaması'],
        suggestion: 'Rölanti süresini azaltın',
        impact_score: 0.8,
    }],
    generated_at: '2025-01-15T10:00:00',
    source: 'llm',
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Koçluk Modülü sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/drivers/**', r =>
            r.fulfill(json({ items: [MOCK_DRIVER], total: 1 }))
        )
        await page.route('**/api/v1/coaching/effectiveness**', r =>
            r.fulfill(json(MOCK_EFFECTIVENESS))
        )
        await page.route('**/api/v1/coaching/*/insights**', r =>
            r.fulfill(json(MOCK_INSIGHTS))
        )
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
    })

    test('etkinlik kartı yüklenir — Son 30 Gün Etkinliği ve Gönderilen sayısı görünür', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('Son 30 Gün Etkinliği').first()).toBeVisible({ timeout: 8_000 })
        // total_sent = 12, shown under "Gönderilen" stat
        const gonderilenStat = page.locator('div').filter({ hasText: /Gönderilen/ }).first()
        await expect(gonderilenStat.getByText('12')).toBeVisible({ timeout: 8_000 })
    })

    test('şoför listesi yüklenir — Ahmet Yılmaz butonu görünür', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.locator('button').filter({ hasText: 'Ahmet Yılmaz' }).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('şoför seçilmeden ipucu mesajı gösterilir', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
        await expect(
            page.getByText('Detay görmek için sol panelden bir şoför seçin.').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('şoför seçince insights yüklenir — headline görünür', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })

        const driverBtn = page.locator('button').filter({ hasText: 'Ahmet Yılmaz' }).first()
        await driverBtn.waitFor({ state: 'visible', timeout: 8_000 })

        const insightsResponse = page.waitForResponse('**/api/v1/coaching/*/insights**')
        await driverBtn.click()
        await insightsResponse

        await expect(page.getByText('Yakıt verimliliği düşük').first()).toBeVisible({ timeout: 8_000 })
    })

    test('insight pattern metni görünür — şoför seçimi sonrası', async ({ authedPage: page }) => {
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })

        const driverBtn = page.locator('button').filter({ hasText: 'Ahmet Yılmaz' }).first()
        await driverBtn.waitFor({ state: 'visible', timeout: 8_000 })

        const insightsResponse = page.waitForResponse('**/api/v1/coaching/*/insights**')
        await driverBtn.click()
        await insightsResponse

        await expect(page.getByText('Boş viteste bekleme').first()).toBeVisible({ timeout: 8_000 })
    })

    test('boş şoför listesi: boş durum gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/drivers/**')
        await page.route('**/api/v1/drivers/**', r =>
            r.fulfill(json({ data: [], meta: { total: 0 } }))
        )
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('Aktif şoför bulunamadı.').first()).toBeVisible({ timeout: 8_000 })
    })

    test('insights API 503 döndüğünde hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/coaching/*/insights**')
        await page.route('**/api/v1/coaching/*/insights**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Service Unavailable"}' })
        )
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })

        const driverBtn = page.locator('button').filter({ hasText: 'Ahmet Yılmaz' }).first()
        await driverBtn.waitFor({ state: 'visible', timeout: 8_000 })

        const insightsResponse = page.waitForResponse('**/api/v1/coaching/*/insights**')
        await driverBtn.click()
        await insightsResponse

        await expect(page.getByText('Öneriler yüklenemedi').first()).toBeVisible({ timeout: 8_000 })
    })

    test('backend 500 döndüğünde sayfa çökmez — başlık hâlâ görünür', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/drivers/**')
        await page.unroute('**/api/v1/coaching/effectiveness**')
        await page.unroute('**/api/v1/coaching/*/insights**')
        await page.route('**/api/v1/drivers/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' })
        )
        await page.route('**/api/v1/coaching/effectiveness**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' })
        )
        await page.route('**/api/v1/coaching/*/insights**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' })
        )
        await page.goto('/coaching')
        await expect(page.getByText('Koçluk Modülü').first()).toBeVisible({ timeout: 10_000 })
    })
})
