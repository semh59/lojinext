import { test, expect } from '@playwright/test'
import { loginViaApi } from '../helpers/api'

test.describe('Auth akışları', () => {
    test('başarılı login /trips e yönlendirir', async ({ page }) => {
        // Mock getMe so post-login navigation is not blocked by DB availability
        await page.route('**/auth/me', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ id: 1, username: 'admin', role: 'super_admin', is_active: true, full_name: 'Admin' }),
            })
        )
        await page.goto('/login')
        await page.getByPlaceholder(/e-posta/i).fill(process.env.E2E_USERNAME!)
        await page.getByPlaceholder('••••••••').fill(process.env.E2E_PASSWORD!)
        await page.getByRole('button', { name: /sisteme giriş/i }).click()
        await expect(page).toHaveURL(/\/trips/, { timeout: 10_000 })
    })

    test('yanlış şifre hata mesajı gösterir', async ({ page }) => {
        await page.goto('/login')
        await page.getByPlaceholder(/e-posta/i).fill('yanlis@lojinext.com')
        await page.getByPlaceholder('••••••••').fill('yanlis_sifre')
        await page.getByRole('button', { name: /sisteme giriş/i }).click()
        // .first(): hata mesajı hem toast hem inline form hatası olarak
        // AYNI ANDA görünebiliyor -> strict-mode "resolved to 2 elements"
        // ihlali. (2026-07-07: eski 3/300s login bucket'ı altında yanlış
        // şifre çoğu koşuda 429 mesajı üretiyordu ve tek elemandı; bucket
        // CI'da yükselince gerçek 401 yolu açıldı ve çift render göründü.)
        await expect(
            page.getByText(/hatalı|geçersiz|kullanıcı adı|giriş yapılamadı/i).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('logout /login e yönlendirir', async ({ page }) => {
        await loginViaApi(page)
        await page.goto('/trips')
        // Wait for auth to resolve then click logout (button text: "Çıkış Yap")
        const logoutBtn = page.getByRole('button', { name: /çıkış yap|çıkış|logout/i })
        await expect(logoutBtn).toBeVisible({ timeout: 15_000 })
        await logoutBtn.click()
        await expect(page).toHaveURL(/\/login/, { timeout: 8_000 })
    })

    test('korumalı route yetkisiz erişimde /login e yönlendirir', async ({ page }) => {
        await page.goto('/trips')
        await expect(page).toHaveURL(/\/login/, { timeout: 8_000 })
    })

    test('404 sayfası görünür ve geri dön butonu vardır', async ({ page }) => {
        await loginViaApi(page)
        await page.goto('/olmayan-bir-yol')
        await expect(page.getByText(/bulunamadı|not found/i)).toBeVisible()
        await expect(page.getByRole('link', { name: /geri dön|ana sayfa/i })).toBeVisible()
    })
})
