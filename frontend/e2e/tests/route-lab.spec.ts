import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const MOCK_LOCATIONS = {
    items: [
        { id: 1, cikis_yeri: 'İstanbul', varis_yeri: 'Ankara', mesafe_km: 450 },
        { id: 2, cikis_yeri: 'Ankara', varis_yeri: 'İzmir', mesafe_km: 600 },
    ],
    total: 2,
}

const MOCK_SIM_RESULT = {
    simulation_id: 1,
    created_at: '2026-06-30T10:00:00',
    summary: {
        distance_km: 451.2,
        duration_min: 300.0,
        total_l: 135.3,
        avg_l_per_100km: 30.0,
        total_ascent_m: 850,
        total_descent_m: 720,
    },
    elevation_coverage_pct: 85,
    raw_segment_count: 1,
    resampled_segment_count: 1,
    meta: {},
    segments: [
        {
            seq: 1,
            length_km: 10.0,
            grade_pct: 1.2,
            road_class: 'motorway',
            sim_speed_kmh: 90,
            sim_l_per_100km: 29.5,
            sim_l_total: 2.95,
            eta_sec: 400,
            mid_lat: 41.0,
            mid_lon: 28.9,
            maxspeed_kmh: null,
            traffic_speed_kmh: null,
            congestion: 'free',
            speed_source: 'osm',
        },
    ],
}

test.describe('RouteLabPage — Güzergah Laboratuvarı', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/locations**', r => r.fulfill(json(MOCK_LOCATIONS)))
        await page.route('**/api/v1/routes/simulate**', r => r.fulfill(json(MOCK_SIM_RESULT)))
        await page.goto('/route-lab', { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'Güzergah Laboratuvarı' })).toBeVisible({ timeout: 15_000 })
    })

    test('sayfa başlığı ve açıklama görünür', async ({ authedPage: page }) => {
        await expect(page.getByText(/500m segment çözünürlüğünde/i)).toBeVisible()
    })

    test('"Kayıtlı güzergah" ve "Koordinat gir" mode butonları render edilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Kayıtlı güzergah' })).toBeVisible()
        await expect(page.getByRole('button', { name: 'Koordinat gir' })).toBeVisible()
    })

    test('varsayılan mod — güzergah select kutusu görünür', async ({ authedPage: page }) => {
        await expect(page.locator('select#route-lab-loc').or(page.getByLabel('Güzergah'))).toBeVisible()
    })

    test('"Simüle Et" butonu render edilir', async ({ authedPage: page }) => {
        await expect(page.getByRole('button', { name: 'Simüle Et' })).toBeVisible()
    })

    test('boş form ile simüle tıklanınca hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Simüle Et' }).click()
        // select <option> da eşleşir ama hidden; <p> hata mesajı hedefle
        await expect(page.locator('p').filter({ hasText: /seçip|güzergah seçin|seçin/i }).first()).toBeVisible({ timeout: 5_000 })
    })

    test('"Koordinat gir" moduna geçince koordinat alanları görünür', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Koordinat gir' }).click()
        await expect(page.getByLabel('Çıkış enlem')).toBeVisible()
        await expect(page.getByLabel('Varış enlem')).toBeVisible()
    })

    test('koordinat modunda eksik koordinat ile submit hata verir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: 'Koordinat gir' }).click()
        await page.getByRole('button', { name: 'Simüle Et' }).click()
        // "Koordinat gir" butonu da /koordinat/i eşleşir → p elementi hedefle
        await expect(page.locator('p').filter({ hasText: /koordinat|zorunlu/i }).first()).toBeVisible({ timeout: 5_000 })
    })

    test('Yük ve araç yaşı input alanları görünür', async ({ authedPage: page }) => {
        await expect(page.getByLabel('Yük (ton)')).toBeVisible()
        await expect(page.getByLabel('Araç yaşı')).toBeVisible()
    })

    test('simülasyon başarılı — özet veriler render edilir', async ({ authedPage: page }) => {
        // Güzergah seç ve submit
        await page.locator('select#route-lab-loc, select').first().selectOption({ index: 1 })
        const [req] = await Promise.all([
            page.waitForRequest(r => r.url().includes('/routes/simulate'), { timeout: 10_000 }),
            page.getByRole('button', { name: 'Simüle Et' }).click(),
        ])
        expect(req.method()).toBe('POST')
        // Sonuç: mesafe veya yakıt değeri render edilmeli
        await expect(page.getByText(/451|135|30/).first()).toBeVisible({ timeout: 10_000 })
    })

    test('429 rate limit hatası — hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/routes/simulate**')
        await page.route('**/api/v1/routes/simulate**', r =>
            r.fulfill({ status: 429, contentType: 'application/json', body: '{"detail":"Rate limited"}' })
        )
        await page.locator('select#route-lab-loc, select').first().selectOption({ index: 1 })
        await page.getByRole('button', { name: 'Simüle Et' }).click()
        await expect(page.getByText(/çok fazla istek|bekleyip/i)).toBeVisible({ timeout: 10_000 })
    })

    test('502 sağlayıcı hatası — Mapbox hata mesajı gösterilir', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/routes/simulate**')
        await page.route('**/api/v1/routes/simulate**', r =>
            r.fulfill({ status: 502, contentType: 'application/json', body: '{"detail":"Bad Gateway"}' })
        )
        await page.locator('select#route-lab-loc, select').first().selectOption({ index: 1 })
        await page.getByRole('button', { name: 'Simüle Et' }).click()
        await expect(page.getByText(/Mapbox|sağlayıcı/i)).toBeVisible({ timeout: 10_000 })
    })

    test('Koordinat gir modu ile başarılı simülasyon yapılır', async ({ authedPage: page }) => {
        let simPayload: any = null
        await page.route('**/api/v1/routes/simulate**', r => {
            simPayload = r.request().postDataJSON()
            return r.fulfill(json(MOCK_SIM_RESULT))
        })

        // 1. Koordinat moduna geç
        await page.getByRole('button', { name: 'Koordinat gir' }).click()

        // 2. Alanları doldur
        const cikisLat = page.locator('input').filter({ hasText: '' }).nth(0)
        await page.getByLabel('Çıkış enlem').fill('41.0082')
        await page.getByLabel('Çıkış boylam').fill('28.9784')
        await page.getByLabel('Varış enlem').fill('39.9208')
        await page.getByLabel('Varış boylam').fill('32.8541')

        await page.getByLabel('Yük (ton)').fill('22')
        await page.getByLabel('Araç yaşı').fill('4')

        // 3. Simüle et tıklanmalı
        await page.getByRole('button', { name: 'Simüle Et' }).click()

        // 4. API payload doğrulaması
        await expect.poll(() => simPayload).toBeTruthy()
        expect(simPayload).toMatchObject({
            cikis_lat: 41.0082,
            cikis_lon: 28.9784,
            varis_lat: 39.9208,
            varis_lon: 32.8541,
            ton: 22,
            arac_yasi: 4
        })

        // 5. Sonuçların göründüğünü doğrula
        await expect(page.getByText(/451\.2|135\.3|30\.0/)).toBeVisible({ timeout: 10_000 })
    })
})
