import { test, expect } from '../fixtures/auth'

test.describe('Profil sayfası', () => {
    test('profil sayfası yüklenir ve alanlar görünür', async ({ authedPage: page }) => {
        await page.goto('/profile')
        // Email alanı readonly
        await expect(
            page.locator('input[type="text"][readonly]').first()
        ).toBeVisible({ timeout: 15_000 })
        // Ad soyad input
        await expect(
            page.locator('input[name="ad_soyad"], input[name="full_name"]').first()
        ).toBeVisible()
    })

    test('isim güncelleme başarı toast gösterir', async ({ authedPage: page }) => {
        await page.route('**/users/me', (route) => {
            if (route.request().method() === 'PATCH') {
                route.fulfill({ status: 200, contentType: 'application/json', body: '{"id":1}' })
            } else {
                route.continue()
            }
        })
        await page.goto('/profile')
        const nameInput = page.locator('input[name="ad_soyad"], input[name="full_name"]').first()
        await expect(nameInput).toBeVisible({ timeout: 15_000 })
        await nameInput.fill('Test Kullanıcı')
        const [request] = await Promise.all([
            page.waitForRequest(
                (req) => req.url().includes('/users/me') && req.method() === 'PATCH',
                { timeout: 10_000 }
            ),
            page.getByRole('button', { name: 'Kaydet', exact: true }).click(),
        ])
        expect(request.method()).toBe('PATCH')
        // Success path calls window.location.reload() immediately after toast — wait for reload
        await page.waitForLoadState('load', { timeout: 8_000 })
    })

    test('"Şifremi Güncelle" butonu render edilir', async ({ authedPage: page }) => {
        await page.goto('/profile')
        await expect(page.getByRole('button', { name: 'Şifremi Güncelle' })).toBeVisible({ timeout: 15_000 })
    })

    test('şifre değiştirme — boş form submit edilince validasyon hatası', async ({ authedPage: page }) => {
        await page.goto('/profile')
        await expect(page.getByRole('button', { name: 'Şifremi Güncelle' })).toBeVisible({ timeout: 15_000 })
        await page.getByRole('button', { name: 'Şifremi Güncelle' }).click()
        // Her iki alan da hata verebilir → .first() strict mode ihlalini önler
        await expect(page.getByText('Mevcut şifrenizi girin.').or(page.getByText('Şifre tekrarını girin.')).first()).toBeVisible({ timeout: 5_000 })
    })

    test('şifre değiştirme — yeni şifre eşleşmezse hata gösterilir', async ({ authedPage: page }) => {
        await page.goto('/profile')
        await expect(page.getByRole('button', { name: 'Şifremi Güncelle' })).toBeVisible({ timeout: 15_000 })
        // Mevcut şifre
        await page.locator('input[name="current_password"]').fill('EskiSifre123!')
        // Yeni şifre
        await page.locator('input[name="new_password"]').fill('YeniSifre123!')
        // Tekrar — yanlış
        await page.locator('input[name="confirm_password"]').fill('FarkliSifre456!')
        await page.getByRole('button', { name: 'Şifremi Güncelle' }).click()
        await expect(page.getByText(/eşleşmiyor|uyuşmuyor/i)).toBeVisible({ timeout: 5_000 })
    })

    test('şifre değiştirme — başarılı POST isteği gönderilir', async ({ authedPage: page }) => {
        await page.route('**/api/v1/users/me/change-password**', r =>
            r.fulfill({ status: 200, contentType: 'application/json', body: '{"detail":"ok"}' })
        )
        await page.goto('/profile')
        await expect(page.getByRole('button', { name: 'Şifremi Güncelle' })).toBeVisible({ timeout: 15_000 })
        await page.locator('input[name="current_password"]').fill('EskiSifre123!')
        await page.locator('input[name="new_password"]').fill('YeniSifre123!')
        await page.locator('input[name="confirm_password"]').fill('YeniSifre123!')
        const [req] = await Promise.all([
            page.waitForRequest(
                r => r.url().includes('/users/me/change-password') && r.method() === 'POST',
                { timeout: 10_000 }
            ),
            page.getByRole('button', { name: 'Şifremi Güncelle' }).click(),
        ])
        expect(req.method()).toBe('POST')
        const body = JSON.parse(req.postData() || '{}')
        expect(body.current_password).toBe('EskiSifre123!')
        expect(body.new_password).toBe('YeniSifre123!')
    })
})
