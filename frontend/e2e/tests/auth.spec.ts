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
        // 2026-07-07: teşhis edildi -> gerçek bir toast+inline çift render YOKTU.
        // `.first()` sadece regex'in aşırı geniş olmasını maskeliyordu: aynı
        // regex hem statik "E-Posta / Kullanıcı Adı" alan etiketine hem de
        // gerçek hata mesajına ("Kullanıcı adı veya şifre hatalı.") uyuyordu
        // -> strict-mode "resolved to 2 elements" ihlali. LoginPage'de toast
        // hiç tetiklenmiyor (login `authApi.login` ham `fetch` kullanıyor,
        // axiosInstance interceptor'ı devrede değil). Kanıt: vitest ile
        // getAllByText sayımı label+hata olmak üzere hep 2 döndü, toast
        // container hiç render olmadı. Kalıcı çözüm: hata mesajına stabil
        // data-testid eklendi (frontend/src/pages/LoginPage.tsx), burada da
        // sadece o elemanı hedefliyoruz.
        await expect(
            page.getByTestId('login-error')
        ).toBeVisible({ timeout: 8_000 })
        await expect(page.getByTestId('login-error')).toHaveText(
            /hatalı|geçersiz|kullanıcı adı|giriş yapılamadı/i
        )
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
