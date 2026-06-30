import { test, expect } from '../fixtures/auth'

const MOCK_VEHICLE = { id: 1, plaka: '34ABC01', marka: 'Mercedes' }
const MOCK_DRIVER  = { id: 1, ad_soyad: 'Ahmet Yılmaz', aktif: true, score: 1.0 }

function json(body: unknown, status = 200) {
    return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Atama Düzeltme sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/vehicles/**', r =>
            r.fulfill(json({ data: [MOCK_VEHICLE], meta: { total: 1, skip: 0, limit: 20 }, errors: null }))
        )
        await page.route('**/api/v1/drivers/**', r =>
            r.fulfill(json({ data: [MOCK_DRIVER], meta: { total: 1, skip: 0, limit: 20 }, errors: null }))
        )
        await page.route('**/api/v1/admin/attribution/override', r =>
            r.fulfill(json({ ok: true }))
        )
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
    })

    test('araç seçenekleri yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
        // Vehicle select shows "{plaka} — {marka}"
        const vehicleSelect = page.locator('div').filter({ hasText: /^Yeni Araç \(opsiyonel\)/ }).locator('select').nth(0)
        await expect(vehicleSelect).toBeVisible({ timeout: 8_000 })
        await expect(vehicleSelect.locator('option', { hasText: '34ABC01 — Mercedes' })).toBeAttached({ timeout: 8_000 })
    })

    test('şoför seçenekleri yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
        // Driver select shows "{ad_soyad}"
        const driverSelect = page.locator('div').filter({ hasText: /^Yeni Şoför \(opsiyonel\)/ }).locator('select').nth(0)
        await expect(driverSelect).toBeVisible({ timeout: 8_000 })
        await expect(driverSelect.locator('option', { hasText: 'Ahmet Yılmaz' })).toBeAttached({ timeout: 8_000 })
    })

    test('validation: Sefer ID boş ise hata gösterilir', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
        // Click submit without filling anything
        await page.getByRole('button', { name: 'Atamayı Güncelle' }).click()
        await expect(page.getByText('Geçerli bir Sefer ID girin')).toBeVisible({ timeout: 5_000 })
    })

    test('validation: en az araç veya şoför seçilmeli', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
        // Fill sefer ID — skip vehicle and driver — fill reason
        await page.locator('input[type="number"]').fill('1')
        // Leave both selects at default ("Değiştirme")
        await page.locator('textarea').fill('Yeterli gerekce metni')
        await page.getByRole('button', { name: 'Atamayı Güncelle' }).click()
        await expect(page.getByText('En az araç veya şoför seçin')).toBeVisible({ timeout: 5_000 })
    })

    test('validation: gerekçe çok kısa', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
        // Fill sefer ID + select vehicle + short reason
        await page.locator('input[type="number"]').fill('1')
        const vehicleSelect = page.locator('div').filter({ hasText: /^Yeni Araç \(opsiyonel\)/ }).locator('select').nth(0)
        await vehicleSelect.waitFor({ state: 'visible', timeout: 8_000 })
        await vehicleSelect.selectOption({ value: '1' })
        await page.locator('textarea').fill('AB')
        await page.getByRole('button', { name: 'Atamayı Güncelle' }).click()
        await expect(
            page.getByText('Gerekçe en az 5 karakter olmalı (denetim kaydı için)')
        ).toBeVisible({ timeout: 5_000 })
    })

    test('başarılı gönderim: POST isteği doğru gönderilir', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })

        await page.locator('input[type="number"]').fill('1')
        const vehicleSelect = page.locator('div').filter({ hasText: /^Yeni Araç \(opsiyonel\)/ }).locator('select').nth(0)
        await vehicleSelect.waitFor({ state: 'visible', timeout: 8_000 })
        await vehicleSelect.selectOption({ value: '1' })
        // Leave driver unselected (vehicle is enough)
        await page.locator('textarea').fill('Test gerekce')

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/api/v1/admin/attribution/override') && req.method() === 'POST',
                { timeout: 8_000 }
            ),
            page.getByRole('button', { name: 'Atamayı Güncelle' }).click(),
        ])

        expect(request.method()).toBe('POST')
        const body = request.postDataJSON()
        expect(body).toMatchObject({
            sefer_id: 1,
            new_arac_id: 1,
            new_sofor_id: null,
            reason: 'Test gerekce',
        })
    })

    test('başarılı gönderim: toast mesajı görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/atama')
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })

        await page.locator('input[type="number"]').fill('1')
        const vehicleSelect = page.locator('div').filter({ hasText: /^Yeni Araç \(opsiyonel\)/ }).locator('select').nth(0)
        await vehicleSelect.waitFor({ state: 'visible', timeout: 8_000 })
        await vehicleSelect.selectOption({ value: '1' })
        await page.locator('textarea').fill('Test gerekce')

        await Promise.all([
            page.waitForResponse(
                res => res.url().includes('/api/v1/admin/attribution/override'),
                { timeout: 8_000 }
            ),
            page.getByRole('button', { name: 'Atamayı Güncelle' }).click(),
        ])

        await expect(
            page.getByText(/Sefer ataması güncellendi/)
        ).toBeVisible({ timeout: 8_000 })
    })

    test('backend 500 → sayfa çökmez', async ({ authedPage: page }) => {
        await page.unroute('**/api/v1/vehicles/**')
        await page.unroute('**/api/v1/drivers/**')
        // Override both data endpoints with 500
        await page.route('**/api/v1/vehicles/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.route('**/api/v1/drivers/**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"error"}' })
        )
        await page.goto('/admin/atama')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        // Page heading must still be visible (ErrorBoundary did not swallow the whole page)
        await expect(page.getByText('Sefer Atama Düzeltme').first()).toBeVisible({ timeout: 10_000 })
    })
})
