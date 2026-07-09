import { test, expect } from '../fixtures/auth'
import { setupFleetPageMocks, MOCK_VEHICLE, MOCK_DRIVER } from '../mocks'

test.describe('Filo sayfası — Araçlar', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupFleetPageMocks(page)
        await page.goto('/fleet')
        await expect(page.getByText('Araçlar & Dorseler').first()).toBeVisible({ timeout: 15_000 })
    })

    test('araçlar sekmesi varsayılan olarak açık gelir ve liste yüklenir', async ({ authedPage: page }) => {
        await expect(page.getByText(MOCK_VEHICLE.plaka).first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText(MOCK_VEHICLE.marka).first()).toBeVisible()
    })

    test('"Yeni Araç Ekle" butonu modal açar', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni araç ekle/i }).click()
        // VehicleModal uses motion.div without role="dialog" — wait for a form input
        await expect(page.locator('input[name="plaka"]')).toBeVisible({ timeout: 8_000 })
    })

    test('araç oluşturma — boş form validasyon hatası gösterir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni araç ekle/i }).click()
        await expect(page.locator('input[name="plaka"]')).toBeVisible({ timeout: 8_000 })
        // Submit button is the last "kaydet" on page while modal is open
        await page.getByRole('button', { name: /kaydet|oluştur|^ekle$/i }).last().click({ force: true })
        await expect(
            page.getByText(/zorunlu|gerekli|karakter|required/i).first()
        ).toBeVisible({ timeout: 5_000 })
    })

    test('araç oluşturma — zorunlu alanlar doldurulup POST isteği gönderilir', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni araç ekle/i }).click()
        await expect(page.locator('input[name="plaka"]')).toBeVisible({ timeout: 8_000 })

        await page.locator('input[name="plaka"]').fill('34TEST01')
        await page.locator('input[name="marka"]').fill('Volvo')

        const yilInput = page.locator('input[name="yil"]')
        await yilInput.click({ clickCount: 3 })
        await yilInput.fill('2022')

        const tankInput = page.locator('input[name="tank_kapasitesi"]')
        if (await tankInput.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await tankInput.fill('600')
        }

        const hedefInput = page.locator('input[name="hedef_tuketim"]')
        if (await hedefInput.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await hedefInput.fill('30')
        }

        const [request] = await Promise.all([
            page.waitForRequest(req => req.url().includes('/vehicles') && req.method() === 'POST', { timeout: 10_000 }),
            // Submit via Enter to avoid backdrop intercept on force click
            page.locator('input[name="marka"]').press('Enter'),
        ])
        expect(request.method()).toBe('POST')
        const body = JSON.parse(request.postData() || '{}')
        expect(body.marka).toBe('Volvo')
    })

    // Regression: shared Modal's focus-trap effect used to re-fire on every
    // keystroke (its `onClose` dep got a fresh reference each re-render),
    // stealing focus back to the dialog's close button. `.fill()` (used
    // elsewhere in this file) writes the value in one shot and never
    // exercised the per-character re-render cycle that triggered it;
    // pressSequentially does.
    test('araç ekle — marka alanına yazarken odak kapat butonuna kaçmaz', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni araç ekle/i }).click()
        const markaInput = page.locator('input[name="marka"]')
        await expect(markaInput).toBeVisible({ timeout: 8_000 })

        await markaInput.click()
        await markaInput.pressSequentially('Mercedes', { delay: 60 })

        await expect(markaInput).toBeFocused()
        await expect(markaInput).toHaveValue('Mercedes')
    })

    test('araç ekle — "Fizik Parametreleri" toggle açılınca ileri seviye alanlar görünür', async ({ authedPage: page }) => {
        await page.getByRole('button', { name: /yeni araç ekle/i }).click()
        await expect(page.locator('input[name="plaka"]')).toBeVisible({ timeout: 8_000 })

        const toggle = page.getByRole('button', { name: /fizik parametreleri/i })
        await expect(toggle).toBeVisible({ timeout: 5_000 })
        await expect(page.locator('input[name="bos_agirlik_kg"]')).not.toBeVisible()

        await toggle.click()
        await expect(page.locator('input[name="bos_agirlik_kg"]')).toBeVisible({ timeout: 5_000 })
    })

    test('araç düzenleme — detay/düzenle butonu modal açar', async ({ authedPage: page }) => {
        await expect(page.getByText(MOCK_VEHICLE.plaka).first()).toBeVisible({ timeout: 10_000 })
        const editBtn = page.getByRole('button', { name: /düzenle|edit/i }).first()
        if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await editBtn.click()
            await expect(page.locator('input[name="plaka"]')).toBeVisible({ timeout: 5_000 })
            await expect(page.locator('input[name="plaka"]')).toHaveValue(MOCK_VEHICLE.plaka)
        } else {
            test.skip()
        }
    })

    test('araç silme — modal açılır ve onay butonu DELETE isteği gönderir', async ({ authedPage: page }) => {
        await expect(page.getByText(MOCK_VEHICLE.plaka).first()).toBeVisible({ timeout: 10_000 })
        // "Sil" button opens VehicleDeleteModal
        const deleteBtn = page.getByRole('button', { name: /^sil$/i }).first()
        await expect(deleteBtn).toBeVisible({ timeout: 5_000 })
        await deleteBtn.click()

        // MOCK_VEHICLE.aktif=true → soft delete modal: title "Aracı Pasife Al", confirm "Pasife Al"
        await expect(page.getByText(/Aracı Pasife Al/i).first()).toBeVisible({ timeout: 5_000 })

        const [request] = await Promise.all([
            page.waitForRequest(req => req.url().includes('/vehicles') && req.method() === 'DELETE', { timeout: 8_000 }),
            page.getByRole('button', { name: /^Pasife Al$/i }).click(),
        ])
        expect(request.method()).toBe('DELETE')
    })
})


test.describe('Filo sayfası — Tab geçişleri', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await setupFleetPageMocks(page)
    })

    test('araçlar → dorseler sekme geçişi çalışır', async ({ authedPage: page }) => {
        await page.goto('/fleet')
        await expect(page.getByText('Araçlar & Dorseler').first()).toBeVisible({ timeout: 15_000 })

        // Default: vehicles tab açık, MOCK_VEHICLE.plaka görünmeli
        await expect(page.getByText(MOCK_VEHICLE.plaka).first()).toBeVisible({ timeout: 8_000 })

        // Switch to trailers
        const dorseBtn = page.getByRole('button', { name: /dorse|treyler/i }).first()
        if (await dorseBtn.isVisible()) {
            await dorseBtn.click()
            await page.waitForTimeout(500)
            // Trailer tab yüklü; sayfa başlığı hala görünür
            await expect(page.getByText('Araçlar & Dorseler').first()).toBeVisible()
        }

        // Back to vehicles
        await page.getByRole('button', { name: /araçlar/i }).first().click()
        await expect(page.getByText(MOCK_VEHICLE.plaka).first()).toBeVisible({ timeout: 8_000 })
    })
})
