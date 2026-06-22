import { Page } from '@playwright/test'

// Minimal user object that satisfies AuthContext.mapUserData
const mockUser = () => ({
    id: 1,
    kullanici_adi: process.env.E2E_USERNAME || 'admin',
    username: process.env.E2E_USERNAME || 'admin',
    ad_soyad: 'Admin User',
    full_name: 'Admin User',
    rol: { ad: 'super_admin' },
    role: 'super_admin',
    aktif: true,
    is_active: true,
})

export async function loginViaApi(page: Page): Promise<void> {
    const resp = await page.request.post('/api/v1/auth/token', {
        form: {
            username: process.env.E2E_USERNAME!,
            password: process.env.E2E_PASSWORD!,
        },
    })

    if (!resp.ok()) {
        throw new Error(`API login failed: ${resp.status()} ${await resp.text()}`)
    }

    const { access_token } = await resp.json() as { access_token: string }

    // SEC-006: the app reads access_token from sessionStorage (not localStorage)
    // to limit XSS token theft; the E2E auth seed must match or every
    // authenticated page redirects to /login and all specs fail.
    await page.addInitScript((token: string) => {
        sessionStorage.setItem('access_token', token)
    }, access_token)

    // Mock /auth/me so tests are not blocked by DB availability
    await page.route('**/auth/me', (route) =>
        route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(mockUser()),
        })
    )
}
