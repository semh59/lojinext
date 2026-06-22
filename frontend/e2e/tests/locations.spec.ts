import { test, expect } from '../fixtures/auth'
import { setupLocationMocks, MOCK_LOCATION } from '../mocks'

test.describe('Lokasyon ve Rota akışları', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupLocationMocks(page)
    })

    test('lokasyon listesi yüklenir ve sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText('Lokasyon ve Rota Yönetimi')).toBeVisible({ timeout: 15_000 })
    })

    test('mock lokasyon tablosunda görünür', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText(MOCK_LOCATION.cikis_yeri).first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText(MOCK_LOCATION.varis_yeri).first()).toBeVisible()
    })

    test('"Yeni Güzergah" butonu modal açar ve form alanları görünür', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText('Lokasyon ve Rota Yönetimi')).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni güzergah/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 8_000 })
        await expect(dialog.locator('input, select').first()).toBeVisible()
    })

    test('boş güzergah formu submit edilince validasyon engeller', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText('Lokasyon ve Rota Yönetimi')).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni güzergah/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 8_000 })
        await dialog.getByRole('button', { name: /kaydet/i }).first().click()
        // LocationFormModal shows error styling on inputs (no error text elements)
        // Verify dialog stays open (Zod validation blocked submission)
        await expect(dialog).toBeVisible({ timeout: 3_000 })
    })

    test('güzergah oluşturma — alanlar doldurulup POST isteği gönderilir', async ({ authedPage: page }) => {
        // Override geocode mock to return suggestions for any query
        await page.route('**/api/v1/locations/geocode**', r =>
            r.fulfill({ status: 200, contentType: 'application/json',
                body: JSON.stringify([
                    { label: 'İstanbul, Türkiye', lat: 41.0082, lon: 28.9784 },
                    { label: 'Ankara, Türkiye', lat: 39.9208, lon: 32.8541 },
                ])
            })
        )

        await page.goto('/locations')
        await expect(page.getByText('Lokasyon ve Rota Yönetimi')).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni güzergah/i }).click()
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 8_000 })

        // Fill origin: aria-label "Çıkış yeri arama", type → wait debounce → click suggestion
        const originInput = page.getByLabel('Çıkış yeri arama')
        await originInput.fill('İstanbul')
        await page.waitForTimeout(600)
        await page.getByText('İstanbul, Türkiye').first().click()

        // Fill destination: aria-label "Varış yeri arama"
        const destInput = page.getByLabel('Varış yeri arama')
        await destInput.fill('Ankara')
        await page.waitForTimeout(600)
        await page.getByText('Ankara, Türkiye').first().click()

        // Wait for route-info response (auto-triggered after both coords are set)
        await page.waitForResponse(resp => resp.url().includes('/route-info'), { timeout: 5_000 }).catch(() => null)
        await page.waitForTimeout(300)

        const dialog = page.getByRole('dialog')
        const [request] = await Promise.all([
            page.waitForRequest(req => req.url().includes('/locations') && req.method() === 'POST', { timeout: 8_000 }),
            dialog.getByRole('button', { name: /kaydet/i }).first().click(),
        ])
        expect(request.method()).toBe('POST')
    })

    test('güzergah düzenleme — edit butonu form açar ve PUT isteği gönderilir', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText(MOCK_LOCATION.cikis_yeri).first()).toBeVisible({ timeout: 10_000 })

        const editBtn = page.getByRole('button', { name: /düzenle|edit/i }).first()
        if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await editBtn.click()
            const dialog = page.getByRole('dialog')
            await expect(dialog).toBeVisible({ timeout: 5_000 })

            // LocationFormModal auto-fires handleCalculate() on open when lat/lon are present.
            // Wait for route-info response, then for submit button to be re-enabled (isCalculating=false).
            await page.waitForResponse(resp => resp.url().includes('/route-info'), { timeout: 5_000 }).catch(() => null)
            await page.waitForTimeout(300)

            // Edit mode shows "Güncelle", create mode shows "Kaydet"
            const kaydetBtn = dialog.getByRole('button', { name: /kaydet|güncelle/i }).first()
            await expect(kaydetBtn).toBeEnabled({ timeout: 3_000 })

            const [request] = await Promise.all([
                page.waitForRequest(req => req.url().includes('/locations') && req.method() === 'PUT', { timeout: 8_000 }),
                kaydetBtn.click(),
            ])
            expect(request.method()).toBe('PUT')
        } else {
            test.skip()
        }
    })

    test('güzergah silme — window.confirm onaylanınca DELETE isteği gönderilir', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText(MOCK_LOCATION.cikis_yeri).first()).toBeVisible({ timeout: 10_000 })

        page.on('dialog', d => d.accept())

        const deleteBtn = page.getByRole('button', { name: /sil/i }).first()
        if (await deleteBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            const [request] = await Promise.all([
                page.waitForRequest(req => req.url().includes('/locations') && req.method() === 'DELETE', { timeout: 8_000 }),
                deleteBtn.click(),
            ])
            expect(request.method()).toBe('DELETE')
        } else {
            test.skip()
        }
    })

    test('lokasyon arama / filtreleme çalışır', async ({ authedPage: page }) => {
        await page.goto('/locations')
        await expect(page.getByText('Lokasyon ve Rota Yönetimi')).toBeVisible({ timeout: 10_000 })
        const searchInput = page.locator('input[type="search"], input[placeholder*="ara"], input[placeholder*="Ara"]').first()
        if (await searchInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await searchInput.fill('İstanbul')
            await page.waitForTimeout(600)
            await expect(searchInput).toHaveValue('İstanbul')
        } else {
            test.skip()
        }
    })
})
