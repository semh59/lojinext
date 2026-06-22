import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const TRIAGE_DATA = {
    critical_count: 1,
    pending_count: 2,
    computed_at: new Date().toISOString(),
    items: [
        {
            id: '1',
            category: 'anomaly',
            severity: 'critical',
            title: 'Yakıt açığı tespit edildi',
            subtitle: '34ABC01 aracı',
            plaka: '34ABC01',
            timestamp: new Date(Date.now() - 5 * 60_000).toISOString(),
            actions: [
                { label: 'İncele', url: '/alerts', action_type: 'navigate' },
            ],
        },
        {
            id: '2',
            category: 'maintenance',
            severity: 'high',
            title: 'Periyodik bakım yaklaşıyor',
            subtitle: '06XY789 aracı',
            plaka: '06XY789',
            timestamp: new Date(Date.now() - 2 * 60 * 60_000).toISOString(),
            actions: [
                { label: 'Planla', url: '/maintenance', action_type: 'navigate' },
            ],
        },
        {
            id: '3',
            category: 'investigation',
            severity: 'medium',
            title: 'Rota sapması soruşturması',
            subtitle: '',
            plaka: null,
            timestamp: new Date(Date.now() - 24 * 60 * 60_000).toISOString(),
            actions: [],
        },
    ],
    active_trips_count: 5,
    completed_today_count: 12,
}

test.describe('TodayPage — Bugün', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/reports/today/triage**', r => r.fulfill(json(TRIAGE_DATA)))
        await page.goto('/today', { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'Bugün' })).toBeVisible({ timeout: 15_000 })
    })

    test('sayfa başlığı ve açıklaması görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Acil eylem listesi + bekleyen aksiyonlar')).toBeVisible()
    })

    test('aktif sefer ve tamamlanan sayaçları gösterilir', async ({ authedPage: page }) => {
        // Sayaçlar — active_trips_count ve completed_today_count
        await expect(page.getByText('Aktif sefer')).toBeVisible()
        await expect(page.getByText('✓ 12')).toBeVisible()
    })

    test('tüm tab butonları render edilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Tümü', exact: true })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Anomali', exact: true })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Bakım', exact: true })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Soruşturma', exact: true })).toBeVisible()
    })

    test('kritik triage kartı görünür ve sınır rengi kritik', async ({ authedPage: page }) => {
        await expect(page.getByText('Yakıt açığı tespit edildi')).toBeVisible()
        await expect(page.getByText('Kritik')).toBeVisible()
    })

    test('yüksek öncelikli triage kartı görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Periyodik bakım yaklaşıyor')).toBeVisible()
        await expect(page.getByText('Yüksek')).toBeVisible()
    })

    test('Anomali sekmesine geçiş sadece anomali kartlarını gösterir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Anomali', exact: true }).click()
        await expect(page.getByText('Yakıt açığı tespit edildi')).toBeVisible()
        await expect(page.getByText('Periyodik bakım yaklaşıyor')).not.toBeVisible()
    })

    test('Bakım sekmesine geçiş sadece bakım kartlarını gösterir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Bakım' }).click()
        await expect(page.getByText('Periyodik bakım yaklaşıyor')).toBeVisible()
        await expect(page.getByText('Yakıt açığı tespit edildi')).not.toBeVisible()
    })

    test('Soruşturma sekmesinde sadece ilgili kart görünür', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Soruşturma' }).click()
        await expect(page.getByText('Rota sapması soruşturması')).toBeVisible()
        await expect(page.getByText('Yakıt açığı tespit edildi')).not.toBeVisible()
    })

    test('triage kartındaki aksiyon butonu tıklanabilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'İncele' }).first()).toBeVisible()
    })

    test('QuickActionsBar — Sefer Planla butonu görünür', async ({ authedPage: page }) => {
        await expect(page.getByText('Hızlı Erişim')).toBeVisible()
        await expect(page.getByRole('button', { name: 'Sefer Planla' })).toBeVisible()
    })

    test('QuickActionsBar — tüm hızlı erişim butonları render edilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Sefer Planla' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Anomaliler' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Şoförler' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Strategic Cockpit' })).toBeVisible()
    })

    test('boş durum — triage boş ise başarı mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/today/triage**')
        await page.route('**/api/v1/reports/today/triage**', r =>
            r.fulfill(json({ items: [], active_trips_count: 0, completed_today_count: 0 }))
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Bugün için acil eylem yok')).toBeVisible({ timeout: 10_000 })
    })

    test('500 hata — hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/reports/today/triage**')
        await page.route('**/api/v1/reports/today/triage**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Sunucu hatası"}' })
        )
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByText('Liste yüklenemedi')).toBeVisible({ timeout: 10_000 })
    })
})
