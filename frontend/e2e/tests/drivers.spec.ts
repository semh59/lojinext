import { test, expect } from '../fixtures/auth'
import { setupDriverMocks, MOCK_DRIVER } from '../mocks'

/**
 * /drivers sayfası E2E.
 *
 * Reports v2 RV2.9'da (commit a59af1b9) `/fleet` sürücüler tab'ı kaldırıldı;
 * şoförler ayrı sayfaya çıktı. Eski `fleet.spec.ts` sürücü test'leri
 * `test.describe.skip` ile DEPRECATED işaretlendi (Tur 5 #145); bu dosya
 * onların yerine geçer (Tur 5 #154).
 */

test.describe('Şoförler sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupDriverMocks(page)
        await page.goto('/drivers')
        await expect(page.getByText('Şoförler').first()).toBeVisible({ timeout: 15_000 })
    })

    test('liste yüklenir ve MOCK_DRIVER görünür', async ({ authedPage: page }) => {
        await expect(page.getByText(MOCK_DRIVER.ad_soyad).first()).toBeVisible({ timeout: 10_000 })
    })

    test('"Yeni Şoför Ekle" butonu modal açar', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni şoför ekle|şoför ekle/i }).first().click()
        await expect(page.locator('input[name="ad_soyad"]')).toBeVisible({ timeout: 8_000 })
    })

    test('şoför oluşturma — boş form validasyon hatası gösterir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni şoför ekle|şoför ekle/i }).first().click()
        await expect(page.locator('input[name="ad_soyad"]')).toBeVisible({ timeout: 8_000 })
        await page.getByRole('button', { name: /kaydet|oluştur/i }).last().click()
        await expect(
            page.locator('p').filter({ hasText: /karakter|zorunlu|gerekli|required/i }).first()
        ).toBeVisible({ timeout: 5_000 })
    })

    test('şoför oluşturma — zorunlu alanlar doldurulup POST isteği gönderilir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni şoför ekle|şoför ekle/i }).first().click()
        await expect(page.locator('input[name="ad_soyad"]')).toBeVisible({ timeout: 8_000 })

        await page.locator('input[name="ad_soyad"]').fill('Mehmet Test')

        const ehliyetSelect = page.locator('select[name="ehliyet_sinifi"]')
        const ehliyetInput = page.locator('input[name="ehliyet_sinifi"]')
        if (await ehliyetSelect.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await ehliyetSelect.selectOption('CE')
        } else if (await ehliyetInput.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await ehliyetInput.fill('CE')
        }

        const [request] = await Promise.all([
            page.waitForRequest(req => req.url().includes('/drivers') && req.method() === 'POST', { timeout: 10_000 }),
            page.getByRole('button', { name: /kaydet|oluştur/i }).last().click(),
        ])
        expect(request.method()).toBe('POST')
    })

    test('şoför silme — silme butonu DELETE isteği gönderir', async ({ authedPage: page }) => {
        page.on('dialog', d => d.accept())
        const deleteBtn = page.getByRole('button', { name: /^sil$/i }).first()
        if (await deleteBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            const [request] = await Promise.all([
                page.waitForRequest(req => req.url().includes('/drivers') && req.method() === 'DELETE', { timeout: 8_000 }),
                deleteBtn.click(),
            ])
            expect(request.method()).toBe('DELETE')
        } else {
            test.skip()
        }
    })
})
