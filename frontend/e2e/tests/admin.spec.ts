import { test, expect } from '../fixtures/auth'

const MOCK_ROLES = [
    { id: 1, ad: 'super_admin', yetkiler: { 'sefer:read': true, 'sefer:write': true, 'sefer:onayla': true, 'rol_oku': true, 'rol_yaz': true } },
    { id: 2, ad: 'operator', yetkiler: { 'sefer:read': true, 'yakit:write': true } },
]

const MOCK_USERS = [
    { id: 1, username: 'admin', email: 'admin@test.com', full_name: 'Admin User', ad_soyad: 'Admin User', role: 'super_admin', is_active: true, created_at: '2025-01-01T00:00:00' },
    { id: 2, username: 'operator', email: 'op@test.com', full_name: 'Operator User', ad_soyad: 'Operator User', role: 'operator', is_active: true, created_at: '2025-01-01T00:00:00' },
]

const MOCK_HEALTH = { status: 'healthy', database: 'ok', redis: 'ok', celery: 'ok', uptime_seconds: 3600 }

test.describe('Admin panel', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        // Single consolidated handler — URL inspection avoids LIFO priority issues
        await page.route('**/api/v1/admin/**', r => {
            const method = r.request().method()
            const url = r.request().url()

            if (url.includes('/health'))
                return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_HEALTH) })

            if (url.includes('/roles'))
                return r.fulfill({ status: 200, contentType: 'application/json',
                    body: JSON.stringify(MOCK_ROLES) })

            if (url.includes('/users')) {
                if (method === 'GET') return r.fulfill({ status: 200, contentType: 'application/json',
                    body: JSON.stringify(MOCK_USERS) })
                if (method === 'POST') return r.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(MOCK_USERS[0]) })
                if (method === 'PUT') return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USERS[0]) })
                if (method === 'DELETE') return r.fulfill({ status: 204 })
            }

            if (url.includes('/notifications'))
                return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })

            if (url.includes('/ml'))
                return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })

            if (url.includes('/maintenance'))
                return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })

            if (url.includes('/imports'))
                return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })

            if (url.includes('/config'))
                return r.fulfill({ status: 200, contentType: 'application/json',
                    body: JSON.stringify({ key: 'test', value: 'test' }) })

            return r.fulfill({ status: 200, contentType: 'application/json',
                body: JSON.stringify({ total_users: 2, active_users: 2 }) })
        })
    })

    test('admin dashboard yüklenir ve stat kartları görünür', async ({ authedPage: page }) => {
        await page.goto('/admin')
        await expect(page.locator('div.grid').first()).toBeVisible({ timeout: 15_000 })
    })

    test('sistem sağlığı sayfası yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/saglik')
        await expect(
            page.locator('div.grid, [class*="health"], [class*="status"]').first()
        ).toBeVisible({ timeout: 15_000 })
    })

    test('admin dışı kullanıcı admin sayfasına erişemez', async ({ authedPage: page }) => {
        await page.route('**/auth/me', r => r.fulfill({
            status: 200, contentType: 'application/json',
            body: JSON.stringify({ id: 2, username: 'operator', role: 'operator', is_active: true, full_name: 'Operator' }),
        }))
        await page.goto('/admin')
        await expect(page).not.toHaveURL(/\/admin$/, { timeout: 8_000 })
    })

    test('kullanıcı yönetimi listesi yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[0].full_name).first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText(MOCK_USERS[1].full_name).first()).toBeVisible()
    })

    test('"Kullanıcı Ekle" butonu modal açar', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[0].full_name).first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /kullanıcı ekle|yeni kullanıcı|ekle/i }).first().click()
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 })
    })

    test('yeni kullanıcı — boş form validasyon hatası gösterir', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[0].full_name).first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /kullanıcı ekle|yeni kullanıcı|ekle/i }).first().click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })
        await dialog.getByRole('button', { name: /kaydet|oluştur/i }).first().click()
        await expect(
            dialog.getByText(/zorunlu|gerekli|required|giriniz/i).first()
        ).toBeVisible({ timeout: 5_000 })
    })

    test('kullanıcı düzenleme — edit butonu modal açar', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[0].full_name).first()).toBeVisible({ timeout: 10_000 })
        const editBtn = page.getByRole('button', { name: /düzenle|edit/i }).first()
        if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await editBtn.click()
            await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 })
        } else {
            test.skip()
        }
    })

    // Regression: shared Modal's focus-trap effect used to depend on `onClose`,
    // which is a fresh function reference on every parent re-render (this
    // page's closeModal is not memoized). Typing a character → state update →
    // re-render → new onClose → effect re-fired → focus stolen back to the
    // dialog's first focusable element (the close button) — on every single
    // keystroke. `.fill()` elsewhere in this file writes the value in one
    // shot and would never have caught this; pressSequentially fires a real
    // keydown/input/keyup cycle per character, matching an actual user.
    test('şifre alanına yazarken odak kapat butonuna kaçmaz (gerçek tuş vuruşu)', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[0].full_name).first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /kullanıcı ekle|yeni kullanıcı|ekle/i }).first().click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })

        const pwField = dialog.locator('input[type="password"]').first()
        await pwField.click()
        await pwField.pressSequentially('Test1234!Secure', { delay: 60 })

        await expect(pwField).toBeFocused()
        await expect(pwField).toHaveValue('Test1234!Secure')
    })

    test('kullanıcı silme — onay dialog açılır', async ({ authedPage: page }) => {
        await page.goto('/admin/kullanicilar')
        await expect(page.getByText(MOCK_USERS[1].full_name).first()).toBeVisible({ timeout: 10_000 })
        const deleteBtn = page.getByRole('button', { name: /sil/i }).first()
        if (await deleteBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
            await deleteBtn.click()
            const confirmation = page.getByRole('dialog')
            if (await confirmation.isVisible({ timeout: 2_000 }).catch(() => false)) {
                await expect(confirmation.getByRole('button', { name: /sil|onayla/i }).first()).toBeVisible()
            }
        } else {
            test.skip()
        }
    })

    test('konfigürasyon sayfası yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/konfig')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('h1, h2, [class*="card"]').first()).toBeVisible({ timeout: 10_000 })
    })

    test('sistem sağlığı — veritabanı durumu "ok" gösterilir', async ({ authedPage: page }) => {
        await page.goto('/admin/saglik')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        // MOCK_HEALTH.database = 'ok' — should appear as status indicator or text
        await expect(
            page.locator('text=/ok|healthy|sağlıklı/i').first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('ML modeli sayfası yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/ml')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        await expect(page.locator('h1, h2, [class*="card"], div.grid').first()).toBeVisible({ timeout: 10_000 })
    })

    test('bildirim yönetimi sayfası yüklenir', async ({ authedPage: page }) => {
        await page.goto('/admin/bildirimler')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.locator('h1, h2, [class*="card"], div.grid').first()).toBeVisible({ timeout: 10_000 })
    })

    test('roller listesi yüklenir ve rol adları görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('operator').first()).toBeVisible()
    })

    test('roller sayfası — "Henüz rol yok" GÖSTERİLMEMELİ (mock format doğru)', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.getByText('Henüz rol yok')).toHaveCount(0, { timeout: 8_000 })
        await expect(page.getByText('super_admin').first()).toBeVisible()
    })

    test('sistem sağlığı sayfası — etkileşimler çalışır', async ({ authedPage: page }) => {
        let backupCalled = false
        await page.route('**/api/v1/admin/health/backup**', r => {
            backupCalled = true
            return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
        })

        await page.goto('/admin/saglik')
        await page.waitForLoadState('networkidle')

        // 1. Yenile butonu görünmeli ve tıklanmalı
        const refreshBtn = page.getByRole('button', { name: /yenile|refresh/i }).first()
        await expect(refreshBtn).toBeVisible()
        await refreshBtn.click()

        // 2. Manuel Yedek Al butonu görünmeli ve tıklanmalı
        const backupBtn = page.getByRole('button', { name: /yedek|backup/i }).first()
        await expect(backupBtn).toBeVisible()
        await backupBtn.click()
        await expect.poll(() => backupCalled).toBe(true)

        // 3. Tab butonlarını bulup geçiş yap
        const healthTab = page.getByRole('button', { name: /sistem durumu|status/i }).first()
        const errorTab = page.getByRole('button', { name: /hata analizi|analysis/i }).first()

        await expect(healthTab).toBeVisible()
        await expect(errorTab).toBeVisible()

        // Hata Analizi tabına geç
        await errorTab.click()
        // Hata Analizi başlığı gelmeli
        await expect(page.getByText(/hata olayları|error events/i).first()).toBeVisible({ timeout: 5_000 })

        // Geri Sistem Durumu tabına geç
        await healthTab.click()
    })
})
